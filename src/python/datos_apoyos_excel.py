# -*- coding: utf-8 -*-
"""
datos_apoyos_excel.py
=====================
Extrae del Excel de la línea (p. ej. line_example.xlsx) y prepara los datos que
necesitan los graficos de utilizacion del Tema 10:

  - tipo de apoyo          -> pestaña "Cálculo de apoyos", columna "Tipo"
  - angulo de la linea     -> pestaña "Cálculo de apoyos", columna "Valor ángulo"
  - coef. de seguridad     -> pestaña "Cálculo de apoyos", columna "Coefici. de seguri."
  - coeficientes L, N, S   -> pestaña "Cálculo de apoyos", ultimas columnas
  - zona de calculo        -> pestaña "T. reg. cond. fase", columna "Zona"
                              (cada tramo tiene una zona; el apoyo hereda la de
                              sus tramos adyacentes)
  - familia de armado y d1 -> pestaña "Apoyos y crucetas" + catalogo de Blender

d1 = distancia entre montantes (ancho del armado en la parte superior).
    Catalogo extraido de BlenderScripts/crear_armados.py:
      familia C / M50 / M60 -> 0.510 m
      familia G             -> 0.908 m
      PRESILLA_250          -> 0.200 m
      PRESILLA_400_1250     -> 0.320 m

USO:
    from datos_apoyos_excel import extraer_apoyos
    apoyos = extraer_apoyos("line_example.xlsx")
    for a in apoyos:
        print(a["numero"], a["tipo_clave"], a["zona"], a["d1_m"])
"""
import os
import re
import json
import unicodedata

import openpyxl

from twinelec_paths import catalogs_dir

# ---------------------------------------------------------------------------
# Sinonimos que usa la plantilla del Excel para la columna "Tipo"
# ---------------------------------------------------------------------------
ALIAS_TIPOS = [
    (r"p.*linea|p\.linea|principio", "principio_final_de_linea"),
    (r"f.*linea|final", "principio_final_de_linea"),
    (r"aline.*susp", "alineacion_suspension"),
    (r"aline.*amarre|aline.*amar", "alineacion_amarre"),
    (r"aline.*anc", "alineacion_anclaje"),
    (r"ang.*susp", "angulo_suspension"),
    (r"ang.*amarre|ang.*amar", "angulo_amarre"),
    (r"ang.*anc", "angulo_anclaje"),
]

# ---------------------------------------------------------------------------
# Catalogo de d1 (ancho de montantes) por familia de armado.
# Extraido de BlenderScripts/crear_armados.py
# ---------------------------------------------------------------------------
D1_POR_FAMILIA = {
    "C": 0.510,          # ANCHO_M50_M60_C = 0.510
    "M50": 0.510,
    "M60": 0.510,
    "G": 0.908,          # ANCHO_G = 0.908
    "PRESILLA_250": 0.200,
    "PRESILLA_400_1250": 0.320,
}

# ---------------------------------------------------------------------------
# Numero de cadenas por fase (NCAD) segun tipo de apoyo y seguridad
# (normal N / reforzada R). Tabla guia de Paloma.
# ---------------------------------------------------------------------------
NCAD_TABLA = {
    "principio_final_de_linea": {"N": 1, "R": 2},
    "alineacion_suspension":    {"N": 1, "R": 2},
    "alineacion_amarre":        {"N": 2, "R": 4},
    "alineacion_anclaje":       {"N": 2, "R": 4},
    "angulo_suspension":        {"N": 1, "R": 2},
    "angulo_amarre":            {"N": 2, "R": 4},
    "angulo_anclaje":           {"N": 2, "R": 4},
}

# ---------------------------------------------------------------------------
# Altura h (y h') de la ecuacion resistente (Tema 10, criterio de Paloma):
#   - apoyos de suspension:  h = HREF + Sep.conductores - LCAD - solera
#   - apoyos de amarre/anclaje: h = HREF + Sep.conductores - solera
# HREF: 'Altura de refere. m' de 'Elección apoyos'.
# Sep.conductores: 'Separ. fases norma. m' de 'Elección apoyos' (la separacion
# normalizada entre fases; la misma que se usa como D en el vano maximo).
# LCAD: longitud de la cadena de aisladores (catalogo de cadenas).
# solera: 0.2 m (constante).
# ---------------------------------------------------------------------------
SOLERA_M = 0.2
TIPOS_SUSPENSION = ("alineacion_suspension", "angulo_suspension")

# Ruta al catalogo de cadenas de aisladores
RUTA_CATALOGO_CADENAS = os.path.join(
    str(catalogs_dir()), "catalogo_cadenas_completo.json")

# ---------------------------------------------------------------------------
# Utilidades de texto (misma convencion que principal.py)
# ---------------------------------------------------------------------------
def _texto_limpio(valor):
    if valor is None:
        return None
    texto = str(valor).replace("_x000D_", " ").replace("\n", " ").strip()
    texto = re.sub(r"\s+", " ", texto)
    if not texto or all(caracter in "-–— " for caracter in texto):
        return None
    return texto


