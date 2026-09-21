# -*- coding: utf-8 -*-
"""
generar_doc_utm.py
==================
Genera el documento Word UTM ACTUALIZADO, IDÉNTICO al original
('Coordinates_UTM_example.docx') pero con las coordenadas de los apoyos
en su estado ACTUAL.

De dónde salen las coordenadas (en este orden):
  1. 'utm_editado.json'  -> si existe, es el estado tras los movimientos
     (lo escribe mover_apoyo.py después de cada movimiento).
  2. 'utm_example.json' -> la extracción inicial del .docx.
  3. El propio '*UTM*.doc*' original (si no hay ningún json).

Salida: 'Coordinates_UTM_example_updated.docx' en la misma carpeta.
Se regenera automáticamente cada vez que se mueve un apoyo (lo llama
mover_apoyo.py -> mover_apoyo_en_linea) y también a mano:

    py -3 generar_doc_utm.py

El nombre contiene "UTM" y ordena ANTES que el original, así los demás
scripts (principal.py, clima.py) leen el documento ACTUALIZADO con
`glob.glob("*UTM*.doc*")[0]`.
"""
import glob
import os
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from twinelec_paths import data_dir

# ---------------------------------------------------------------------------
# Lectura de las coordenadas actuales
# ---------------------------------------------------------------------------
def leer_utm_desde_json(ruta_json):
    """Lee un json de apoyos (lista o dict con 'apoyos') -> lista de dicts
    [{'id','x','y','cota'}, ...] ordenada por id numérico."""
    import json
    with open(ruta_json, encoding="utf-8") as f:
        datos = json.load(f)
    if isinstance(datos, dict) and "apoyos" in datos:
        datos = datos["apoyos"]
    utm = []
    for p in datos:
        if not isinstance(p, dict):
            continue
        utm.append({
            "id": str(p.get("id", p.get("numero", ""))),
            "x": float(p.get("x")),
            "y": float(p.get("y")),
            "cota": float(p.get("cota", p.get("z", 0.0))),
        })
    utm.sort(key=lambda p: int(p["id"]))
    return utm


def leer_utm_desde_doc(ruta_doc):
    """Lee la tabla del .doc/.docx UTM original (mismo criterio que
    principal.py y clima.py): col 1 = id, 2 = X, 3 = Y, 4 = Cota."""
    doc = Document(ruta_doc)
    utm = []
    for i, fila in enumerate(doc.tables[0].rows):
        if i == 0:
            continue
        celdas = [c.text.replace(",", ".") for c in fila.cells]
        utm.append({
            "id": celdas[0],
            "x": float(celdas[1]),
            "y": float(celdas[2]),
            "cota": float(celdas[3]),
        })
    return utm


def _carpeta_proyecto():
    return str(data_dir())


def _doc_original(carpeta):
    """El '*UTM*.doc*' ORIGINAL (excluye los '(actualizado)' ya generados)."""
    for a in sorted(glob.glob(os.path.join(carpeta, "*UTM*.doc*"))):
        if "actualizado" not in os.path.basename(a).lower():
            return a
    return None


def leer_utm_actual(carpeta=None):
    """Devuelve las coordenadas UTM ACTUALES de los apoyos."""
    if carpeta is None:
        carpeta = _carpeta_proyecto()

    # 1. Estado tras movimientos (si existe)
    utm_editado = os.path.join(carpeta, "utm_editado.json")
    if os.path.exists(utm_editado):
        return leer_utm_desde_json(utm_editado)

    # 2. Extracción inicial
    utm_extraido = os.path.join(carpeta, "utm_example.json")
    if os.path.exists(utm_extraido):
        return leer_utm_desde_json(utm_extraido)

    # 3. El propio documento original
    original = _doc_original(carpeta)
    if original is not None:
        return leer_utm_desde_doc(original)

    raise FileNotFoundError("No se encontró ningún origen de coordenadas UTM "
                            "(utm_editado.json, utm_*.json o *UTM*.doc*).")


# ---------------------------------------------------------------------------
# Formato del documento (replica del original)
# ---------------------------------------------------------------------------
def _formatear_numero(valor):
    """'500000.00' -> '500000,00' (coma decimal, 2 cifras)."""
    return ("%.2f" % float(valor)).replace(".", ",")


def _estilo_run(run, tam_pt, negrita=True):
    run.font.name = "Arial"
    run.font.size = Pt(tam_pt)
    run.font.bold = negrita
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), "Arial")
    rfonts.set(qn("w:hAnsi"), "Arial")
    rfonts.set(qn("w:cs"), "Arial")


def _parrafo_centrado(doc, texto, tam_pt):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    if texto:
        _estilo_run(p.add_run(texto), tam_pt)
    return p


