# -*- coding: utf-8 -*-
"""
cambiar_tipo_apoyo.py
=====================
Cambia el TIPO DE APOYO (gama + montaje + detalle) de un apoyo:

  GAMA    : SERIE_C, ANDEL_M60, ANDEL_M50, SERIE_G
  MONTAJE : TRESBOLILLO, BANDERA, BOVEDA_CAPA, BOVEDA_PICO,
            BOVEDA_TRIANGULO, HORIZONTAL (y DOBLE_CIRCUITO si 6 fases)
  DETALLE : la semicruceta / boveda concreta (longitud, atirantada...)

El catalogo del asistente se construye SOLO con los modelos que tienen FBX
exportado a Unity (Assets/Resources/ModelosCruceta) y que superan la
comprobacion de compatibilidad de Unity (MontarCrucetasAndel). Asi no se
ofrece ninguna opcion que luego falle en la escena.

Cuando se cambia el tipo de apoyo:
  1. Excel 'Apoyos y crucetas': referencia del apoyo (gama), Armado base
     (montaje), Longitud crucetas, Referencia armado, Separacion crucetas,
     Referencia cruceta y Cruceta tipo.
  2. apoyos_configurados.json: catalogo_id, armado (si cambia la gama),
     montaje, cruceta y configuracion_id.
  3. Unity reconstruye la escena con el nuevo montaje.

CLI:
  py cambiar_tipo_apoyo.py --catalogo
  py cambiar_tipo_apoyo.py --peticion p.json --resultado r.json
"""
import ast
import os
import re
import json

import openpyxl

from twinelec_paths import assets_dir, blender_scripts_dir, unity_model_dir

from datos_apoyos_excel import (
    _clave_texto,
    _localizar_columna,
    _numero_decimal,
    _texto_limpio,
)


# ---------------------------------------------------------------------------
# Gamas y montajes (textos EXCEL compatibles con principal._normalizar_montaje)
# ---------------------------------------------------------------------------
GAMAS = {
    "SERIE_C": {
        "nombre": "Serie C (Andel)",
        "catalogo_id": "CATALOGO_SERIE_C",
        "familia": "C",
        "referencia_apoyo": "Andel Serie C C-2000",
        "cabeza_m": 4.2, "modulo_m": 0.6,
        "recurso_cabeza": "ModelosArmado/Cabeza_C",
        "primer_patron": "B",
    },
    "ANDEL_M60": {
        "nombre": "Andel M60",
        "catalogo_id": "CATALOGO_ANDEL",
        "familia": "M60",
        "referencia_apoyo": "Andel M60 C-2000",
        "cabeza_m": 4.0, "modulo_m": 0.4,
        "recurso_cabeza": "ModelosArmado/Cabeza_M60",
        "primer_patron": "A",
    },
    "ANDEL_M50": {
        "nombre": "Andel M50",
        "catalogo_id": "CATALOGO_ANDEL",
        "familia": "M50",
        "referencia_apoyo": "Andel M50 C-2000",
        "cabeza_m": 4.0, "modulo_m": 0.4,
        "recurso_cabeza": "ModelosArmado/Cabeza_M50",
        "primer_patron": "B",
    },
    "SERIE_G": {
        "nombre": "Serie G (Andel)",
        "catalogo_id": "CATALOGO_ANDEL",
        "familia": "G",
        "referencia_apoyo": "Andel Serie G C-2000",
        "cabeza_m": 5.6, "modulo_m": 0.7,
        "recurso_cabeza": "ModelosArmado/Cabeza_G",
        "primer_patron": "A",
    },
}