def _clave_conductor(valor):
    """Iguala LA-56, LA 56 y la designacion normativa sin perder sus cifras."""
    texto = _texto_limpio(valor)
    if texto is None:
        return ""
    texto = unicodedata.normalize("NFKD", texto).upper()
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", "", texto)


def _clave_texto(valor):
    texto = _texto_limpio(valor)
    if texto is None:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def leer_conductor(archivo_excel, ruta_catalogo=None):
    """Lee 'Tipo de conductor' de la hoja Mediciones y lo resuelve contra el
    catálogo data/catalogs/conductors/catalogo_conductores.json.

    Es GENERAL: funciona para cualquier conductor que este en el catalogo
    (LA-30, LA-56, LA-78, LA-110, ...). Devuelve diametro y peso del conductor.
    """
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Mediciones"]
    nomenclatura = None
    for fila in ws.iter_rows():
        if any(_clave_texto(c.value) == "tipo de conductor" for c in fila):
            valores = [_texto_limpio(c.value) for c in fila if _texto_limpio(c.value)]
            if valores:
                nomenclatura = valores[-1]
            break
    if nomenclatura is None:
        raise ValueError("No se encontro 'Tipo de conductor' en la hoja Mediciones.")

    if ruta_catalogo is None:
        ruta_catalogo = str(
            catalogs_dir() / "conductors" / "catalogo_conductores.json"
        )
    if not os.path.exists(ruta_catalogo):
        raise FileNotFoundError("Catalogo de conductores no encontrado: %s" % ruta_catalogo)

    with open(ruta_catalogo, encoding="utf-8") as archivo:
        catalogo = json.load(archivo)

    clave_buscada = _clave_conductor(nomenclatura)
    coincidencia = None
    for conductor in catalogo.get("conductores", []):
        nombres = [conductor["designacion"], *conductor.get("aliases", [])]
        if clave_buscada in {_clave_conductor(nombre) for nombre in nombres}:
            coincidencia = conductor
            break
    if coincidencia is None:
        raise ValueError("El conductor '%s' no figura en el catalogo." % nomenclatura)

    return {
        "nomenclatura_excel": nomenclatura,
        "designacion": coincidencia["designacion"],
        "diametro_mm": coincidencia["diametro_mm"],
        "diametro_m": coincidencia["diametro_mm"] / 1000.0,
        "seccion_mm2": coincidencia["seccion_mm2"],
        "masa_kg_km": coincidencia["masa_kg_km"],
        "peso_kg_m": coincidencia["masa_kg_km"] / 1000.0,
        "peso_daN_m": coincidencia["masa_kg_km"] * 0.98 / 1000.0,
    }


def leer_zonas_tendido(archivo_excel):
    """Lee las longitudes 'Zona de tendido A/B/C' de la hoja Mediciones [m].
    Devuelve {zona: longitud} (solo las filas presentes)."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Mediciones"]
    resultado = {}
    for fila in ws.iter_rows():
        texto = _texto_limpio(fila[1].value) if len(fila) > 1 else None
        clave = _clave_texto(texto)
        if "zona de tendido" in clave:
            coincidencia = re.search(r"zona de tendido\s*([abc])", clave)
            if coincidencia:
                letra = coincidencia.group(1).upper()
                resultado[letra] = _numero_decimal(fila[3].value) if len(fila) > 3 else None
    return resultado


def zona_de_tendido_principal(archivo_excel):
    """Zona predominante de la linea segun 'Zona de tendido' de Mediciones
    (la que acumula mas metros de linea)."""
    zonas = leer_zonas_tendido(archivo_excel)
    if not zonas:
        return None
    return max(zonas, key=lambda z: zonas.get(z) or 0.0)


def _numero_decimal(valor):
    texto = _texto_limpio(valor)
    if texto is None:
        return None
    texto = texto.replace(" ", "").replace(",", ".")
    coincidencia = re.search(r"[-+]?\d+(?:\.\d+)?", texto)
    if coincidencia is None:
        return None
    return float(coincidencia.group(0))


def mapear_tipo_a_clave(tipo_texto):
    """Convierte el texto de la columna 'Tipo' del Excel en la clave de CASOS."""
    clave = _clave_texto(tipo_texto)
    if not clave:
        return None
    for patron, tipo in ALIAS_TIPOS:
        if re.search(patron, clave):
            return tipo
    return None


def _localizar_columna(hoja, patrones, fila_cabecera=1):
    """Devuelve el indice de la primera celda de 'fila_cabecera' que contenga
    alguno de los patrones. Usado para no depender de posiciones fijas."""
    for celda in hoja[fila_cabecera]:
        clave = _clave_texto(celda.value)
        if clave and any(re.search(p, clave) for p in patrones):
            return celda.column - 1
    return None


# ---------------------------------------------------------------------------
# Extraccion de zonas (pestaña "T. reg. cond. fase", columna "Zona")
# ---------------------------------------------------------------------------
def extraer_zonas_por_tramo(archivo_excel):
    """Zona (columna 'Zona') de cada tramo en 'T. reg. cond. fase'."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["T. reg. cond. fase"]
    col_tramo = _localizar_columna(ws, [r"^tramo$"])
    col_zona = _localizar_columna(ws, [r"^zona$"])
    if col_tramo is None or col_zona is None:
        raise ValueError("No se encontraron las columnas 'Tramo' o 'Zona' en T. reg. cond. fase.")

    zonas = {}
    for fila in ws.iter_rows(min_row=1):
        tramo = _texto_limpio(fila[col_tramo].value)
        zona = _texto_limpio(fila[col_zona].value)
        if tramo and zona:
            # Tramo del tipo "  1-  2"
            nums = re.findall(r"\d+", tramo)
            if len(nums) >= 2:
                zonas[tuple(int(n) for n in nums)] = zona
    return zonas