def _bordes_tabla(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for borde in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement("w:" + borde)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    tblPr.append(borders)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    cell_mar = OxmlElement("w:tblCellMar")
    for borde in ("left", "right"):
        el = OxmlElement("w:" + borde)
        el.set(qn("w:w"), "70")
        el.set(qn("w:type"), "dxa")
        cell_mar.append(el)
    tblPr.append(cell_mar)


def _celda_tabla(celda, texto):
    celda.width = Cm(3.75)
    p = celda.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    if texto:
        _estilo_run(p.add_run(texto), 10)


# ---------------------------------------------------------------------------
# Generación del documento
# ---------------------------------------------------------------------------
def _titulos_originales(carpeta):
    """Reutiliza los títulos del documento original ('Proyecto: ...',
    'Listado coordenadas UTM', 'Página nº 1') para que sea idéntico."""
    original = _doc_original(carpeta)
    if original is None:
        return ("Proyecto: TwinElec demo", "Listado coordenadas UTM",
                "Página nº 1")
    try:
        doc = Document(original)
        txts = [p.text for p in doc.paragraphs]
        t0 = txts[0] if len(txts) > 0 and txts[0].strip() else "Proyecto"
        t2 = txts[2] if len(txts) > 2 and txts[2].strip() else \
            "Listado coordenadas UTM"
        t5 = "Página nº 1"
        for t in txts:
            if "Página" in t or "página" in t:
                t5 = t
                break
        return (t0, t2, t5)
    except Exception:
        return ("Proyecto: TwinElec demo", "Listado coordenadas UTM",
                "Página nº 1")


def generar_docx_utm(utm, ruta_salida, t0=None, t2=None, t5=None):
    """Genera el .docx UTM con el formato EXACTO del original.

    utm:         lista [{'id','x','y','cota'}, ...].
    ruta_salida: dónde guardar el .docx.
    t0/t2/t5:    textos de los títulos (None -> se leen del original).
    """
    if t0 is None or t2 is None or t5 is None:
        t0, t2, t5 = _titulos_originales(os.path.dirname(ruta_salida))

    doc = Document()

    # Márgenes como el original (~3 cm laterales, ~2,5 cm verticales)
    sec = doc.sections[0]
    sec.left_margin = Cm(3.0)
    sec.right_margin = Cm(3.0)
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.5)

    # Bloque de texto (párrafos 0..7 del original)
    _parrafo_centrado(doc, t0, 16)   # 0: título del proyecto
    _parrafo_centrado(doc, "", 16)   # 1: vacío
    _parrafo_centrado(doc, t2, 16)   # 2: 'Listado coordenadas UTM'
    _parrafo_centrado(doc, "", 16)   # 3: vacío
    _parrafo_centrado(doc, "", 10)   # 4: vacío
    _parrafo_centrado(doc, t5, 10)   # 5: 'Página nº 1'
    _parrafo_centrado(doc, "", 10)   # 6: vacío
    _parrafo_centrado(doc, "", 10)   # 7: vacío

    # Tabla: cabecera + 1 fila por apoyo
    table = doc.add_table(rows=1 + len(utm), cols=4)
    _bordes_tabla(table)

    cabecera = ["Apoyo nº", "Coordenada X UTM", "Coordenada Y UTM", "Cota"]
    for j, titulo in enumerate(cabecera):
        _celda_tabla(table.rows[0].cells[j], titulo)

    for i, apoyo in enumerate(utm, start=1):
        fila = table.rows[i].cells
        _celda_tabla(fila[0], str(apoyo["id"]))
        _celda_tabla(fila[1], _formatear_numero(apoyo["x"]))
        _celda_tabla(fila[2], _formatear_numero(apoyo["y"]))
        _celda_tabla(fila[3], _formatear_numero(apoyo["cota"]))

    doc.save(ruta_salida)
    return os.path.abspath(ruta_salida)


def _ruta_salida(carpeta):
    original = _doc_original(carpeta)
    if original is None:
        nombre = "Coordenadas UTM (actualizado).docx"
    else:
        base = os.path.splitext(os.path.basename(original))[0]
        nombre = base + " (actualizado).docx"
    return os.path.join(carpeta, nombre)


def generar_docx_desde_json(ruta_json):
    """Lee un json UTM y genera el documento actualizado. Devuelve la ruta.

    Punto de entrada que usa mover_apoyo.py después de cada movimiento."""
    carpeta = os.path.dirname(os.path.abspath(ruta_json))
    utm = leer_utm_desde_json(ruta_json)
    salida = _ruta_salida(carpeta)
    return generar_docx_utm(utm, salida)


def generar_docx_actual(carpeta=None):
    """Genera el documento con las coordenadas ACTUALES de los apoyos.
    Devuelve la ruta del .docx generado."""
    if carpeta is None:
        carpeta = _carpeta_proyecto()
    utm = leer_utm_actual(carpeta)
    salida = _ruta_salida(carpeta)
    t0, t2, t5 = _titulos_originales(carpeta)
    return generar_docx_utm(utm, salida, t0=t0, t2=t2, t5=t5)


if __name__ == "__main__":
    import io
    try:
        if sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
    except Exception:
        pass
    try:
        ruta = generar_docx_actual()
        n = len(leer_utm_actual())
        print("✅ Documento UTM actualizado generado:")
        print("   ", ruta)
        print(f"    Con {n} apoyos.")
    except Exception as error:
        print("❌ Error:", error)
        sys.exit(1)
