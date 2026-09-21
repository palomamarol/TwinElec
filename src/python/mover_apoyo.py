# -*- coding: utf-8 -*-
"""
mover_apoyo.py
==============
Motor de "mover un apoyo en el terreno" (Unidad de edicion 2 - parte fisica).

Cuando se mueve un apoyo, se recalculan EN CASCADA (toda la linea):
  1. Coordenadas UTM (x, y, cota) del apoyo; la coordenada "esclava" la da la
     orografia (funcion 'terreno(x, y) -> cota', o al reves).
  2. Vanos (distancias horizontales a los apoyos vecinos).
  3. Desniveles (diferencia de cotas; se preservan los desniveles originales
     de la linea y se les aplica el delta de cota del apoyo movido).
  4. Angulo de la linea en el apoyo -> parametro S = 2*cos(alfa/2).
  5. Tensiones y flechas de TODA la linea (ecuacion de cambio de estado,
     criterio A: se mantiene constante la EDS de cada tramo).
  6. Coeficientes L, N, S de los apoyos afectados (movido + vecinos).
  7. Escritura en el Excel de trabajo (copia del original, se va actualizando).

GENERAL: funciona para cualquier linea/excel de la plantilla.

USO:
    from mover_apoyo import mover_apoyo_en_linea
    resumen = mover_apoyo_en_linea(
        ruta_excel, ruta_utm, apoyo_numero=2,
        nuevo_x=458260.0, nuevo_y=4211560.0,   # o nuevo_x + nuevo_z
        salida_excel="line_example_editada.xlsx")
"""
import math
import os
import json
import shutil

import openpyxl

from twinelec_paths import assets_dir

import tensiones_vanos as tv


# ---------------------------------------------------------------------------
# Lectura de datos de la linea
# ---------------------------------------------------------------------------
def leer_utm(ruta_utm):
    """Lee el json de coordenadas UTM. Devuelve lista de dicts ordenada por id:
    [{'id':.., 'x':.., 'y':.., 'cota':..}, ...]."""
    with open(ruta_utm, encoding="utf-8") as f:
        datos = json.load(f)
    if isinstance(datos, dict) and "apoyos" in datos:
        datos = datos["apoyos"]
    utm = []
    for p in datos:
        if isinstance(p, dict):
            utm.append({
                "id": str(p.get("id", p.get("numero", ""))),
                "x": float(p.get("x")),
                "y": float(p.get("y")),
                "cota": float(p.get("cota", p.get("z", 0.0))),
            })
    utm.sort(key=lambda p: int(p["id"]))
    return utm


def _texto_limpio(valor):
    if valor is None:
        return None
    return str(valor).replace("_x000D_", " ").replace("\n", " ").strip()


def _numero(valor):
    if valor is None:
        return None
    t = _texto_limpio(valor).replace(",", ".").replace(" ", "")
    try:
        return float(t)
    except Exception:
        return None


def _normalizar(valor):
    """Normaliza acentos y 'x000D_' para buscar cabeceras de forma robusta."""
    import unicodedata
    t = _texto_limpio(valor)
    if not t:
        return ""
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t


def _clave_normalizada(valor):
    import re
    return re.sub(r"[^a-z0-9]+", " ", _normalizar(valor).lower()).strip()


def _localizar_columna(hoja, patrones, fila_cabecera=1):
    import re
    for celda in hoja[fila_cabecera]:
        clave = _clave_normalizada(celda.value)
        if clave and any(re.search(p, clave) for p in patrones):
            return celda.column - 1
    return None