def zona_de_apoyo(numero_apoyo, zonas_por_tramo):
    """Zona de un apoyo: la de sus tramos adyacentes (o la unica de la linea)."""
    adyacentes = []
    for (a, b), zona in zonas_por_tramo.items():
        if numero_apoyo in (a, b):
            adyacentes.append(zona)
    if adyacentes:
        # Devuelve la mas frecuente entre los tramos adyacentes
        return max(set(adyacentes), key=adyacentes.count)
    if zonas_por_tramo:
        # Sin tramo identificado, se asume la zona comun de la linea
        return max(zonas_por_tramo.values())
    return None


def _leer_numero_con_desplazamiento(fila, col):
    """Lee un numero en 'col'; si esta vacio prueba la columna siguiente
    (la plantilla desplaza los datos una columna respecto a la cabecera)."""
    if col is None:
        return None
    valor = _numero_decimal(fila[col].value)
    if valor is None and col + 1 < len(fila):
        valor = _numero_decimal(fila[col + 1].value)
    return valor


def _detectar_columnas_lns(ws, col_tipo, col_l, col_n, col_s):
    """Localiza las columnas reales de L, N, S usando la primera fila de datos.

    La plantilla agrupa 'Coeficientes L, N, S' en una celda fusionada y los
    datos aparecen desplazados una columna a la derecha de las cabeceras.
    Se comprueba ese desplazamiento y, si no cuadra, las cabeceras mismas.
    """
    if col_l is None or col_n is None or col_s is None:
        return None
    for fila in ws.iter_rows(min_row=1):
        if _texto_limpio(fila[col_tipo].value) is not None:
            for desplazamiento in (1, 0):
                c_l = col_l + desplazamiento
                c_n = col_n + desplazamiento
                c_s = col_s + desplazamiento
                if c_s < len(fila):
                    v_l = _numero_decimal(fila[c_l].value)
                    v_n = _numero_decimal(fila[c_n].value)
                    if v_l is not None and v_n is not None:
                        return c_l, c_n, c_s
            break
    return None


def extraer_apoyos(archivo_excel):
    """Devuelve la lista de apoyos con los datos basicos para los graficos."""
    if not os.path.exists(archivo_excel):
        raise FileNotFoundError("No existe el Excel: %s" % archivo_excel)

    zonas_por_tramo = extraer_zonas_por_tramo(archivo_excel)

    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Cálculo de apoyos"]
    col_tipo = _localizar_columna(ws, [r"^tipo$"])
    col_angulo = _localizar_columna(ws, [r"^valor.*angulo"])
    col_coef = _localizar_columna(ws, [r"^coef.*segur"])
    # Cabeceras L, N, S (fila 2 de la plantilla: "Semi suma vanos L", ...)
    col_l = _localizar_columna(ws, [r"semi suma"], fila_cabecera=2)
    col_n = _localizar_columna(ws, [r"diferen.*tang"], fila_cabecera=2)
    col_s = _localizar_columna(ws, [r"coef.*angulo"], fila_cabecera=2)
    if col_tipo is None:
        raise ValueError("No se encontro la columna 'Tipo' en 'Cálculo de apoyos'.")

    # Columnas reales de L/N/S (pueden estar desplazadas de las cabeceras)
    lns = _detectar_columnas_lns(ws, col_tipo, col_l, col_n, col_s)
    if lns is not None:
        col_l, col_n, col_s = lns

    apoyos = []
    for fila in ws.iter_rows(min_row=1):
        tipo_texto = _texto_limpio(fila[col_tipo].value)
        if not tipo_texto:
            continue
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        tipo_clave = mapear_tipo_a_clave(tipo_texto)
        # L/N/S pueden estar desplazados una columna respecto a la cabecera
        # (la plantilla agrupa 'Coeficientes L, N, S' en una celda fusionada).
        l = _leer_numero_con_desplazamiento(fila, col_l)
        n = _leer_numero_con_desplazamiento(fila, col_n)
        s = _leer_numero_con_desplazamiento(fila, col_s)

        apoyo = {
            "numero": int(numero),
            "tipo_texto": tipo_texto,
            "tipo_clave": tipo_clave,
            "angulo_sexagesimal": (_numero_decimal(fila[col_angulo].value)
                                   if col_angulo is not None else None),
            "coef_seguridad": (_texto_limpio(fila[col_coef].value)
                               if col_coef is not None else None),
            "zona": zona_de_apoyo(int(numero), zonas_por_tramo),
            "L": l, "N": n, "S": s,
        }
        # Clave de zona lista para graficos_utilizacion_ecuaciones.py
        # (la categoria se deduce de 'coef_seguridad': N -> no especial)
        apoyo["zona_clave"] = zona_a_clave(apoyo["zona"], apoyo["coef_seguridad"])
        apoyos.append(apoyo)
    return apoyos