MONTAJES = {
    "TRESBOLILLO": {
        "nombre": "Tresbolillo", "niveles": 3, "d_m": 1.8,
        "texto_excel": "Tresbolillo", "referencia_armado": "TB-18",
        "texto_eleccion": "Tres.",
    },
    "BANDERA": {
        "nombre": "Bandera", "niveles": 3, "d_m": 1.8,
        "texto_excel": "Bandera", "referencia_armado": "BA-18",
        "texto_eleccion": "Band.",
    },
    "BOVEDA_CAPA": {
        "nombre": "Bóveda en capa", "niveles": 1, "d_m": None,
        "texto_excel": "Bóveda en capa", "referencia_armado": "BV-CAPA",
        "texto_eleccion": "Bóv. capa",
    },
    "BOVEDA_PICO": {
        "nombre": "Bóveda en pico", "niveles": 1, "d_m": None,
        "texto_excel": "Bóveda en pico", "referencia_armado": "BV-PICO",
        "texto_eleccion": "Bóv. pico",
    },
    "BOVEDA_TRIANGULO": {
        "nombre": "Bóveda triángulo", "niveles": 1, "d_m": None,
        "texto_excel": "Bóveda triángulo", "referencia_armado": "BV-TRI",
        "texto_eleccion": "Bóv. triáng.",
    },
    "HORIZONTAL": {
        "nombre": "Horizontal", "niveles": 1, "d_m": None,
        "texto_excel": "Horizontal", "referencia_armado": "HOR-1",
        "texto_eleccion": "Horizontal",
    },
    "DOBLE_CIRCUITO": {
        "nombre": "Doble circuito", "niveles": 3, "d_m": 1.8,
        "texto_excel": "Doble circuito", "referencia_armado": "DC-18",
        "texto_eleccion": "Doble circ.",
    },
}

# Montajes que exigen 6 fases (linea de doble circuito)
MONTAJES_6_FASES = {"DOBLE_CIRCUITO"}


# ---------------------------------------------------------------------------
# Tablas del catalogo 3D (leidas de Blender) y FBX disponibles en Unity
# ---------------------------------------------------------------------------
def _cargar_tablas_catalogo():
    ruta_script = str(blender_scripts_dir() / "crear_semicrucetas_andel.py")
    with open(ruta_script, "r", encoding="utf-8-sig") as f:
        arbol = ast.parse(f.read(), filename=ruta_script)
    nombres = {
        "SEMICRUCETAS_ASC", "CRUCETAS_ARCX", "CRUCETAS_AMC",
        "SEMICRUCETAS_ATIRANTADAS", "SERIE_C_SEMICRUCETAS",
        "SERIE_C_CRUCETAS_RECTAS", "SERIE_C_ATIRANTADAS",
        "SERIE_C_BOVEDAS_TRIANGULO", "SERIE_C_BOVEDAS_CAPA",
        "SERIE_C_BOVEDAS_PICO", "BOVEDAS_CAPA", "BOVEDAS_PICO",
        "BOVEDAS_TRIANGULO",
    }
    tablas = {}
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign) or len(nodo.targets) != 1:
            continue
        destino = nodo.targets[0]
        if isinstance(destino, ast.Name) and destino.id in nombres:
            tablas[destino.id] = ast.literal_eval(nodo.value)
    return tablas


def _fbx_crucetas_disponibles(carpeta_assets=None):
    """Conjunto de nombres de modelo (sin '.fbx') en ModelosCruceta."""
    if carpeta_assets is None:
        carpeta_assets = str(unity_model_dir())
    if not os.path.isdir(carpeta_assets):
        return set()
    return {f[:-4] for f in os.listdir(carpeta_assets)
            if f.lower().endswith(".fbx")}


def _a_de(valor):
    """Semilongitud 'a' de una referencia: el primer numero de su tupla."""
    if isinstance(valor, (tuple, list)):
        return float(valor[0])
    return float(valor)


def _total_de(valor):
    """Longitud total si la tabla la lleva (2o elemento de la tupla)."""
    if isinstance(valor, (tuple, list)) and len(valor) >= 2:
        return float(valor[1])
    return None


# ---------------------------------------------------------------------------
# Compatibilidad con Unity MontarCrucetasAndel (incluye prefijos C_ de la
# Serie C, que el codigo de Unity ahora acepta tambien)
# ---------------------------------------------------------------------------
def _compatible_unity(tipo_montaje, es_atirantada, modelo):
    if es_atirantada and tipo_montaje in ("TRESBOLILLO", "BANDERA",
                                          "DOBLE_CIRCUITO"):
        return modelo.startswith("ATC") or modelo.startswith("C_ATC-")
    if tipo_montaje == "PASO_HERRAJE_PUENTE":
        return modelo.startswith("ATC")
    if (not es_atirantada) and tipo_montaje in ("TRESBOLILLO", "BANDERA"):
        return modelo.startswith("ASC-") or modelo.startswith("C_ASC-")
    if (not es_atirantada) and tipo_montaje in ("DOBLE_CIRCUITO", "HORIZONTAL"):
        return modelo.startswith("ARCX-") or modelo.startswith("C_ARC-")
    if tipo_montaje == "PASO_LATERAL":
        return modelo.startswith("AMCX-")
    if tipo_montaje == "TRIANGULO_TG":
        return modelo.startswith("TG")
    if tipo_montaje == "BOVEDA_CAPA":
        return modelo.startswith("BH") or modelo.startswith("C_BH")
    if tipo_montaje == "BOVEDA_PICO":
        return modelo.startswith("BF") or modelo.startswith("C_BF")
    if tipo_montaje == "BOVEDA_TRIANGULO":
        return modelo.startswith("BT") or modelo.startswith("C_BT")
    return False