def leer_geometria_excel(ruta_excel):
    """Lee de 'T. reg. cond. fase' los tramos: vano, desnivel y vano de
    regulacion. Devuelve {'tramos': [(a, h, ar), ...], 'n': n}."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws = wb["T. reg. cond. fase"]
    col_tramo = _localizar_columna(ws, [r"^tramo$"])
    col_vano = _localizar_columna(ws, [r"^vano"])
    col_desn = _localizar_columna(ws, [r"^desnivel"])
    col_ar = _localizar_columna(ws, [r"^vano.*reg"])
    tramos = []
    for fila in ws.iter_rows(min_row=1):
        tramo = _texto_limpio(fila[col_tramo].value) if col_tramo is not None else None
        if not tramo:
            continue
        a = _numero(fila[col_vano].value) if col_vano is not None else None
        h = _numero(fila[col_desn].value) if col_desn is not None else None
        ar = _numero(fila[col_ar].value) if col_ar is not None else None
        if a is not None:
            tramos.append((a, h if h is not None else 0.0,
                           ar if ar is not None else a))
    return {"tramos": tramos, "n": len(tramos)}


def leer_grupos_vanos_regulacion(ruta_excel):
    """Detecta los VANOS DE REGULACION de la linea en 'T. reg. cond. fase'.

    Regla de Paloma: los tramos dentro del mismo vano de regulacion comparten
    la misma tension. Cada grupo queda delimitado en el Excel por las lineas
    negras gruesas (borde superior 'thick/medium' de la fila de datos).

    Devuelve {(tramo_i, tramo_j): id_grupo} con id_grupo = 1, 2, ...
    En el ejemplo cada tramo es su propio grupo (3 grupos)."""
    import re
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws = wb["T. reg. cond. fase"]
    col_tramo = _localizar_columna(ws, [r"^tramo$"])
    grupo_por_tramo = {}
    grupo = 0
    primero = True
    for fila in ws.iter_rows(min_row=1):
        tramo = _texto_limpio(fila[col_tramo].value) if col_tramo is not None else None
        if not tramo:
            continue
        nums = [int(n) for n in re.findall(r"\d+", tramo)]
        if len(nums) < 2:
            continue
        top_style = fila[0].border.top.style
        es_frontera = bool(top_style) and top_style not in ("thin",)
        if primero or es_frontera:
            grupo += 1
            primero = False
        grupo_por_tramo[(nums[0], nums[1])] = grupo
    return grupo_por_tramo


def leer_estado_eds(ruta_excel):
    """Lee la EDS de cada tramo: t0 (temp) y T0 (tension a t0 con el solo peso
    del cable) de 'T. tend. cond. fase'. Devuelve {'t0_C':.., 'T0_por_tramo':..}.
    La deteccion de temperaturas no depende del caracter de grado (puede ser
    ., , o similar), por eso se extrae el numero de la cabecera.
    """
    import re
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws_reg = wb["T. reg. cond. fase"]
    ws_ten = wb["T. tend. cond. fase"]

    # t0: valor numerico bajo la subcolumna 'Temp.' del bloque 'E.D.S.'
    t0 = None
    col_temp = None
    for c in ws_reg[2]:
        if c.value is None:
            continue
        clave = str(c.value).lower()
        if "temp" in clave:
            col_temp = c.column - 1
            break
    if col_temp is not None:
        for fila in ws_reg.iter_rows(min_row=3):
            v = _numero(fila[col_temp].value)
            if v is not None:
                t0 = v
                break

    # columnas T de temperatura en 'T. tend. cond. fase':
    # fila 3 == 'T (daN)' y fila 2 con un numero al principio
    col_t_por_temp = {}
    for c in ws_ten[2]:
        if c.value is None:
            continue
        celda_t = ws_ten.cell(row=3, column=c.column).value
        if celda_t is None:
            continue
        m = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(c.value))
        if m:
            temp = float(m.group(0).replace(",", "."))
            col_t_por_temp[temp] = c.column - 1

    T0_por_tramo = {}
    col_tramo = _localizar_columna(ws_ten, [r"^tramo$"])
    for fila in ws_ten.iter_rows(min_row=4, max_row=12):
        tramo = _texto_limpio(fila[col_tramo].value) if col_tramo is not None else None
        if not tramo:
            continue
        nums = [int(n) for n in __import__("re").findall(r"\d+", tramo)]
        if len(nums) < 2:
            continue
        clave_tramo = (nums[0], nums[1])
        if t0 is not None and t0 in col_t_por_temp:
            col_t = col_t_por_temp[t0]
            if col_t < len(fila):
                T0_por_tramo[clave_tramo] = _numero(fila[col_t].value)
    return {"t0_C": t0 if t0 is not None else 10.0,
            "T0_por_tramo": T0_por_tramo,
            "p0_daN_m": None}  # el peso del cable se pasa aparte


# ---------------------------------------------------------------------------
# Geometria de la linea
# ---------------------------------------------------------------------------
def vanos_desniveles_utm(utm):
    """Vanos (distancia horizontal) y desniveles (diferencia de cotas) entre
    apoyos consecutivos a partir de las coordenadas UTM."""
    n = len(utm)
    vanos = []
    desniveles = []
    for i in range(n - 1):
        dx = utm[i + 1]["x"] - utm[i]["x"]
        dy = utm[i + 1]["y"] - utm[i]["y"]
        dz = utm[i + 1]["cota"] - utm[i]["cota"]
        vanos.append(math.hypot(dx, dy))
        desniveles.append(dz)
    return vanos, desniveles


def angulos_linea_utm(utm):
    """Angulo (sexagesimal, 180 = linea recta) en cada apoyo, calculado desde
    las direcciones de los tramos adyacentes. Extremos -> 180."""
    n = len(utm)
    angulos = [180.0] * n

    def azimut(i):
        dx = utm[i + 1]["x"] - utm[i]["x"]
        dy = utm[i + 1]["y"] - utm[i]["y"]
        return math.degrees(math.atan2(dy, dx))

    for k in range(1, n - 1):
        a1 = azimut(k - 1)
        a2 = azimut(k)
        dif = abs(a1 - a2)
        if dif > 180.0:
            dif = 360.0 - dif
        angulos[k] = 180.0 - dif
    return angulos


def rotar_aguas_abajo(utm, apoyo_k, delta_grados):
    """Rota las coordenadas (x, y) de los apoyos apoyo_k+1..N alrededor del
    apoyo_k (indice 0..n-1) el angulo 'delta_grados' (sexagesimal). Las cotas
    se conservan: solo cambia la PLANTA (este/norte) de los apoyos aguas
    abajo, igual que si la alineacion girase en ese apoyo.

    Los vanos (distancias entre apoyos consecutivos) y los desniveles NO
    cambian porque es una rotacion rigida del tramo. Lo que cambia son las
    coordenadas UTM y el angulo en el propio apoyo.

    Devuelve una copia de la lista UTM con las nuevas posiciones."""
    import math
    copia = [dict(p) for p in utm]
    if apoyo_k < 0 or apoyo_k >= len(utm) - 1:
        return copia
    if abs(delta_grados) < 1e-9:
        return copia
    rad = math.radians(delta_grados)
    c = math.cos(rad)
    s = math.sin(rad)
    x0 = copia[apoyo_k]["x"]
    y0 = copia[apoyo_k]["y"]
    for i in range(apoyo_k + 1, len(copia)):
        dx = copia[i]["x"] - x0
        dy = copia[i]["y"] - y0
        copia[i]["x"] = x0 + c * dx - s * dy
        copia[i]["y"] = y0 + s * dx + c * dy
    return copia


def coeficientes_apoyos(vanos, desniveles, angulos):
    """L, N, S de cada apoyo a partir de vanos, desniveles y angulos:
        L = (a_ant + a_sig)/2
        N = h_ant/a_ant - h_sig/a_sig  (apoyos intermedios)
        N = h_sig/a_sig                (primer apoyo)
        N = -h_ant/a_ant               (ultimo apoyo)
        S = 2*cos(alfa/2)   (solo apoyos de angulo; extremos sin S)
    La convencion de los extremos reproduce la pestaña 'Cálculo de apoyos'.
    Devuelve [{L, N, S}, ...]."""
    m = len(vanos) + 1
    res = []
    for k in range(m):
        l_ant = vanos[k - 1] if k - 1 >= 0 else 0.0
        l_sig = vanos[k] if k < len(vanos) else 0.0
        h_ant = desniveles[k - 1] if k - 1 >= 0 else 0.0
        h_sig = desniveles[k] if k < len(desniveles) else 0.0
        L = (l_ant + l_sig) / 2.0
        if k == 0:
            N = h_sig / l_sig if l_sig > 0 else 0.0
        elif k == m - 1:
            N = -h_ant / l_ant if l_ant > 0 else 0.0
        else:
            N = 0.0
            if l_ant > 0:
                N += h_ant / l_ant
            if l_sig > 0:
                N -= h_sig / l_sig
        alfa = angulos[k]
        S = None
        if 0.0 < alfa < 180.0:
            S = 2.0 * math.cos(math.radians(alfa / 2.0))
        res.append({"L": L, "N": N, "S": S})
    return res


def nuevo_angulo_tras_mover(utm, apoyo_k):
    """Recalcula el angulo del apoyo movido (y solo el suyo) tras cambiar las
    coordenadas de 'apoyo_k' en 'utm'."""
    n = len(utm)
    if n < 3 or apoyo_k <= 0 or apoyo_k >= n - 1:
        return 180.0
    i = apoyo_k

    def az(i):
        dx = utm[i + 1]["x"] - utm[i]["x"]
        dy = utm[i + 1]["y"] - utm[i]["y"]
        return math.degrees(math.atan2(dy, dx))

    a1 = az(i - 1)
    a2 = az(i)
    dif = abs(a1 - a2)
    if dif > 180.0:
        dif = 360.0 - dif
    return 180.0 - dif


def mover_coordenadas(utm, apoyo_k, nuevo_x=None, nuevo_y=None, nuevo_z=None,
                      terreno=None):
    """Actualiza las coordenadas del apoyo 'apoyo_k' (indice 0..n-1). Reglas:
      - Si se da (x, y) y no z -> z = terreno(x, y)  (z esclava de la orografia)
      - Si se da (x, z) y no y -> y se obtiene de terreno_inverso
        (por defecto no disponible; hay que dar x e y, o x, z e y).
      - Si se da z y no (x, y) -> solo cambia la cota (x, y quedan igual).
    Devuelve la lista utm modificada."""
    utm = [dict(p) for p in utm]
    p = utm[apoyo_k]
    if nuevo_x is not None:
        p["x"] = float(nuevo_x)
    if nuevo_y is not None:
        p["y"] = float(nuevo_y)
    if nuevo_z is not None:
        p["cota"] = float(nuevo_z)
    elif (nuevo_x is not None or nuevo_y is not None) and terreno is not None:
        p["cota"] = float(terreno(p["x"], p["y"]))
    return utm


# ---------------------------------------------------------------------------
# Recalculo de tensiones con la EDS constante (opcion A)
# ---------------------------------------------------------------------------
def CONDICIONES_HIPOTESIS():
    """(clave, t_C, clave_sobrecarga) de las columnas de 'T. reg. cond. fase'.
    Deducidas y validadas contra el Excel de demostración:
      T.max viento a -10 C con Sv;  T.max hielo a -15 C con Sh;
      T.Viento 1/2 a -10 C con S_vm;  15 C+V con Sv120;  0 C+H con Sh;  50 C.
    """
    return [
        ("TVF", -10.0, "Sv"),
        ("THF", -15.0, "Sh"),
        ("TVM", -10.0, "S_vm"),
        ("15V", 15.0, "Sv120"),
        ("T0H", 0.0, "Sh"),
        ("TTemp", 50.0, "Peso cable"),
    ]


def recalcular_tensiones_tramos(vanos, desniveles, estado_eds, alfa, E, S,
                                sobrecarga_por_tramo, grupos=None,
                                condiciones=None):
    """Tensiones y flechas por tramo con la EDS constante (opcion A).

    Regla de los vanos de regulacion: los tramos del MISMO vano de regulacion
    comparten la misma tension (el vano de regulacion del grupo es
    ar = sqrt(suma(a^3)/suma(a)) sobre los tramos del grupo); la flecha de cada
    tramo se calcula con esa tension comun y su propio vano/desnivel.

    grupos: {i_tramo: id_grupo} o None (cada tramo es su propio grupo).
    sobrecarga_por_tramo: lista con un dict {'Sv','Sh','S_vm','Sv120',
                                             'Peso cable'} por tramo.
    Devuelve {i_tramo: {clave_cond: {'T':.., 'F':..}}}.
    """
    if condiciones is None:
        condiciones = CONDICIONES_HIPOTESIS()
    n = len(vanos)
    if grupos is None:
        grupos = {i: i for i in range(n)}

    # agrupar indices de tramo por id de grupo (orden estable)
    grupos_tramos = {}
    for i, g in grupos.items():
        grupos_tramos.setdefault(g, []).append(i)

    t0 = estado_eds["t0_C"]
    p0 = estado_eds["p0_daN_m"]
    res = {}
    for g, idxs in grupos_tramos.items():
        ar = tv.vano_regulacion([vanos[i] for i in idxs])
        if ar is None:
            continue
        T0 = estado_eds["T0_por_tramo"][idxs[0]] if idxs else None
        if T0 is None:
            continue
        # Tension comun del grupo por condicion (un solo valor por condicion)
        tens_grupo = {}
        for clave, t, clave_p in condiciones:
            p = sobrecarga_por_tramo[idxs[0]].get(clave_p)
            if p is None:
                continue
            Tf = tv.tension_cambio_estado(t0, T0, p0, ar, t, p, alfa, E, S)
            if Tf is not None:
                tens_grupo[clave] = Tf
        # Flecha de cada tramo con la tension comun del grupo
        for i in idxs:
            h = desniveles[i] if i < len(desniveles) else 0.0
            res[i] = {}
            for clave, t, clave_p in condiciones:
                if clave not in tens_grupo:
                    continue
                p = sobrecarga_por_tramo[i].get(clave_p)
                if p is None:
                    continue
                f = tv.flecha_vano(vanos[i], h, p, tens_grupo[clave])
                res[i][clave] = {"T": tens_grupo[clave], "F": f}
    return res


def copiar_excel_trabajo(ruta_excel, salida_excel):
    """Copia el Excel original a la ruta de trabajo (una sola vez; si ya
    existe la copia, la reutiliza para acumular cambios)."""
    if not os.path.exists(salida_excel):
        os.makedirs(os.path.dirname(os.path.abspath(salida_excel)),
                    exist_ok=True)
        shutil.copy2(ruta_excel, salida_excel)
        print("  [copiar_excel_trabajo] Copia creada:", salida_excel)
    return salida_excel


def _fila_de_tramo(ws, col_tramo, tramo_i, tramo_j):
    """Fila (1-based) donde la columna 'Tramo' contiene '  i-  j'."""
    for fila in ws.iter_rows(min_row=1):
        v = _texto_limpio(fila[col_tramo].value)
        if not v:
            continue
        nums = [int(n) for n in __import__("re").findall(r"\d+", v)]
        if len(nums) >= 2 and nums[0] == tramo_i and nums[1] == tramo_j:
            return fila[col_tramo].row
    return None


def _columna_condicion_reg(ws, patrones):
    """Columna (0-based) de la celda de fila 2 cuyo texto coincide; la celda de
    fila 3 debe ser 'T (daN)' (el par T/F)."""
    import re
    for celda in ws[2]:
        clave = _clave_normalizada(celda.value)
        if clave and any(re.search(p, clave) for p in patrones):
            if ws.cell(row=3, column=celda.column).value is not None:
                return celda.column - 1
    return None


def _tiene_flecha(ws, col_t):
    """True si la condicion cuya T esta en 'col_t' tiene columna F en col_t+1
    (la fila 3 de la siguiente columna es 'F (m)')."""
    celda = ws.cell(row=3, column=col_t + 2).value
    return celda is not None and "f" in str(celda).lower()


def actualizar_excel_trabajo(salida_excel, vanos, desniveles, angulos, coefs,
                             tensiones_por_tramo, vano_reg_por_tramo=None):
    """Escribe en el Excel de trabajo (copia del original) los nuevos valores:
      - 'T. reg. cond. fase': Vano, Desnivel, Vano Reg. y las T/F por hipotesis
      - 'Cálculo de apoyos': angulo, y coeficientes L, N, S de cada apoyo
    Devuelve el libro (wb) sin guardar (para que el orquestador lo cierre)."""
    wb = openpyxl.load_workbook(salida_excel)
    ws_reg = wb["T. reg. cond. fase"]
    ws_cal = wb["Cálculo de apoyos"]

    # ---- 'T. reg. cond. fase' ----
    col_tramo = _localizar_columna(ws_reg, [r"^tramo$"])
    col_vano = _localizar_columna(ws_reg, [r"^vano"])
    col_desn = _localizar_columna(ws_reg, [r"^desnivel"])
    col_ar = _localizar_columna(ws_reg, [r"^vano.*reg"])
    # localizar columnas T de cada condicion (por nombre en fila 2)
    cols_cond = {
        "TVF": _columna_condicion_reg(ws_reg, [r"^t maxima viento"]),
        "THF": _columna_condicion_reg(ws_reg, [r"^t maxima hielo"]),
        "TVM": _columna_condicion_reg(ws_reg, [r"viento 1 2"]),
        "15V": _columna_condicion_reg(ws_reg, [r"^15"]),
        "T0H": _columna_condicion_reg(ws_reg, [r"^0"]),
        "TTemp": _columna_condicion_reg(ws_reg, [r"^50"]),
    }
    for i, a in enumerate(vanos):
        fila = _fila_de_tramo(ws_reg, col_tramo, i + 1, i + 2)
        if fila is None:
            continue
        if col_vano is not None:
            ws_reg.cell(row=fila, column=col_vano + 1).value = round(a, 2)
        if col_desn is not None:
            ws_reg.cell(row=fila, column=col_desn + 1).value = round(desniveles[i], 3)
        if col_ar is not None:
            ar_val = (vano_reg_por_tramo[i] if vano_reg_por_tramo
                      and i < len(vano_reg_por_tramo) else a)
            ws_reg.cell(row=fila, column=col_ar + 1).value = round(ar_val, 2)
        for clave, item in tensiones_por_tramo[i].items():
            col_t = cols_cond.get(clave)
            if col_t is None:
                continue
            ws_reg.cell(row=fila, column=col_t + 1).value = round(item["T"], 1)
            if _tiene_flecha(ws_reg, col_t):
                ws_reg.cell(row=fila, column=col_t + 2).value = round(item["F"], 3)

    # ---- 'Cálculo de apoyos' ----
    col_ang = _localizar_columna(ws_cal, [r"valor.*angulo"])
    # Coeficientes L, N, S: cabecera fusionada 'Coeficientes L, N, S' en
    # la columna L; N = L+1 y S = L+2.
    col_l = _localizar_columna(ws_cal, [r"^coeficientes.*l.*n.*s"])
    col_n = col_l + 1 if col_l is not None else None
    col_s = col_n + 1 if col_n is not None else None
    for k, c in enumerate(coefs):
        fila = None
        for r in ws_cal.iter_rows(min_row=1, max_col=2):
            if _numero(r[0].value) == k + 1:
                fila = r[0].row
                break
        if fila is None:
            continue
        if col_ang is not None:
            ws_cal.cell(row=fila, column=col_ang + 1).value = angulos[k]
        if col_l is not None:
            ws_cal.cell(row=fila, column=col_l + 1).value = round(c["L"], 3)
        if col_n is not None:
            ws_cal.cell(row=fila, column=col_n + 1).value = round(c["N"], 4)
        if col_s is not None and c.get("S") is not None:
            ws_cal.cell(row=fila, column=col_s + 1).value = round(c["S"], 3)
    wb.save(salida_excel)
    return wb


# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------
def mover_apoyo_en_linea(ruta_excel, ruta_utm, apoyo_numero,
                         nuevo_x=None, nuevo_y=None, nuevo_z=None,
                         terreno=None, salida_excel=None, viento_kmh=120.0,
                         utm_inicial=None):
    """Mueve un apoyo y recalcula toda la linea (vanos, desniveles, angulos,
    tensiones, flechas, L/N/S) escribiendo el resultado en el Excel de trabajo
    (copia del original que se va actualizando con cada cambio).

    Reglas:
      - apoyo_numero: 1..N
      - Si se da (x, y) y no z -> z = terreno(x, y) (esclava de la orografia)
      - Si se da z (con o sin x/y) -> se usa tal cual la cota
    Devuelve un dict resumen con los nuevos valores calculados.
    """
    # ---- Datos base ----
    import datos_apoyos_excel as dae
    from sobrecargas import calcular_sobrecargas

    if salida_excel is None:
        base = os.path.splitext(os.path.basename(ruta_excel))[0]
        salida_excel = os.path.join(os.path.dirname(os.path.abspath(ruta_excel)),
                                    base + "_editada.xlsx")

    utm = utm_inicial if utm_inicial is not None else leer_utm(ruta_utm)
    n = len(utm)
    k = apoyo_numero - 1
    if k < 0 or k >= n:
        raise ValueError("apoyo_numero fuera de rango (1..%d)" % n)

    z_orig = utm[k]["cota"]
    utm_orig = [dict(p) for p in utm]
    utm = mover_coordenadas(utm, k, nuevo_x, nuevo_y, nuevo_z, terreno)

    # ---- Geometria: solo cambian los dos tramos aledaños al apoyo movido ----
    # Base: vanos y desniveles del Excel original (el resto queda identico).
    geom = leer_geometria_excel(ruta_excel)
    vanos = [t[0] for t in geom["tramos"]]
    desniveles = [t[1] for t in geom["tramos"]]
    delta_z = utm[k]["cota"] - z_orig

    def _distancia_utm(a, b):
        return math.hypot(utm[b]["x"] - utm[a]["x"],
                          utm[b]["y"] - utm[a]["y"])

    def _distancia_utm_orig(a, b):
        return math.hypot(utm_orig[b]["x"] - utm_orig[a]["x"],
                          utm_orig[b]["y"] - utm_orig[a]["y"])

    if k - 1 >= 0:
        # tramo k-1 (apoyo k-1 -> k): vano y desnivel cambian
        vanos[k - 1] += _distancia_utm(k - 1, k) - _distancia_utm_orig(k - 1, k)
        desniveles[k - 1] += delta_z
    if k < n - 1:
        # tramo k (apoyo k -> k+1): vano y desnivel cambian
        vanos[k] += _distancia_utm(k, k + 1) - _distancia_utm_orig(k, k + 1)
        desniveles[k] -= delta_z
    angulos = angulos_linea_utm(utm)
    coefs = coeficientes_apoyos(vanos, desniveles, angulos)

    # ---- Conductor y sobrecargas por tramo ----
    conductor = dae.leer_conductor(ruta_excel)
    props = tv.propiedades_conductor(conductor)
    alfa = props["alfa_1_C"]
    E = props["E_daN_mm2"]
    S = props["seccion_mm2"]
    p0 = props["peso_daN_m"]
    peso_kg_m = conductor["masa_kg_km"] / 1000.0
    diam_mm = conductor["diametro_mm"]

    zonas_tramo = dae.extraer_zonas_por_tramo(ruta_excel)
    sobrecarga_por_tramo = []
    for i in range(len(vanos)):
        zona = zonas_tramo.get((i + 1, i + 2), "A")
        sob = calcular_sobrecargas(diam_mm, peso_kg_m, zona, viento_kmh)
        sobrecarga_por_tramo.append({
            "Sv": sob["Sv"], "Sv120": sob["Sv120"], "Sh": sob["Sh"],
            "S_vm": sob["S_vm"], "Peso cable": p0,
        })

    # ---- EDS (opcion A: constante) y tensiones por vano de regulacion ----
    estado_eds = leer_estado_eds(ruta_excel)
    estado_eds["p0_daN_m"] = p0
    # ordenar T0 por tramo en la secuencia 1-2, 2-3, ...
    t0s = []
    for i in range(len(vanos)):
        t0s.append(estado_eds["T0_por_tramo"].get((i + 1, i + 2)))
    estado_eds["T0_por_tramo"] = t0s

    # Grupos de vanos de regulacion (tension comun dentro de cada grupo)
    grupos_clave = leer_grupos_vanos_regulacion(ruta_excel)
    grupos_por_indice = {}
    grupos_tramos = {}
    for i in range(len(vanos)):
        g = grupos_clave.get((i + 1, i + 2), i + 1)
        grupos_por_indice[i] = g
        grupos_tramos.setdefault(g, []).append(i)
    # vano de regulacion de cada tramo (el de su grupo)
    vano_reg_por_tramo = []
    for i in range(len(vanos)):
        ar_grupo = tv.vano_regulacion(
            [vanos[j] for j in grupos_tramos[grupos_por_indice[i]]])
        vano_reg_por_tramo.append(ar_grupo if ar_grupo is not None else vanos[i])

    tensiones = recalcular_tensiones_tramos(
        vanos, desniveles, estado_eds, alfa, E, S, sobrecarga_por_tramo,
        grupos=grupos_por_indice)

    # ---- Excel de trabajo (copia acumulativa) ----
    copiar_excel_trabajo(ruta_excel, salida_excel)
    actualizar_excel_trabajo(salida_excel, vanos, desniveles, angulos,
                             coefs, tensiones,
                             vano_reg_por_tramo=vano_reg_por_tramo)

    # ---- Esfuerzos V/T/L de las hipotesis (CalculoApoyos) ----
    try:
        from cambiar_cadena_conductor import recalcular_esfuerzos_apoyos
        recalcular_esfuerzos_apoyos(ruta_excel, salida_excel,
                                    tensiones=tensiones)
        print("  [mover_apoyo] Esfuerzos V/T/L actualizados.")
    except Exception as error_esf:
        print("  ⚠️ No se pudieron recalcular los esfuerzos V/T/L:",
              error_esf)

    # ---- Nuevo UTM (json intermedio; el .docx se genera en otra etapa) ----
    # Se escribe JUNTO al Excel de trabajo (la carpeta activa de la app), NO
    # junto a la ruta UTM de entrada (que en el .exe es Datos/). Asi la app y
    # la exportacion leen siempre los cambios.
    utm_editado = os.path.join(os.path.dirname(os.path.abspath(salida_excel)),
                               "utm_editado.json")
    with open(utm_editado, "w", encoding="utf-8") as f:
        json.dump(utm, f, ensure_ascii=False, indent=2)

    # ---- Documento UTM (Word) actualizado automáticamente ----
    doc_utm = None
    try:
        from generar_doc_utm import generar_docx_desde_json
        doc_utm = generar_docx_desde_json(utm_editado)
        print("  [mover_apoyo] Documento UTM actualizado:", doc_utm)
    except Exception as error_docx:
        print("  ⚠️ No se pudo regenerar el documento UTM:", error_docx)

    return {
        "salida_excel": os.path.abspath(salida_excel),
        "utm_editado": os.path.abspath(utm_editado),
        "doc_utm": doc_utm,
        "utm": utm,
        "vanos": vanos,
        "desniveles": desniveles,
        "angulos": angulos,
        "coeficientes": coefs,
        "tensiones_por_tramo": tensiones,
    }


def regenerar_csv_linea(ruta_utm, ruta_csv=None):
    """Regenera 'coordenadas_linea.csv' (Apoyo,X,Z,Y,Angulo) a partir de las
    coordenadas UTM ACTUALES de los apoyos.

    El CSV de Unity usa las coordenadas RELATIVAS al apoyo 1:
        X = este   - este1
        Z = norte  - norte1
        Y = cota   - cota1
    y los angulos calculados desde la geometria UTM (igual que el CSV
    original que usa el proyecto).

    ruta_utm: json UTM (el original o el 'utm_editado.json' tras mover).
    Si ruta_csv es None, escribe en unity/Assets/coordenadas_linea.csv.
    """
    import csv as _csv
    utm = leer_utm(ruta_utm)
    if not utm:
        raise ValueError("No hay apoyos UTM en '%s'." % ruta_utm)
    x0 = utm[0]["x"]
    y0 = utm[0]["y"]
    cota0 = utm[0]["cota"]
    angulos = angulos_linea_utm(utm)

    if ruta_csv is None:
        ruta_csv = str(assets_dir() / "coordenadas_linea.csv")
    os.makedirs(os.path.dirname(os.path.abspath(ruta_csv)), exist_ok=True)
    with open(ruta_csv, "w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["Apoyo", "X", "Z", "Y", "Angulo"])
        for i, p in enumerate(utm):
            w.writerow([i + 1,
                        round(p["x"] - x0, 3),
                        round(p["y"] - y0, 3),
                        round(p["cota"] - cota0, 3),
                        round(angulos[i], 3)])
    return os.path.abspath(ruta_csv)


def mover_apoyo_con_orografia(ruta_excel, ruta_utm, apoyo_numero,
                              x=None, y=None, z=None, eje_auto="z",
                              salida_excel=None, orog=None):
    """Mueve un apoyo con 2 grados de libertad: la tercera coordenada la
    calcula automaticamente la orografia PNOA.

    eje_auto:
      'z' -> se dan x e y;  z = cota_en(x, y)
      'x' -> se dan y y z;  x = buscar_x_para_cota(y, z, cerca del apoyo)
      'y' -> se dan x y z;  y = buscar_y_para_cota(x, z, cerca del apoyo)

    Si la posicion objetivo queda FUERA del PNOA o sin dato de orografia,
    levanta ValueError con un mensaje claro (lo mostrara Unity como aviso).
    """
    from orografia import orografia as get_orografia
    if orog is None:
        orog = get_orografia(os.path.dirname(os.path.abspath(ruta_excel)))
    utm_actual = leer_utm(ruta_utm)[apoyo_numero - 1]

    eje_auto = (eje_auto or "z").lower()
    if eje_auto == "z":
        if x is None or y is None:
            raise ValueError("Faltan X e Y (eje automatico Z).")
        z = orog.cota_en(x, y)
        if z is None:
            raise ValueError("La posicion (X=%s, Y=%s) no tiene dato de "
                             "orografia (fuera del PNOA o hueco)." % (x, y))
    elif eje_auto == "x":
        if y is None or z is None:
            raise ValueError("Faltan Y y Z (eje automatico X).")
        x = orog.buscar_x_para_cota(y, z, x_actual=utm_actual["x"])
        if x is None:
            raise ValueError("No se encontro la cota %.1f en la orografia "
                             "para Y=%s cerca del apoyo." % (z, y))
    elif eje_auto == "y":
        if x is None or z is None:
            raise ValueError("Faltan X y Z (eje automatico Y).")
        y = orog.buscar_y_para_cota(x, z, y_actual=utm_actual["y"])
        if y is None:
            raise ValueError("No se encontro la cota %.1f en la orografia "
                             "para X=%s cerca del apoyo." % (z, x))
    else:
        raise ValueError("eje_auto debe ser 'x', 'y' o 'z'.")

    # Paron si la posicion se sale de los PNOA
    if not orog.dentro_de_pnoa(x, y):
        raise ValueError(
            "La posicion (X=%.2f, Y=%.2f) queda FUERA de los PNOA disponibles "
            "(extension: %s). No se puede mover el apoyo fuera del terreno."
            % (x, y, orog.extension))

    res = mover_apoyo_en_linea(ruta_excel, ruta_utm, apoyo_numero,
                               nuevo_x=x, nuevo_y=y, nuevo_z=z,
                               salida_excel=salida_excel)
    res["posicion"] = {"x": x, "y": y, "cota": z}
    res["extension_pnoa"] = list(orog.extension)
    # Regenera el CSV de coordenadas que usa Unity para colocar los apoyos
    try:
        res["csv_linea"] = regenerar_csv_linea(res["utm_editado"])
    except Exception as e:
        res["csv_linea"] = None
        res["aviso_csv"] = str(e)
    return res


def procesar_peticion_json(ruta_peticion, ruta_resultado=None):
    """Lee la peticion JSON de Unity, mueve el apoyo y escribe el resultado
    (o el error). Peticion:
        {"excel":.., "utm":.., "salida_excel":.., "apoyo":N,
         "x":.., "y":.., "z":.., "eje_auto":"z"}
    Solo dos de x/y/z vienen rellenos; la tercera la calcula la orografia.
    """
    with open(ruta_peticion, encoding="utf-8-sig") as f:
        p = json.load(f)
    try:
        res = mover_apoyo_con_orografia(
            p.get("excel"), p.get("utm"), int(p["apoyo"]),
            x=(p.get("x") if p.get("x") is not None else None),
            y=(p.get("y") if p.get("y") is not None else None),
            z=(p.get("z") if p.get("z") is not None else None),
            eje_auto=p.get("eje_auto", "z"),
            salida_excel=p.get("salida_excel"))
        resultado = {"ok": True}
        resultado.update(res)
    except Exception as e:
        resultado = {"ok": False, "error": str(e)}
    if ruta_resultado:
        with open(ruta_resultado, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2, default=str)
    return resultado


if __name__ == "__main__":
    import sys
    import io
    try:
        if sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
    except Exception:
        pass

    if "--peticion" in sys.argv:
        idx = sys.argv.index("--peticion")
        ruta_peticion = sys.argv[idx + 1]
        ruta_resultado = None
        if "--resultado" in sys.argv:
            ruta_resultado = sys.argv[sys.argv.index("--resultado") + 1]
        r = procesar_peticion_json(ruta_peticion, ruta_resultado)
        print(json.dumps(r, ensure_ascii=False, indent=2)[:2500])
    else:
        RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "line_example.xlsx")
        RUTA_UTM = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "utm_example.json")
        SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "line_example_editada.xlsx")

        print("== DEMO: mover el apoyo 2 a (458260, 4211560) con cota 558.0 ==")
        res = mover_apoyo_en_linea(RUTA, RUTA_UTM, apoyo_numero=2,
                                   nuevo_x=458260.0, nuevo_y=4211560.0,
                                   nuevo_z=558.0, salida_excel=SALIDA)
        print("  Excel de trabajo:", res["salida_excel"])
        print("  Vanos nuevos:    ", [round(v, 2) for v in res["vanos"]])
        print("  Desniveles nuevos:", [round(d, 3) for d in res["desniveles"]])
        print("  Angulos nuevos:  ", [round(a, 2) for a in res["angulos"]])
        for i, c in enumerate(res["coeficientes"]):
            s = ("%.3f" % c["S"]) if c["S"] is not None else "-"
            print("  Apoyo %d: L=%7.3f  N=%8.4f  S=%s" % (i + 1, c["L"], c["N"], s))
        print("  Tensiones (T en daN):")
        for i, t in res["tensiones_por_tramo"].items():
            fila = " ".join("%s=%s" % (k, round(v["T"], 1)) for k, v in t.items())
            print("    tramo %d-%d: %s" % (i + 1, i + 2, fila))