def d1_de_armado(familia_armado):
    """Ancho entre montantes (d1) segun la familia de armado del catalogo Blender."""
    familia = str(familia_armado).upper()
    if familia in D1_POR_FAMILIA:
        return D1_POR_FAMILIA[familia]
    # Normalizacion basica (p.ej. 'Serie C' -> 'C')
    for clave in D1_POR_FAMILIA:
        if clave in familia:
            return D1_POR_FAMILIA[clave]
    return None


def zona_a_clave(zona, categoria=None):
    """Traduce la zona (A/B/C) + categoria de la linea a la clave de zona de
    graficos_utilizacion_ecuaciones.py:
        zona A             -> "A"
        zona B/C no espe.  -> "BC_no_especial"
        zona B/C especial  -> "BC_especial"
    La categoria se indica con 'no_especial'/'especial' (o 'N'/'S' segun la
    plantilla del Excel). Por defecto se asume no especial.
    """
    if zona is None:
        return None
    z = str(zona).upper()
    if z == "A":
        return "A"
    if z in ("B", "C"):
        if categoria is not None:
            c = _clave_texto(categoria)
            if c and ("s" == c or c.startswith("si") or "especial" in c
                      and "no" not in c[:3]):
                return "BC_especial"
        return "BC_no_especial"
    return None


def n_cadenas(tipo_clave, coef_seguridad):
    """NCAD (cadenas por fase) segun la tabla guia: tipo de apoyo x seguridad.
    coef_seguridad: 'N' (normal) o 'R' (reforzada), como viene en el Excel
    (columna 'Coefici. de seguri.')."""
    if tipo_clave is None:
        return None
    reg = NCAD_TABLA.get(tipo_clave)
    if reg is None:
        return None
    clave = _clave_texto(coef_seguridad) if coef_seguridad is not None else ""
    if clave in ("r", "reforzada") or clave.startswith("ref"):
        return reg["R"]
    return reg["N"]


def leer_montaje_por_apoyo(archivo_excel):
    """Tipo de montaje (Tresbolillo, Doble circuito, ...) de la pestaña
    'Apoyos y crucetas', columna 'Armado base'. Devuelve {apoyo_numero: montaje}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Apoyos y crucetas"]
    col_montaje = _localizar_columna(ws, [r"armado.*base"], fila_cabecera=2)
    if col_montaje is None:
        raise ValueError("No se encontro la columna 'Armado base' en 'Apoyos y crucetas'.")
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        montaje = _texto_limpio(fila[col_montaje].value)
        if montaje:
            resultado[int(numero)] = montaje
    return resultado


def buscar_cadena_por_apoyo(archivo_cuadros):
    """Lee el .docx 'Cuadro n 10 - Calculo de cadenas de aisladores' y devuelve
    {apoyo_numero: nombre_cadena}."""
    import docx
    documento = docx.Document(archivo_cuadros)
    cadenas = {}
    for tabla in documento.tables:
        for fila in tabla.rows:
            celdas = [c.text.strip() for c in fila.cells]
            if len(celdas) >= 3:
                numero = _numero_decimal(celdas[0])
                if numero is not None and celdas[2]:
                    cadenas[int(numero)] = celdas[2]
    return cadenas


def buscar_archivo_cuadros(carpeta=None, nombre_clave=None):
    """Localiza automaticamente un docx de 'cuadros' de la linea.

    nombre_clave: subcadena a buscar en el nombre (p.ej. 'cadena' para el
    cuadro 10 de cadenas, '14' para el cuadro 14 de tensiones)."""
    if carpeta is None:
        carpeta = os.path.dirname(os.path.abspath(__file__))
    if nombre_clave is None:
        # Por defecto busca el de cadenas de aisladores
        for nombre in sorted(os.listdir(carpeta)):
            if (nombre.lower().endswith(".docx")
                    and "cadena" in nombre.lower()):
                return os.path.join(carpeta, nombre)
        return None
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.lower().endswith(".docx") and nombre_clave in nombre:
            return os.path.join(carpeta, nombre)
    return None


def leer_tension_linea(archivo_cuadros=None):
    """Tension de la linea [kV] del cuadro 14 de los 'cuadros' docx
    (columna 'tension de la linea kv'). Devuelve None si no se encuentra.
    Solo se escanea el docx del cuadro 14 (nombre con '14'), no otros."""
    if archivo_cuadros is None or "14" not in os.path.basename(archivo_cuadros):
        archivo_cuadros = buscar_archivo_cuadros(nombre_clave="14")
    if archivo_cuadros is None or not os.path.exists(archivo_cuadros):
        return None
    import docx
    documento = docx.Document(archivo_cuadros)
    for tabla in documento.tables:
        for fila in tabla.rows:
            celdas = [c.text.strip() for c in fila.cells]
            texto_fila = " ".join(celdas).lower()
            if "kv" not in texto_fila and "tension" not in texto_fila:
                continue
            for celda in celdas:
                valor = _numero_decimal(celda)
                if valor is not None:
                    return valor
    return None


def leer_cadena_catalogo(nombre_cadena, ruta_catalogo=None):
    """Devuelve las caracteristicas de una cadena del catalogo
    catalogo_cadenas_completo.json (PCADF, EVCADF120/140/60, longitud, ...)."""
    if ruta_catalogo is None:
        ruta_catalogo = RUTA_CATALOGO_CADENAS
    if not os.path.exists(ruta_catalogo):
        raise FileNotFoundError("Catalogo de cadenas no encontrado: %s" % ruta_catalogo)
    with open(ruta_catalogo, encoding="utf-8") as archivo:
        catalogo = json.load(archivo)
    clave_buscada = _clave_conductor(nombre_cadena)
    for cadena in catalogo.get("cadenas", []):
        if _clave_conductor(cadena["nombre"]) == clave_buscada:
            return dict(cadena["caracteristicas"],
                        nombre=cadena["nombre"], conductor=cadena.get("conductor"),
                        tension_kv=cadena.get("tension_kv"))
    return None


def leer_separacion_fases_por_apoyo(archivo_excel):
    """D = separacion normalizada entre fases [m] de la pestaña 'Elección apoyos',
    columna 'Separ. fases norma. m'. Devuelve {apoyo_numero: D}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Elección apoyos"]
    col_d = _localizar_columna(ws, [r"separ.*fases.*norma"])
    if col_d is None:
        raise ValueError("No se encontro 'Separ. fases norma.' en 'Elección apoyos'.")
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        d = _numero_decimal(fila[col_d].value)
        if d is not None:
            resultado[int(numero)] = d
    return resultado


