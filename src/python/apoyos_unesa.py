# -*- coding: utf-8 -*-
"""
apoyos_unesa.py
===============
Obtiene el esfuerzo util (Fu) de cada apoyo a partir del catalogo Unesa
(apoyos_unesa.json, extraido del PDF 'Apoyos Unesa.pdf').

Procedimiento:
  1. Clase del apoyo (C-500, C-1000, ...) desde 'Apoyos y crucetas'
     columna 'Referencia del apoyo segun catalogo del fabricante'.
  2. Centro de gravedad (cdg) del ARMADO SUPERIOR, medido desde la parte mas
     alta del apoyo hacia abajo, teniendo en cuenta la longitud de las
     crucetas (no se considera el fuste):
         posiciones de las crucetas desde arriba: cabeza - i*separacion
         cdg = sum(longitud_i * posicion_i) / sum(longitud_i)
  3. Se aproxima el cdg al inmediato superior disponible en el catalogo.
  4. Fu = columna T (viento 120) de la tabla segun fases (3 o 6) y segun el
     uso del apoyo: fin de linea (principio/final), angulo, u otros.
"""
import os
import re

import openpyxl

from twinelec_paths import catalogs_dir

RUTA_CATALOGO = str(catalogs_dir() / "apoyos_unesa.json")

# Altura de la cabeza (armado superior) por familia (Blender crear_armados.py)
ALTURA_CABEZA_POR_FAMILIA = {
    "C": 4.2, "M50": 4.0, "M60": 4.0, "G": 5.6,
}

# Numero de niveles verticales de crucetas segun el montaje
NIVELES_POR_MONTAJE = {
    "tresbolillo": 3,
    "doble circuito": 3,
    "boveda horizontal": 1,
}

# Uso del apoyo en el catalogo segun el tipo
USO_POR_TIPO = {
    "principio_final_de_linea": "fin_de_linea",
    "alineacion_suspension": "otros",
    "alineacion_amarre": "otros",
    "alineacion_anclaje": "otros",
    "angulo_suspension": "angulo",
    "angulo_amarre": "angulo",
    "angulo_anclaje": "angulo",
}

# Fases del catalogo segun el montaje (3=simple circuito, 6=doble circuito)
FASES_POR_MONTAJE = {
    "tresbolillo": 3,
    "boveda horizontal": 3,
    "doble circuito": 6,
}


def _texto_limpio(valor):
    if valor is None:
        return None
    texto = str(valor).replace("_x000D_", " ").replace("\n", " ").strip()
    texto = re.sub(r"\s+", " ", texto)
    if not texto or all(c in "-–— " for c in texto):
        return None
    return texto


def _clave_texto(valor):
    texto = _texto_limpio(valor)
    if texto is None:
        return ""
    import unicodedata
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def _localizar_columna(ws, patrones, fila_cabecera=1):
    for celda in ws[fila_cabecera]:
        clave = _clave_texto(celda.value)
        if clave and any(re.search(p, clave) for p in patrones):
            return celda.column - 1
    return None


def _float(valor):
    if valor is None:
        return None
    texto = str(valor).replace(",", ".").strip()
    try:
        return float(texto)
    except ValueError:
        return None


def cargar_catalogo(ruta=None):
    import json
    if ruta is None:
        ruta = RUTA_CATALOGO
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)

