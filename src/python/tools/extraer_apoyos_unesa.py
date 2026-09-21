# -*- coding: utf-8 -*-
"""
extraer_apoyos_unesa.py
=======================
Convierte 'Apoyos Unesa.pdf' a 'apoyos_unesa.json' (facil de leer).

El catalogo contiene, para cada apoyo (C-500 ... C-13000):
  - tablas de ESFUERZOS por hipotesis y altura (c.d.g.):
      columnas T (transversal), L (longitudinal), V (vertical) para
      'fin de linea', 'angulo' y 'otros' (valores normalizados).
  - tabla de CRUCETAS por longitud de cruceta (m).

USO:  py extraer_apoyos_unesa.py
"""
import json
import os
import re

import fitz

PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Apoyos Unesa.pdf")
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apoyos_unesa.json")

RE_APOYO = re.compile(r"Apoyo\s+(C-?\d+)")


def _num(valor):
    """Convierte '1,5' / '26' / '' -> float / None."""
    if valor is None:
        return None
    texto = str(valor).strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _rellenar(filas, indice):
    """Rellena hacia abajo la columna 'indice' (celdas fusionadas en el PDF)."""
    ultimo = None
    for fila in filas:
        valor = fila[indice] if indice < len(fila) else None
        if valor is not None and str(valor).strip():
            ultimo = str(valor).strip()
        fila[indice] = ultimo
    return filas


def _normalizar_trio(fila, i):
    """Extrae T, L, V de tres celdas consecutivas (valores None si vacias)."""
    return {"T": _num(fila[i]), "L": _num(fila[i + 1]), "V": _num(fila[i + 2])}


def parsear_hipotesis(tabla):
    """Convierte una tabla de esfuerzos (find_tables) en filas estructuradas."""
    filas = [list(f) for f in tabla.extract()]
    if not filas:
        return []
    _rellenar(filas, 0)   # fases
    _rellenar(filas, 1)   # c.d.g.
    _rellenar(filas, 2)   # hipotesis
    _rellenar(filas, 3)   # seguridad

    resultado = []
    for fila in filas:
        if len(fila) < 13:
            continue
        fases = _num(fila[0])
        cdg_raw = fila[1]
        hip = re.sub(r"\s+", " ", str(fila[2])).strip().lower()
        if not hip or not fases:
            continue
        if hip not in ("viento 120", "viento 140",
                       "hielo+viento 60km/h", "hielo", "desequilibrio"):
            continue
        # Normalizar c.d.g. a centimetros:
        #  - fases 3: siempre viene en cm
        #  - fases 6: el PDF es inconsistente (metros 1.2/1.8/2.4 en unos apoyos,
        #    centimetros 140/210/240 en otros). Si el valor es < 50 se asume metros.
        cdg_num = _num(cdg_raw)
        if cdg_num is None:
            cdg_cm = None
        elif int(fases) == 6 and abs(cdg_num) < 50:
            cdg_cm = cdg_num * 100.0
        else:
            cdg_cm = cdg_num
        resultado.append({
            "fases": int(fases),
            "cdg_raw": cdg_raw,
            "cdg_cm": cdg_cm,
            "hipotesis": hip,
            "seguridad": _num(fila[3]),
            "fin_de_linea": _normalizar_trio(fila, 4),
            "angulo": _normalizar_trio(fila, 7),
            "otros": _normalizar_trio(fila, 10),
        })
    return resultado


def parsear_crucetas(tabla):
    """Convierte la tabla de crucetas (por longitud de cruceta) en filas."""
    filas = [list(f) for f in tabla.extract()]
    resultado = []
    for fila in filas:
        if len(fila) < 13:
            continue
        cru = _num(fila[0])
        if cru is None:
            continue
        resultado.append({
            "cruceta_m": cru,
            "simple_circuito_angulo": _normalizar_trio(fila, 1),
            "simple_circuito_otros": _normalizar_trio(fila, 4),
            "doble_circuito_angulo": _normalizar_trio(fila, 7),
            "doble_circuito_otros": _normalizar_trio(fila, 10),
        })
    return resultado


def extraer():
    doc = fitz.open(PDF)
    apoyos = {}   # designacion -> {tablas_esfuerzos, tabla_crucetas}
    orden = []
    apoyo_actual = None

    for pagina in doc:
        texto = pagina.get_text()
        # Detectar el apoyo que corresponde a esta pagina (el ultimo titulo visto)
        for m in RE_APOYO.finditer(texto):
            apoyo_actual = m.group(1)
            if apoyo_actual not in apoyos:
                apoyos[apoyo_actual] = {"tablas_esfuerzos": [], "tabla_crucetas": []}
                orden.append(apoyo_actual)

        for tabla in pagina.find_tables().tables:
            filas = [list(f) for f in tabla.extract()]
            cabecera = " ".join(str(c) for fila in filas[:3] for c in fila if c).lower()
            if apoyo_actual is None:
                continue
            if "hipotesis" in cabecera or "c.d.g." in cabecera:
                apoyos[apoyo_actual]["tablas_esfuerzos"].extend(parsear_hipotesis(tabla))
            elif "cruceta" in cabecera:
                apoyos[apoyo_actual]["tabla_crucetas"].extend(parsear_crucetas(tabla))

    documento = {
        "version_esquema": 1,
        "fuente": os.path.abspath(PDF),
        "nota": ("Catalogos Unesa de apoyos. 'cdg_raw' es la altura del centro de"
                 " gravedad tal cual viene en el PDF (fases 3 en cm, fases 6 en m)."
                 " T=esfuerzo transversal, L=longitudinal, V=vertical (daN)."),
        "apoyos": [{"designacion": d, **apoyos[d]} for d in orden],
    }
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)

    print("Apoyos:", orden)
    for d in orden:
        print("  %-7s esfuerzos=%d  crucetas=%d"
              % (d, len(apoyos[d]["tablas_esfuerzos"]),
                 len(apoyos[d]["tabla_crucetas"])))
    print("JSON guardado en:", SALIDA)


if __name__ == "__main__":
    extraer()