def leer_href_por_apoyo(archivo_excel):
    """HREF = 'Altura de refere. m' de la pestaña 'Elección apoyos' [m].
    Es la altura de referencia del apoyo (la del catalogo). Devuelve
    {apoyo_numero: href_m}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Elección apoyos"]
    col = _localizar_columna(ws, [r"altura.*refere"])
    if col is None:
        raise ValueError("No se encontro 'Altura de refere.' en 'Elección apoyos'.")
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        href = _numero_decimal(fila[col].value)
        if href is not None:
            resultado[int(numero)] = href
    return resultado


def leer_separacion_conductores_por_apoyo(archivo_excel):
    """Separacion entre conductores [m] usada en la formula de h. Segun el
    criterio de Paloma se toma de la pestaña 'Elección apoyos', columna
    'Separ. fases norma. m' (la separacion normalizada entre fases, la misma
    que se usa como D en el vano maximo). Devuelve {apoyo_numero: valor}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Elección apoyos"]
    col = _localizar_columna(ws, [r"separ.*fases.*norma"])
    if col is None:
        raise ValueError("No se encontro 'Separ. fases norma.' en 'Elección apoyos'.")
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        sep = _numero_decimal(fila[col].value)
        if sep is not None:
            resultado[int(numero)] = sep
    return resultado


def calcular_h_segun_tipo(tipo_clave, href, sep_conductores, lcad=None):
    """h (y h') de la ecuacion resistente segun el tipo de apoyo:

        Suspension:     h = HREF + Sep.conductores - LCAD - solera
        Amarre/anclaje: h = HREF + Sep.conductores - solera

    solera = SOLERA_M (0.2 m). Devuelve None si falta algun dato esencial.
    """
    if tipo_clave is None or href is None or sep_conductores is None:
        return None
    if tipo_clave in TIPOS_SUSPENSION:
        if lcad is None:
            return None
        return href + sep_conductores - lcad - SOLERA_M
    return href + sep_conductores - SOLERA_M