def _modelo_con_fbx(modelo, familia, fbx):
    """True si Unity puede cargar el modelo (FBX directo o variante _H)."""
    if modelo in fbx:
        return True
    if any(nombre.startswith(modelo + "_H") for nombre in fbx):
        return familia in ("M50", "M60")
    return False


# ---------------------------------------------------------------------------
# Catalogo del asistente (gama -> montajes -> detalles), filtrado
# ---------------------------------------------------------------------------
def _etiqueta_detalle(montaje, tipo, a_m, total_m, es_atirantada):
    texto_total = ("%.2f" % total_m) if total_m else ("%.2f" % a_m)
    if montaje in ("TRESBOLILLO", "BANDERA"):
        if es_atirantada:
            return "%s · %.2f m · ATIRANTADA" % (tipo, a_m)
        return "%s · %.2f m · PLANA" % (tipo, a_m)
    if montaje == "BOVEDA_CAPA":
        return "%s · capa %s m" % (tipo, texto_total)
    if montaje == "BOVEDA_PICO":
        return "%s · pico %s m" % (tipo, texto_total)
    if montaje == "BOVEDA_TRIANGULO":
        return "%s · triángulo %s m" % (tipo, texto_total)
    if montaje == "HORIZONTAL":
        return "%s · recta %s m" % (tipo, texto_total)
    return tipo


def _detalles_semicrucetas(tablas, fbx, gama, montaje):
    """Detalles ASC/ATC validos para TRESBOLILLO y BANDERA."""
    pref = "C_" if gama == "SERIE_C" else ""
    familia = GAMAS[gama]["familia"]
    if pref == "C_":
        planas = sorted(tablas.get("SERIE_C_SEMICRUCETAS", {}).items())
        atir = sorted(tablas.get("SERIE_C_ATIRANTADAS", {}).items())
    else:
        planas = sorted(tablas.get("SEMICRUCETAS_ASC", {}).items())
        atir = sorted(tablas.get("SEMICRUCETAS_ATIRANTADAS", {}).items())
    detalles = []
    for ref, valor in planas:
        modelo = pref + ref
        if _modelo_con_fbx(modelo, familia, fbx) and _compatible_unity(
                montaje, False, modelo):
            a = _a_de(valor)
            detalles.append({
                "id": modelo, "tipo": ref, "a_m": a, "atirantada": False,
                "etiqueta": _etiqueta_detalle(montaje, ref, a, None, False),
            })
    for ref, valor in atir:
        modelo = pref + ref
        if _modelo_con_fbx(modelo, familia, fbx) and _compatible_unity(
                montaje, True, modelo):
            a = _a_de(valor)
            detalles.append({
                "id": modelo, "tipo": ref, "a_m": a, "atirantada": True,
                "etiqueta": _etiqueta_detalle(montaje, ref, a, None, True),
            })
    return detalles


def _detalles_boveda(tablas, fbx, gama, montaje):
    """Detalles de las bovedas (capa, pico o triangulo)."""
    pref = "C_" if gama == "SERIE_C" else ""
    familia = GAMAS[gama]["familia"]
    if montaje == "BOVEDA_CAPA":
        tabla = tablas.get("SERIE_C_BOVEDAS_CAPA" if pref else "BOVEDAS_CAPA",
                           {})
    elif montaje == "BOVEDA_PICO":
        tabla = tablas.get("SERIE_C_BOVEDAS_PICO" if pref else "BOVEDAS_PICO",
                           {})
    else:
        tabla = tablas.get("SERIE_C_BOVEDAS_TRIANGULO" if pref
                           else "BOVEDAS_TRIANGULO", {})
    detalles = []
    for ref, valor in sorted(tabla.items()):
        modelo = pref + ref
        if _modelo_con_fbx(modelo, familia, fbx) and _compatible_unity(
                montaje, False, modelo):
            a = _a_de(valor); total = _total_de(valor)
            detalles.append({
                "id": modelo, "tipo": ref, "a_m": a, "atirantada": False,
                "etiqueta": _etiqueta_detalle(montaje, ref, a, total, False),
            })
    return detalles