def extraer_clase_por_apoyo(archivo_excel):
    """Devuelve {apoyo_numero: 'C-2000'} desde 'Apoyos y crucetas'."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Apoyos y crucetas"]
    col_ref = _localizar_columna(ws, [r"referencia.*apoyo"], fila_cabecera=2)
    if col_ref is None:
        return {}
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        try:
            numero = int(fila[0].value)
        except (TypeError, ValueError):
            continue
        ref = _texto_limpio(fila[col_ref].value)
        if ref:
            m = re.search(r"(C-?\d+)", ref, re.I)
            if m:
                resultado[numero] = m.group(1).upper()
    return resultado


def extraer_datos_armado(archivo_excel):
    """Devuelve {apoyo_numero: {montaje, separacion_m, cabeza_m, long_cruceta_m}}."""
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    ws = wb["Apoyos y crucetas"]
    col_montaje = _localizar_columna(ws, [r"armado.*base"], fila_cabecera=2)
    col_sep = _localizar_columna(ws, [r"separaci.*crucetas"], fila_cabecera=2)
    col_long = _localizar_columna(ws, [r"longitud.*crucetas"], fila_cabecera=2)
    if col_montaje is None:
        return {}
    resultado = {}
    for fila in ws.iter_rows(min_row=1):
        try:
            numero = int(fila[0].value)
        except (TypeError, ValueError):
            continue
        montaje = _texto_limpio(fila[col_montaje].value)
        if not montaje:
            continue
        sep = _float(fila[col_sep].value) if col_sep is not None else None
        long_cru = _float(fila[col_long].value) if col_long is not None else None
        cabeza = ALTURA_CABEZA_POR_FAMILIA.get("C")
        resultado[numero] = {
            "montaje": montaje,
            "montaje_clave": _clave_texto(montaje),
            "separacion_m": sep,
            "long_cruceta_m": long_cru,
            "cabeza_m": cabeza,
        }
    return resultado


def calcular_cdg_armado_cm(armado):
    """cdg del armado superior desde la parte mas alta del apoyo, en cm.
    Posiciones de las crucetas desde arriba: cabeza - i*separacion.
    Se pondera por la longitud de cada cruceta (todas iguales -> media)."""
    cabeza = armado.get("cabeza_m")
    sep = armado.get("separacion_m")
    niveles = NIVELES_POR_MONTAJE.get(armado.get("montaje_clave"), 3)
    long_cru = armado.get("long_cruceta_m") or 1.0
    if cabeza is None or sep is None:
        return None
    posiciones = [cabeza - i * sep for i in range(niveles)]
    posiciones = [p for p in posiciones if p >= 0]
    if not posiciones:
        return None
    cdg_m = sum(posiciones) / len(posiciones)
    return cdg_m * 100.0


def fu_desde_catalogo(clase, fases, cdg_cm, tipo_uso, catalogo=None):
    """Fu [daN] = columna T (viento 120) del catalogo para la clase, fases,
    cdg (aproximado al superior) y tipo de uso (fin_de_linea/angulo/otros)."""
    if catalogo is None:
        catalogo = cargar_catalogo()
    apoyo = None
    for a in catalogo.get("apoyos", []):
        if a["designacion"].upper() == str(clase).upper():
            apoyo = a
            break
    if apoyo is None:
        return None

    filas = [t for t in apoyo["tablas_esfuerzos"]
             if t["fases"] == int(fases) and t["cdg_cm"] is not None]
    if not filas:
        return None

    cdgs = sorted({t["cdg_cm"] for t in filas})
    cdg_uso = None
    if cdg_cm is not None:
        for c in cdgs:
            if c >= cdg_cm - 1e-6:
                cdg_uso = c
                break
    if cdg_uso is None:
        cdg_uso = max(cdgs)

    for t in filas:
        if abs(t["cdg_cm"] - cdg_uso) < 1e-6 and t["hipotesis"] == "viento 120":
            col = t.get(tipo_uso) or {}
            return col.get("T")
    return None

def fu_por_hipotesis_para_apoyo(numero, tipo_clave, archivo_excel, catalogo=None):
    """Devuelve {hipotesis: Fu_daN} con la columna T para CADA condicion
    (viento 120, viento 140, hielo+viento 60km/h, hielo, desequilibrio)."""
    clases = extraer_clase_por_apoyo(archivo_excel)
    armados = extraer_datos_armado(archivo_excel)
    clase = clases.get(numero)
    armado = armados.get(numero)
    if not clase or not armado:
        return None
    cdg = calcular_cdg_armado_cm(armado)
    fases = FASES_POR_MONTAJE.get(armado["montaje_clave"], 3)
    uso = USO_POR_TIPO.get(tipo_clave)
    if uso is None:
        return None
    return _fu_por_hipotesis(clase, fases, cdg, uso, catalogo)


def _fu_por_hipotesis(clase, fases, cdg_cm, tipo_uso, catalogo=None):
    """Columnas T (daN) para cada hipotesis del catalogo, al cdg indicado."""
    if catalogo is None:
        catalogo = cargar_catalogo()
    apoyo = None
    for a in catalogo.get("apoyos", []):
        if a["designacion"].upper() == str(clase).upper():
            apoyo = a
            break
    if apoyo is None:
        return None
    filas = [t for t in apoyo["tablas_esfuerzos"]
             if t["fases"] == int(fases) and t["cdg_cm"] is not None]
    if not filas:
        return None
    cdgs = sorted({t["cdg_cm"] for t in filas})
    cdg_uso = None
    if cdg_cm is not None:
        for c in cdgs:
            if c >= cdg_cm - 1e-6:
                cdg_uso = c
                break
    if cdg_uso is None:
        cdg_uso = max(cdgs)

    resultado = {}
    for t in filas:
        if abs(t["cdg_cm"] - cdg_uso) < 1e-6:
            col = t.get(tipo_uso) or {}
            resultado[t["hipotesis"]] = col.get("T")
    return resultado


def fu_para_apoyo(numero, tipo_clave, archivo_excel, catalogo=None):
    """Fu [daN] principal = columna T de 'viento 120'."""
    por_hip = fu_por_hipotesis_para_apoyo(numero, tipo_clave, archivo_excel, catalogo)
    if not por_hip:
        return None
    return por_hip.get("viento 120")


if __name__ == "__main__":
    import sys
    ruta = sys.argv[1] if len(sys.argv) > 1 else "line_example.xlsx"
    catalogo = cargar_catalogo()
    for n in sorted(extraer_clase_por_apoyo(ruta)):
        armado = extraer_datos_armado(ruta).get(n, {})
        cdg = calcular_cdg_armado_cm(armado)
        print("Apoyo %d | clase=%s | cdg_armado=%.0f cm" % (n, extraer_clase_por_apoyo(ruta).get(n), cdg or -1))