def leer_tensiones_por_tramo(archivo_excel):
    """Tensiones del conductor por hipotesis de la pestaña 'T. reg. cond. fase':
      TVF   (T.máxima viento)        THF  (T.máxima hielo)
      TVHF  (T.máxima hielo+viento)  TVM  (T.Viento 1/2 a 120 km/h)
      T15V  (15°C+V a 120 km/h)      T0H  (0°C+H)
      TTemp (50°C)
    Devuelve {(apoyo_a, apoyo_b): {clave: tension_daN}}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["T. reg. cond. fase"]
    col_tramo = _localizar_columna(ws, [r"^tramo$"])
    if col_tramo is None:
        raise ValueError("No se encontro la columna 'Tramo' en T. reg. cond. fase.")

    cabeceras = {}
    for c in ws[2]:
        clave = _clave_texto(c.value)
        if not clave:
            continue
        col = c.column - 1
        if "maxima" in clave and "hielo" in clave and "viento" in clave:
            cabeceras["TVHF"] = col
        elif "maxima" in clave and "viento" in clave:
            cabeceras["TVF"] = col
        elif "maxima" in clave and "hielo" in clave:
            cabeceras["THF"] = col
        elif "viento" in clave and "1 2" in clave:
            cabeceras["TVM"] = col
        elif clave.startswith("15oc") or ("15oc" in clave and "v" in clave):
            cabeceras["T15V"] = col
        elif "0oc" in clave and "h" in clave:
            cabeceras["T0H"] = col
        elif clave.startswith("50oc"):
            cabeceras["TTemp"] = col

    tensiones = {}
    for fila in ws.iter_rows(min_row=1):
        tramo = _texto_limpio(fila[col_tramo].value)
        nums = re.findall(r"\d+", tramo) if tramo else []
        if len(nums) < 2:
            continue
        clave_tramo = tuple(int(n) for n in nums)
        tensiones[clave_tramo] = {k: _numero_decimal(fila[col].value)
                                  for k, col in cabeceras.items()}
    return tensiones


def tensiones_para_apoyo(numero_apoyo, tensiones_por_tramo):
    """Tensiones de un apoyo: el MAXIMO de las tensiones de sus tramos
    adyacentes (criterio conservador). Se puede ajustar si se prefiere
    el tramo del vano de regulacion correspondiente."""
    resultado = {}
    for (a, b), tens in tensiones_por_tramo.items():
        if numero_apoyo in (a, b):
            for k, v in tens.items():
                if v is not None and (k not in resultado or v > resultado[k]):
                    resultado[k] = v
    return resultado


def leer_angulo_desviacion_max(archivo_excel):
    """Angulo maximo de desviacion de la cadena (gammamax) [grados] de la
    pestaña 'Distancias a masa', columna 'Áng. desv. cad. máx. °'.
    Solo aplica a apoyos de suspension. Devuelve {apoyo_numero: grados}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Distancias a masa"]
    col = _localizar_columna(ws, [r"desv.*cad.*max"], fila_cabecera=2)
    if col is None:
        return {}
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        angulo = _numero_decimal(fila[col].value)
        if angulo is not None:
            resultado[int(numero)] = angulo
    return resultado


def leer_altura_conductor_real(archivo_excel):
    """h = altura del punto de aplicacion de esfuerzos [m] desde la pestaña
    'Cálculo de apoyos', columna 'Altura conduc. real m' (equivale a 'Altura
    libre real m' de 'Elección apoyos'). Devuelve {apoyo_numero: h}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Cálculo de apoyos"]
    col = _localizar_columna(ws, [r"altura.*conduc.*real"])
    if col is None:
        return {}
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        h = _numero_decimal(fila[col].value)
        if h is not None:
            resultado[int(numero)] = h
    return resultado


def leer_altura_cdg_armado(archivo_excel):
    """h = altura desde el suelo hasta el cdg del armado [m] de 'Cimen.
    monobloque'. Bajo el encabezado fusionado 'Altura sobre terreno' (D2:E2),
    la 2a subcolumna (E) es la altura del punto de aplicacion de los esfuerzos
    (cdg de los conductores/armado): 'Altura conduc. real' + separacion de
    crucetas. Devuelve {apoyo_numero: h}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Cimen. monobloque"]
    col_total = _localizar_columna(ws, [r"altura sobre terreno"], fila_cabecera=2)
    if col_total is None:
        return {}
    col_cdg = col_total + 1   # subcolumna E bajo el merge D2:E2
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        if col_cdg < len(fila):
            h = _numero_decimal(fila[col_cdg].value)
            if h is not None:
                resultado[int(numero)] = h
    return resultado


def leer_esfuerzo_util(archivo_excel):
    """Fu = esfuerzo util del apoyo [daN] de 'Cimen. monobloque',
    columna 'Esfuerzo útil daN'. Devuelve {apoyo_numero: Fu_daN}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Cimen. monobloque"]
    col = _localizar_columna(ws, [r"esfuerzo.*util"], fila_cabecera=2)
    if col is None:
        return {}
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        fu = _numero_decimal(fila[col].value)
        if fu is not None:
            resultado[int(numero)] = fu
    return resultado


def leer_d1_por_apoyo(archivo_excel):
    """d1 (ancho entre montantes en el punto de fallo) [m] por apoyo, desde
    'Apoyos y crucetas' col 'Referencia del apoyo' (familia del armado) y el
    catalogo de Blender (C/M50/M60=0.510, G=0.908, ...)."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Apoyos y crucetas"]
    col_ref = _localizar_columna(ws, [r"referencia.*apoyo"], fila_cabecera=2)
    if col_ref is None:
        return {}
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        numero = _numero_decimal(fila[0].value)
        if numero is None:
            continue
        ref = _texto_limpio(fila[col_ref].value)
        if ref:
            d1 = d1_de_armado(ref)
            if d1 is not None:
                resultado[int(numero)] = d1
    return resultado


def viento_segun_categoria(categoria=None):
    """Velocidad de viento de la hipotesis reglamentaria segun la categoria:
        categoria especial -> 140 km/h
        resto              -> 120 km/h

    La categoria de la linea NO viene etiquetada en el Excel. Por defecto se
    asume no especial (120 km/h). Cuando se conozca la categoria, se pasa como
    'especial'/'s' para que devuelva 140.
    """
    if categoria is not None:
        clave = _clave_texto(categoria)
        if clave in ("s", "si", "especial") or clave.startswith("especial"):
            return 140.0
    return 120.0