def _detalles_recta(tablas, fbx, gama, montaje):
    """Detalles ARCX para HORIZONTAL y DOBLE_CIRCUITO (solo gamas ANDEL)."""
    if gama not in ("ANDEL_M50", "ANDEL_M60"):
        return []  # las crucetas rectas ARCX son del catalogo ANDEL
    familia = GAMAS[gama]["familia"]
    detalles = []
    for ref, valor in sorted(tablas.get("CRUCETAS_ARCX", {}).items()):
        modelo = ref
        if _modelo_con_fbx(modelo, familia, fbx) and _compatible_unity(
                montaje, False, modelo):
            a = _a_de(valor); total = _total_de(valor)
            detalles.append({
                "id": modelo, "tipo": ref, "a_m": a, "atirantada": False,
                "etiqueta": _etiqueta_detalle(montaje, ref, a, total, False),
            })
    return detalles


def _detalles_de(tablas, fbx, gama, montaje):
    if montaje in ("TRESBOLILLO", "BANDERA"):
        return _detalles_semicrucetas(tablas, fbx, gama, montaje)
    if montaje in ("BOVEDA_CAPA", "BOVEDA_PICO", "BOVEDA_TRIANGULO"):
        return _detalles_boveda(tablas, fbx, gama, montaje)
    if montaje in ("HORIZONTAL", "DOBLE_CIRCUITO"):
        return _detalles_recta(tablas, fbx, gama, montaje)
    return []


def catalogo_wizard(numero_fases=3):
    """Catalogo completo para el asistente de Unity (JSON listo para usar)."""
    tablas = _cargar_tablas_catalogo()
    fbx = _fbx_crucetas_disponibles()
    gamas = []
    for gid, g in GAMAS.items():
        montajes = []
        for mid, m in MONTAJES.items():
            if mid in MONTAJES_6_FASES and numero_fases < 6:
                continue  # la linea no tiene 6 fases
            detalles = _detalles_de(tablas, fbx, gid, mid)
            if not detalles:
                continue
            montajes.append({
                "tipo": mid,
                "nombre": m["nombre"],
                "niveles": m["niveles"],
                "detalles": detalles,
            })
        gamas.append({
            "id": gid,
            "nombre": g["nombre"],
            "familia": g["familia"],
            "montajes": montajes,
        })
    return {
        "numero_fases": numero_fases,
        "gamas": gamas,
    }


# ---------------------------------------------------------------------------
# Escritura en Excel y en apoyos_configurados.json
# ---------------------------------------------------------------------------
def _fila_de_apoyo(ws, apoyo_numero):
    for fila in ws.iter_rows(min_row=1, max_col=2):
        numero = _numero_decimal(fila[0].value)
        if numero is not None and int(numero) == int(apoyo_numero):
            return fila[0].row
    return None


def _modelo_armado_id(referencia_apoyo):
    """Mismo criterio que principal._resolver_modelo_armado."""
    clave = _clave_texto(referencia_apoyo)
    if not clave:
        return None
    if "serie c" in clave:
        nivel = re.search(r"\bc\s*(500|1000|2000|3000|4500|7000|9000)\b", clave)
        if nivel:
            return "SERIE_C_C%s" % nivel.group(1)
    identificador = re.sub(r"[^A-Z0-9]+", "_", clave.upper()).strip("_")
    return "ARMADO_%s" % identificador if identificador else None


def _nueva_referencia_apoyo(gama, referencia_actual=None):
    """Referencia completa de la gama CONSERVANDO la clase del apoyo
    (C-1000, C-2000...). Ej: apoyo C-1000 en Andel M60 -> 'Andel M60 C-1000'."""
    clase = "2000"
    if referencia_actual:
        m = re.search(r"\bC\s*[-]?\s*(\d{3,4})\b", str(referencia_actual))
        if m:
            clase = m.group(1)
    clase_completa = "C-%s" % clase
    return {
        "SERIE_C": "Andel Serie C %s" % clase_completa,
        "ANDEL_M60": "Andel M60 %s" % clase_completa,
        "ANDEL_M50": "Andel M50 %s" % clase_completa,
        "SERIE_G": "Andel Serie G %s" % clase_completa,
    }[gama]