def datos_completos_para_graficos(archivo_excel, viento_kmh=None, ruta_catalogo=None,
                                  archivo_cuadros=None, cadenas_por_apoyo=None):
    """Ensambla TODO lo que necesitan los graficos de utilizacion para la linea.

    Es GENERAL: lee cualquier Excel de la plantilla.
      1. Conductor (diametro, peso)   -> Mediciones + catalogo de conductores
      2. Apoyos (tipo, zona, L, N, S) -> Cálculo de apoyos + T. reg. cond. fase
      3. Montaje (Tresbolillo, ...)    -> 'Apoyos y crucetas', col. Armado base
      4. Cadena de aisladores          -> .docx cuadro 10 + catalogo de cadenas
      5. NCAD (cadenas por fase)       -> tabla guia tipo x seguridad (N/R)
      6. Sobrecargas (Sv, Sh, S_vh...) -> sobrecargas.calcular_sobrecargas

    El viento de la hipotesis (120 o 140 km/h) depende de la categoria de la
    linea (especial -> 140, no especial -> 120). Como la categoria no esta en
    el Excel, por defecto se usa 120 km/h; se puede forzar con 'viento_kmh'.
    """
    from sobrecargas import calcular_sobrecargas
    from reglamento import (dpp_segun_tension, categoria_segun_tension,
                            k_prima_segun_categoria, k_segun_angulo,
                            angulo_oscilacion, viento_kmh_segun_tension)
    from apoyos_unesa import (fu_para_apoyo, fu_por_hipotesis_para_apoyo,
                              cargar_catalogo as cargar_catalogo_unesa)
    catalogo_unesa = cargar_catalogo_unesa()

    conductor = leer_conductor(archivo_excel, ruta_catalogo)
    apoyos = extraer_apoyos(archivo_excel)
    montajes = leer_montaje_por_apoyo(archivo_excel)
    separaciones = leer_separacion_fases_por_apoyo(archivo_excel)
    tensiones_por_tramo = leer_tensiones_por_tramo(archivo_excel)
    angulos_cadena = leer_angulo_desviacion_max(archivo_excel)
    hrefs = leer_href_por_apoyo(archivo_excel)
    # La separacion de conductores de la formula de h es la 'Separ. fases
    # norma.' de 'Elección apoyos' (la misma columna que ya se lee como D).
    seps_conductores = separaciones
    esfuerzos_util = leer_esfuerzo_util(archivo_excel)
    d1s = leer_d1_por_apoyo(archivo_excel)

    if cadenas_por_apoyo is None:
        if archivo_cuadros is None:
            archivo_cuadros = buscar_archivo_cuadros()
        cadenas_por_apoyo = (buscar_cadena_por_apoyo(archivo_cuadros)
                             if archivo_cuadros else {})

    for a in apoyos:
        a["montaje"] = montajes.get(a["numero"])
        a["D_m"] = separaciones.get(a["numero"])
        a["n_cadenas"] = n_cadenas(a["tipo_clave"], a["coef_seguridad"])
        nombre_cadena = cadenas_por_apoyo.get(a["numero"])
        a["cadena"] = nombre_cadena
        a["cadena_caracteristicas"] = (
            leer_cadena_catalogo(nombre_cadena) if nombre_cadena else None)
        a["tensiones_daN"] = tensiones_para_apoyo(
            a["numero"], tensiones_por_tramo)
        a["gammamax_grados"] = angulos_cadena.get(a["numero"])
        a["href_m"] = hrefs.get(a["numero"])
        a["sep_conductores_m"] = seps_conductores.get(a["numero"])
        cc = a.get("cadena_caracteristicas") or {}
        a["lcad_m"] = cc.get("longitud_m")
        a["h_m"] = calcular_h_segun_tipo(
            a["tipo_clave"], a["href_m"], a["sep_conductores_m"], a["lcad_m"])
        a["h_prima_m"] = a["h_m"]   # en el Tema 10 h = h'
        a["Fu_daN"] = fu_para_apoyo(
            a["numero"], a["tipo_clave"], archivo_excel, catalogo_unesa)
        a["Fu_por_hipotesis_daN"] = fu_por_hipotesis_para_apoyo(
            a["numero"], a["tipo_clave"], archivo_excel, catalogo_unesa) or {}
        a["Fu_cimen_daN"] = esfuerzos_util.get(a["numero"])  # referencia
        a["d1_m"] = d1s.get(a["numero"])

    # --- Tension de la linea: cuadro 14 de 'cuadros' (respaldo: cadena) ---
    tension_linea_kv = leer_tension_linea()
    if tension_linea_kv is None:
        for a in apoyos:
            cc = a["cadena_caracteristicas"]
            if cc and cc.get("tension_kv"):
                tension_linea_kv = cc["tension_kv"]
                break
    categoria = (categoria_segun_tension(tension_linea_kv)
                 if tension_linea_kv else None)
    if viento_kmh is None:
        viento_kmh = (viento_kmh_segun_tension(tension_linea_kv)
                      if tension_linea_kv else viento_segun_categoria())

    # --- Sobrecargas por zona ---
    zonas_presentes = sorted({a["zona"] for a in apoyos if a["zona"]})
    sobrecargas_por_zona = {}
    for zona in zonas_presentes:
        sobrecargas_por_zona[zona] = calcular_sobrecargas(
            conductor["diametro_mm"], conductor["peso_kg_m"],
            zona, viento_kmh=viento_kmh)

    # --- Vano maximo: DPP, K' y K (Tabla 16) por apoyo ---
    for a in apoyos:
        a["tension_linea_kv"] = tension_linea_kv
        a["categoria"] = categoria
        if tension_linea_kv is not None:
            a["DPP_m"] = dpp_segun_tension(tension_linea_kv)
            a["K_prima"] = k_prima_segun_categoria(categoria)
        else:
            a["DPP_m"] = None
            a["K_prima"] = None
        sob = sobrecargas_por_zona.get(a["zona"])
        if sob is not None:
            gamma = angulo_oscilacion(a["zona"], sob["P_v_max"],
                                      conductor["diametro_m"], sob["P_daN"],
                                      sob["Sh"])
            a["gamma_oscilacion_grados"] = gamma
            a["K_vano_maximo"] = (k_segun_angulo(gamma, tension_linea_kv)
                                  if tension_linea_kv is not None else None)
        else:
            a["gamma_oscilacion_grados"] = None
            a["K_vano_maximo"] = None

    return {
        "archivo_excel": os.path.abspath(archivo_excel),
        "archivo_cuadros": (os.path.abspath(archivo_cuadros)
                            if archivo_cuadros else None),
        "tension_linea_kv": tension_linea_kv,
        "categoria": categoria,
        "viento_kmh": viento_kmh,
        "conductor": conductor,
        "zonas_de_tendido_m": leer_zonas_tendido(archivo_excel),
        "zona_predominante": zona_de_tendido_principal(archivo_excel),
        "sobrecargas_por_zona": sobrecargas_por_zona,
        "apoyos": apoyos,
    }


if __name__ == "__main__":
    RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "line_example.xlsx")
    print("== DATOS COMPLETOS PARA GRAFICOS DE UTILIZACION ==")
    print("Viento hipotesis: especial->140 km/h, no especial->120 km/h.")
    print("(la categoria no esta en el Excel: por defecto 120 km/h)\n")

    datos = datos_completos_para_graficos(RUTA)

    print("LINEA:")
    print("  Tension: %s kV | Categoria: %s | Viento hipotesis: %s km/h"
          % (datos["tension_linea_kv"], datos["categoria"], datos["viento_kmh"]))

    c = datos["conductor"]
    print("\nCONDUCTOR (leido de Mediciones -> catalogo):")
    print("  %s (%s)  d=%.2f mm  peso=%.4f kg/m  (%.1f kg/km)"
          % (c["nomenclatura_excel"], c["designacion"], c["diametro_mm"],
             c["peso_kg_m"], c["masa_kg_km"]))

    print("\nZONAS DE TENDIDO (Mediciones):", datos["zonas_de_tendido_m"])

    print("\nSOBRECARGAS por zona (conductor + zona + viento %g km/h):"
          % datos["viento_kmh"])
    for zona, r in sorted(datos["sobrecargas_por_zona"].items()):
        print("  zona %s: Sv=%.4f Sv120=%.4f Sh=%.4f S_vm=%.4f S_vh=%.4f dmh=%.4f m"
              % (zona, r["Sv"], r["Sv120"], r["Sh"], r["S_vm"], r["S_vh"],
                 r["dmh_m"]))

    print("\nAPOYOS:")
    for a in datos["apoyos"]:
        cad = a["cadena_caracteristicas"]
        t = a["tensiones_daN"]
        print("  #%d %-12s -> %-24s zona=%s(%s) L=%s N=%s S=%s | %s | NCAD=%s | D=%.2f m"
              % (a["numero"], a["tipo_texto"], a["tipo_clave"], a["zona"],
                 a["zona_clave"], a["L"], a["N"], a["S"],
                 a.get("montaje"), a.get("n_cadenas"), a.get("D_m") or 0))
        print("      tensiones: TVF=%s THF=%s TVHF=%s TVM=%s T0H=%s TTemp=%s daN  gammamax=%s"
              % (t.get("TVF"), t.get("THF"), t.get("TVHF"),
                 t.get("TVM"), t.get("T0H"), t.get("TTemp"),
                 a.get("gammamax_grados")))
        print("      vano max: DPP=%s m  K'=%s  K=%s  gamma_osc=%s  h=h'=%s m  Fu=%s daN"
              % (a.get("DPP_m"), a.get("K_prima"), a.get("K_vano_maximo"),
                 a.get("gamma_oscilacion_grados"), a.get("h_m"), a.get("Fu_daN")))
        if cad:
            print("      cadena: %s  PCADF=%.2f daN  EVCADF120=%.3f  EVCADF140=%.3f"
                  "  EVCADF60=%.3f  L=%.3f m"
                  % (a["cadena"], cad["peso_daN"], cad["esfuerzo_viento_120_daN"],
                     cad["esfuerzo_viento_140_daN"], cad["esfuerzo_viento_60_daN"],
                     cad["longitud_m"]))

    print("\nCATALOGO d1 por familia (Blender):")
    for fam, d1 in sorted(D1_POR_FAMILIA.items()):
        print("  %-16s d1 = %.3f m" % (fam, d1))