def _leer_referencia_apoyo(ruta_excel, apoyo_numero):
    """Referencia del apoyo en 'Apoyos y crucetas' col B (conserva la clase)."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws = wb["Apoyos y crucetas"]
    col = _localizar_columna(ws, [r"referencia.*apoyo"], 2)
    fila = _fila_de_apoyo(ws, apoyo_numero)
    if col is None or fila is None:
        return None
    return ws.cell(row=fila, column=col + 1).value


def _bloque_armado_para(gama, referencia_apoyo):
    g = GAMAS[gama]
    ruta = "ModelosArmado/Modulo_%s" % g["familia"]
    return {
        "modelo_id": _modelo_armado_id(referencia_apoyo),
        "referencia_origen": referencia_apoyo,
        "recurso_unity": g["recurso_cabeza"],
        "familia": g["familia"],
        "altura_cabeza_m": g["cabeza_m"],
        "altura_modulo_m": g["modulo_m"],
        "recurso_modulo_a": ruta + "_A",
        "recurso_modulo_b": ruta + "_B",
        "primer_patron_bajo_cabeza": g["primer_patron"],
    }


def _ruta_config_unity(carpeta_excel):
    return str(assets_dir() / "apoyos_configurados.json")


def actualizar_excel(salida_excel, apoyo_numero, gama, montaje, detalle,
                     referencia_apoyo):
    wb = openpyxl.load_workbook(salida_excel)
    ws = wb["Apoyos y crucetas"]
    col_ref_apoyo = _localizar_columna(ws, [r"referencia.*apoyo"], 2)
    col_armado = _localizar_columna(ws, [r"armado.*base"], 2)
    col_long = _localizar_columna(ws, [r"longitud.*crucetas"], 2)
    col_ref_armado = _localizar_columna(ws, [r"referenc.*armado"], 2)
    col_sep = _localizar_columna(ws, [r"separaci.*crucetas"], 2)
    col_ref_cruc = _localizar_columna(ws, [r"referencia.*cruceta"], 2)
    col_tipo_cruc = _localizar_columna(ws, [r"cruceta.*tipo"], 2)
    fila = _fila_de_apoyo(ws, apoyo_numero)
    if fila is None:
        raise ValueError("No se encontro la fila del apoyo %s en el Excel."
                         % apoyo_numero)
    valores = [
        (col_ref_apoyo, referencia_apoyo),
        (col_armado, MONTAJES[montaje]["texto_excel"]),
        (col_long, round(detalle["a_m"], 2)),
        (col_ref_armado, MONTAJES[montaje]["referencia_armado"]),
        (col_sep, MONTAJES[montaje]["d_m"]),
        (col_ref_cruc, detalle["tipo"]),
        (col_tipo_cruc, detalle["tipo"]),
    ]
    for col, valor in valores:
        if col is not None:
            ws.cell(row=fila, column=col + 1).value = valor
    wb.save(salida_excel)


def actualizar_eleccion_apoyos(salida_excel, apoyo_numero, gama, montaje):
    """Actualiza la pestana 'Elección apoyos':
      - col G ('Monta. y sep. condu.'): el texto del montaje (p.ej. 'Tres.').
      - col M ('Refer. del apoyo'): la referencia corta de la gama
        (p.ej. 'C-2000' -> 'M60 C-2000'), conservando anotaciones y clase."""
    wb = openpyxl.load_workbook(salida_excel)
    ws = wb["Elección apoyos"]
    col_montaje = _localizar_columna(ws, [r"monta.*sep.*condu"])
    col_refer = _localizar_columna(ws, [r"refer.*apoyo"])
    fila = _fila_de_apoyo(ws, apoyo_numero)
    if fila is None:
        wb.close()
        return

    nuevo_texto = MONTAJES[montaje]["texto_eleccion"]
    if col_montaje is not None:
        actual = ws.cell(row=fila, column=col_montaje + 1).value
        actual = actual if isinstance(actual, str) else ""
        # Reemplaza el token de montaje actual ('Tres.', 'Band.', ...)
        # conservando el resto de la celda (separaciones, saltos...).
        for mid, m in MONTAJES.items():
            if actual.startswith(m["texto_eleccion"]):
                actual = actual[len(m["texto_eleccion"]):]
                break
        else:
            actual = " " + actual.lstrip()
        ws.cell(row=fila, column=col_montaje + 1).value = nuevo_texto + actual

    if col_refer is not None:
        actual = ws.cell(row=fila, column=col_refer + 1).value
        actual = actual if isinstance(actual, str) else ""
        m = re.search(r"\bC\s*[-]?\s*(\d{3,4})\b", actual)
        clase = m.group(1) if m else "2000"
        prefijo = {"SERIE_C": "C", "ANDEL_M60": "M60 C",
                   "ANDEL_M50": "M50 C", "SERIE_G": "G C"}[gama]
        nuevo_token = "%s-%s" % (prefijo, clase)
        m_old = re.search(r"(?:M\s*(?:50|60)\s*C|G\s*C|C)\s*[-]?\s*\d{3,4}",
                          actual)
        if m_old:
            actual = actual[:m_old.start()] + nuevo_token + actual[m_old.end():]
        else:
            actual = nuevo_token + actual
        ws.cell(row=fila, column=col_refer + 1).value = actual
    wb.save(salida_excel)


def actualizar_config_unity(ruta_config, apoyo_numero, gama, montaje,
                            detalle, cambiar_armado, referencia_apoyo):
    from cambiar_cruceta import _reconstruir_config_id
    with open(ruta_config, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    encontrado = False
    for apoyo_obj in cfg.get("apoyos", []):
        apoyo = apoyo_obj.get("apoyo") or {}
        if apoyo.get("numero") != int(apoyo_numero):
            continue
        if cambiar_armado:
            apoyo_obj["catalogo_id"] = GAMAS[gama]["catalogo_id"]
            apoyo_obj["armado"] = _bloque_armado_para(gama, referencia_apoyo)
        montaje_obj = apoyo_obj.setdefault("montaje", {})
        montaje_obj["montaje_id"] = "MONTAJE_" + montaje
        montaje_obj["tipo"] = montaje
        montaje_obj["referencia_armado"] = MONTAJES[montaje]["referencia_armado"]
        montaje_obj["separacion_vertical_m"] = MONTAJES[montaje]["d_m"]
        montaje_obj["lado_inicial"] = 1
        cruceta = apoyo_obj.setdefault("cruceta", {})
        cruceta["modelo_id"] = detalle["id"]
        cruceta["tipo_origen"] = detalle["tipo"]
        cruceta["referencia_origen"] = detalle["tipo"]
        cruceta["a_m"] = round(detalle["a_m"], 3)
        cruceta["es_atirantada"] = detalle["atirantada"]
        apoyo_obj["configuracion_id"] = _reconstruir_config_id(apoyo_obj)
        encontrado = True
        break
    if not encontrado:
        raise ValueError("No se encontro el apoyo %s en '%s'."
                         % (apoyo_numero, ruta_config))
    with open(ruta_config, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return ruta_config


# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------
def cambiar_tipo_apoyo(ruta_excel, apoyo_numero, gama, montaje, detalle,
                       numero_fases=3, salida_excel=None, config_unity=None,
                       ruta_utm=None):
    """Cambia el tipo de apoyo: gama + montaje + detalle (cruceta/boveda).

    - gama: "SERIE_C", "ANDEL_M60", "ANDEL_M50", "SERIE_G"
    - montaje: "TRESBOLILLO", "BANDERA", "BOVEDA_CAPA", ...
    - detalle: el 'id' de una opcion del catalogo_wizard().

    Valida contra el catalogo real (FBX + compatibilidad Unity + fases) y
    actualiza el Excel de trabajo y apoyos_configurados.json."""
    gama = str(gama or "").upper().strip()
    montaje = str(montaje or "").upper().strip()
    if gama not in GAMAS:
        raise ValueError("Gama desconocida: %r. Usa: %s."
                         % (gama, ", ".join(sorted(GAMAS))))
    if montaje not in MONTAJES:
        raise ValueError("Montaje desconocido: %r. Usa: %s."
                         % (montaje, ", ".join(sorted(MONTAJES))))

    # ---- Localizar el detalle en el catalogo (valida fases y FBX) ----
    cat = catalogo_wizard(numero_fases=numero_fases)
    d = None
    for g in cat["gamas"]:
        if g["id"] != gama:
            continue
        for m in g["montajes"]:
            if m["tipo"] != montaje:
                continue
            for opcion in m["detalles"]:
                if opcion["id"] == detalle:
                    d = opcion
                    break
    if d is None:
        raise ValueError(
            "El detalle '%s' no esta disponible para %s / %s con %d fases. "
            "Usa '--catalogo' para ver las opciones validas."
            % (detalle, gama, montaje, numero_fases))

    # ---- Excel de trabajo (acumulativo) ----
    if salida_excel is None:
        base = os.path.splitext(os.path.basename(ruta_excel))[0]
        salida_excel = os.path.join(os.path.dirname(os.path.abspath(ruta_excel)),
                                    base + "_editada.xlsx")
    import shutil
    salida_abs = os.path.abspath(salida_excel)
    if not os.path.exists(salida_excel):
        os.makedirs(os.path.dirname(salida_abs), exist_ok=True)
        shutil.copy2(ruta_excel, salida_excel)
        print("  [cambiar_tipo_apoyo] Copia creada:", salida_excel)

    # Referencia actual (conserva la clase C-1000/C-2000 del apoyo)
    referencia_actual = _leer_referencia_apoyo(salida_excel, int(apoyo_numero))
    nueva_referencia = _nueva_referencia_apoyo(gama, referencia_actual)

    actualizar_excel(salida_excel, int(apoyo_numero), gama, montaje, d,
                     nueva_referencia)
    actualizar_eleccion_apoyos(salida_excel, int(apoyo_numero), gama, montaje)

    # ---- BOVEDAS: la ALTURA TOTAL del apoyo puede variar. Si el montaje es
    #      una boveda y la altura actual no deja hueco para ella sobre la
    #      cabeza, se SUBE el apoyo (alturas del Excel + cota UTM +
    #      desniveles y tensiones) usando el mismo mecanismo que 'mover
    #      apoyo y altura'. Los archivos de ENTRADA nunca se modifican. ----
    delta_altura_m = 0.0
    aviso_altura = None
    if montaje in ("BOVEDA_CAPA", "BOVEDA_PICO", "BOVEDA_TRIANGULO"):
        try:
            altura_b = d.get("total_m")
            if altura_b:
                import modulos_fuste as mf
                import mover_apoyo as ma
                cabeza = float(GAMAS[gama]["cabeza_m"])
                modulo = float(GAMAS[gama]["modulo_m"])
                minimo = cabeza + float(altura_b) + modulo
                alturas = mf.leer_alturas_por_apoyo(salida_excel)
                a = alturas.get(int(apoyo_numero), {})
                actual = (a.get("altura_total_m") or a.get("cogolla_m")
                          or a.get("href_m"))
                if actual is not None and actual + 1e-6 < minimo:
                    delta_altura_m = minimo - float(actual)
                    nuevas = {}
                    for clave, val in a.items():
                        if isinstance(val, (int, float)):
                            nuevas[clave] = val + delta_altura_m
                    if "altura_total_m" not in nuevas:
                        nuevas["altura_total_m"] = float(actual) + delta_altura_m
                    mf.actualizar_alturas_excel(
                        salida_excel, int(apoyo_numero), nuevas)

                    # Cota UTM + desniveles + tensiones + CSV + doc UTM
                    utm_editado_candidato = os.path.join(
                        os.path.dirname(os.path.abspath(salida_excel)),
                        "utm_editado.json")
                    ruta_utm_ef = utm_editado_candidato \
                        if os.path.exists(utm_editado_candidato) \
                        else (ruta_utm or mf._localizar_utm(
                            salida_excel, ruta_excel))
                    if ruta_utm_ef and os.path.exists(ruta_utm_ef):
                        utm = ma.leer_utm(ruta_utm_ef)
                        k = int(apoyo_numero) - 1
                        if 0 <= k < len(utm):
                            utm[k]["cota"] = (float(utm[k]["cota"])
                                              + delta_altura_m)
                            p = utm[k]
                            ma.mover_apoyo_en_linea(
                                salida_excel, ruta_utm_ef, int(apoyo_numero),
                                nuevo_x=p["x"], nuevo_y=p["y"],
                                nuevo_z=p["cota"],
                                salida_excel=salida_excel, utm_inicial=utm)
                            ma.regenerar_csv_linea(os.path.join(
                                os.path.dirname(os.path.abspath(salida_excel)),
                                "utm_editado.json"))
        except Exception as error_altura:
            aviso_altura = str(error_altura)

    # ---- Esfuerzos V/T/L (el tipo de apoyo cambia las formulas del
    #      CalculoApoyos) ----
    try:
        from cambiar_cadena_conductor import recalcular_esfuerzos_apoyos
        recalcular_esfuerzos_apoyos(ruta_excel, salida_excel)
        print("  [cambiar_tipo_apoyo] Esfuerzos V/T/L actualizados.")
    except Exception as error_esf:
        print("  ⚠️ No se pudieron recalcular los esfuerzos V/T/L:",
              error_esf)

    # ---- Configuracion de Unity ----
    ruta_config = None
    if config_unity is None:
        config_unity = _ruta_config_unity(
            os.path.dirname(os.path.abspath(ruta_excel)))
    cambiar_armado = False
    if os.path.exists(config_unity):
        with open(config_unity, encoding="utf-8") as f:
            cfg = json.load(f)
        for apoyo_obj in cfg.get("apoyos", []):
            apoyo = apoyo_obj.get("apoyo") or {}
            if apoyo.get("numero") == int(apoyo_numero):
                gama_actual = apoyo_obj.get("catalogo_id")
                familia_actual = (apoyo_obj.get("armado") or {}).get("familia")
                cambiar_armado = not (
                    gama_actual == GAMAS[gama]["catalogo_id"]
                    and familia_actual == GAMAS[gama]["familia"])
                break
        ruta_config = actualizar_config_unity(
            config_unity, int(apoyo_numero), gama, montaje, d, cambiar_armado,
            nueva_referencia)
        print("  [cambiar_tipo_apoyo] Unity actualizado:", ruta_config)

    return {
        "apoyo_numero": int(apoyo_numero),
        "gama": gama,
        "gama_nombre": GAMAS[gama]["nombre"],
        "montaje": montaje,
        "montaje_nombre": MONTAJES[montaje]["nombre"],
        "detalle": d["id"],
        "tipo": d["tipo"],
        "a_m": round(d["a_m"], 3),
        "atirantada": d["atirantada"],
        "cambio_gama": cambiar_armado,
        "delta_altura_m": round(delta_altura_m, 3),
        "aviso_altura": aviso_altura,
        "salida_excel": os.path.abspath(salida_excel),
        "config_unity": os.path.abspath(ruta_config) if ruta_config else None,
    }


# ---------------------------------------------------------------------------
# CLI (JSON) para Unity
# ---------------------------------------------------------------------------
def procesar_peticion_json(ruta_peticion, ruta_resultado=None):
    """Peticion: {"excel":.., "salida_excel":.., "apoyo":N, "gama":..,
    "montaje":.., "detalle":.., "numero_fases":3, "config_unity":..}."""
    with open(ruta_peticion, encoding="utf-8-sig") as f:
        p = json.load(f)
    try:
        res = cambiar_tipo_apoyo(
            p.get("excel"), int(p["apoyo"]), p.get("gama"), p.get("montaje"),
            p.get("detalle"),
            numero_fases=int(p.get("numero_fases") or 3),
            salida_excel=p.get("salida_excel"),
            config_unity=p.get("config_unity"),
            ruta_utm=p.get("utm"))
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

    if "--catalogo" in sys.argv:
        cat = catalogo_wizard(numero_fases=3)
        print(json.dumps(cat, ensure_ascii=False, indent=2))
    elif "--peticion" in sys.argv:
        idx = sys.argv.index("--peticion")
        ruta_peticion = sys.argv[idx + 1]
        ruta_resultado = None
        if "--resultado" in sys.argv:
            ruta_resultado = sys.argv[sys.argv.index("--resultado") + 1]
        r = procesar_peticion_json(ruta_peticion, ruta_resultado)
        print(json.dumps(r, ensure_ascii=False, indent=2)[:2500])
    else:
        print("== CATALOGO DE TIPOS DE APOYO (3 fases) ==")
        cat = catalogo_wizard(numero_fases=3)
        for g in cat["gamas"]:
            print("\n[%s] %s (familia %s)" % (g["id"], g["nombre"], g["familia"]))
            for m in g["montajes"]:
                print("   %-16s (%d nivel, %d opciones)"
                      % (m["nombre"], m["niveles"], len(m["detalles"])))
                for d in m["detalles"]:
                    print("      - %s" % d["etiqueta"])






