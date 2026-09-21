# -*- coding: utf-8 -*-
"""
editar_angulo.py
================
Edicion MANUAL del ANGULO de un apoyo en 'Cálculo de apoyos' del gemelo
digital. Al cambiar el angulo se recalcula TODO en cascada:

  1. Valor del angulo (col. 'Valor angulo') en 'Cálculo de apoyos'.
  2. Coeficiente S = 2*cos(alfa/2) (col. 'Coeficientes L,N,S') del apoyo.
  3. ESFUERZOS V/T/L de las hipotesis 1a-4a (usan el angulo en las
     ecuaciones de los apoyos de angulo) -> 'Cálculo de apoyos' y
     'Elección apoyos'.
  4. Graficos de utilizacion (PNG/PDF) y rotacion 3D del apoyo
     (col. 'Angulo' de coordenadas_linea.csv de Unity).

GENERAL: funciona para cualquier apoyo/linea/excel de la plantilla.

CLI:
  py editar_angulo.py --listado p.json --resultado r.json
  py editar_angulo.py --peticion p.json --resultado r.json
"""
import json
import math
import os
import shutil

import openpyxl

from twinelec_paths import assets_dir

import mover_apoyo as mv
import cambiar_cadena_conductor as ccc
from cambiar_cadena_conductor import (
    _localizar_columna,
    _numero,
    leer_tipos_apoyos,
    recalcular_esfuerzos_apoyos,
)


# ---------------------------------------------------------------------------
# Listado de angulos actuales (para la ventana de Unity)
# ---------------------------------------------------------------------------
def _es_apoyo_de_angulo(tipo_texto, tipo_clave):
    """True si el apoyo es de ANGULO (amarre/anclaje/suspension): el tipo del
    Excel empieza por 'Ang-' (p. ej. 'Áng-Anc', 'Áng-Ama') o la clave de
    CASOS es 'angulo_*'."""
    import unicodedata
    if tipo_clave and str(tipo_clave).startswith("angulo_"):
        return True
    if not tipo_texto:
        return False
    txt = str(tipo_texto)
    txt = "".join(c for c in unicodedata.normalize("NFKD", txt)
                  if not unicodedata.combining(c)).lower()
    return txt.startswith("ang-")


def listar_angulos(ruta_excel):
    """Por apoyo DE ANGULO: numero, tipo, angulo actual y S actual.
    Solo se listan los apoyos de angulo (tipo 'Ang-*'), que son los unicos
    cuyo angulo tiene sentido editar."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    try:
        tipos = leer_tipos_apoyos(wb)
    finally:
        wb.close()
    apoyos = []
    for n in sorted(tipos.keys()):
        t = tipos[n]
        if not _es_apoyo_de_angulo(t.get("tipo_texto"), t.get("tipo_clave")):
            continue
        apoyos.append({
            "numero": n,
            "tipo": t["tipo_texto"],
            "tipo_clave": t["tipo_clave"],
            "angulo": t["angulo"],
            "S": t["S"],
            "es_de_angulo": True,
        })
    return apoyos


# ---------------------------------------------------------------------------
# Edicion del angulo
# ---------------------------------------------------------------------------
def _fila_de_apoyo(ws, apoyo_numero):
    """Fila (1-based) del apoyo en 'Cálculo de apoyos' (columna 1 = numero)."""
    for fila in ws.iter_rows(min_row=1):
        numero = _numero(fila[0].value)
        if numero is not None and int(numero) == apoyo_numero:
            return fila[0].row
    return None


def _localizar_utm(salida_excel, ruta_excel):
    """Busca el json UTM de la linea: primero junto al Excel de trabajo
    ('utm_editado.json' acumula los movimientos ya aplicados), despues junto
    al original, y por ultimo cualquier 'utm_*.json' de esas carpetas."""
    import glob
    base = os.path.splitext(os.path.basename(ruta_excel))[0]
    nombres = ["utm_editado.json", "utm_%s_extraido.json" % base]
    carpetas = [os.path.dirname(os.path.abspath(salida_excel)),
                os.path.dirname(os.path.abspath(ruta_excel)),
                os.path.dirname(os.path.abspath(__file__))]
    for carpeta in carpetas:
        for nombre in nombres:
            ruta = os.path.join(carpeta, nombre)
            if os.path.exists(ruta):
                return ruta
        globs = glob.glob(os.path.join(carpeta, "utm_*.json"))
        if globs:
            return globs[0]
    return None


def _escribir_angulo_y_s(salida_excel, apoyo_numero, alfa, S):
    """Escribe el angulo y el coeficiente S EXACTOS del apoyo en el Excel."""
    wb = openpyxl.load_workbook(salida_excel)
    try:
        ws = wb["Cálculo de apoyos"]
        fila = _fila_de_apoyo(ws, apoyo_numero)
        if fila is None:
            raise ValueError("No se encontro el apoyo %d en 'Cálculo de apoyos'."
                             % apoyo_numero)
        col_ang = _localizar_columna(ws, [r"valor.*angulo"])
        if col_ang is not None:
            ws.cell(row=fila, column=col_ang + 1).value = round(alfa, 3)
        col_l = _localizar_columna(ws, [r"^coeficientes.*l.*n.*s"])
        if col_l is not None:
            ws.cell(row=fila, column=col_l + 3).value = (
                round(S, 4) if S is not None else None)
        wb.save(salida_excel)
    finally:
        wb.close()


def editar_angulo(ruta_excel, salida_excel, apoyo_numero, angulo_nuevo,
                  ruta_utm=None):
    """Cambia el angulo del apoyo y recalcula TODA la linea:

      1. Rota las coordenadas UTM de los apoyos AGUAS ABAJO alrededor del
         apoyo editado. Los vanos y desniveles NO cambian (rotacion rigida),
         pero las coordenadas, el angulo del apoyo y el S si.
      2. Recalcula en cascada (igual que 'mover apoyo y altura'): angulos,
         coeficientes L/N/S, tensiones y flechas, esfuerzos V/T/L, el Excel
         de trabajo, el CSV de Unity y el documento UTM.
      3. Si no hay coordenadas UTM, se limita a cambiar el angulo, el S y el
         angulo 3D del CSV (comportamiento antiguo).
    Devuelve un dict con el resumen y la lista de apoyos movidos.
    """
    alfa = float(angulo_nuevo)
    if not (0.0 < alfa <= 180.0):
        raise ValueError("El angulo debe estar entre 0 y 180 grados.")

    if salida_excel != ruta_excel and not os.path.exists(salida_excel):
        shutil.copy2(ruta_excel, salida_excel)

    S = (2.0 * math.cos(math.radians(alfa / 2.0))
         if 0.0 < alfa < 180.0 else None)

    tipo_anterior = None
    try:
        wb = openpyxl.load_workbook(salida_excel, data_only=True)
        try:
            tipo_anterior = leer_tipos_apoyos(wb).get(
                int(apoyo_numero), {}).get("tipo_texto")
        finally:
            wb.close()
    except Exception:
        pass

    apoyos_movidos = []
    aviso_cascada = None
    angulo_anterior = None
    csv_actualizado = None

    # ---- Cascada completa: rotar aguas abajo + recalcular toda la linea ----
    try:
        # Preferir el 'utm_editado.json' que acumula los cambios ya aplicados.
        utm_editado_candidato = os.path.join(
            os.path.dirname(os.path.abspath(salida_excel)), "utm_editado.json")
        ruta_utm_efectiva = utm_editado_candidato \
            if os.path.exists(utm_editado_candidato) \
            else (ruta_utm or _localizar_utm(salida_excel, ruta_excel))
        if not ruta_utm_efectiva or not os.path.exists(ruta_utm_efectiva):
            raise ValueError(
                "No se encontraron las coordenadas UTM de la linea: "
                "no se puede propagar el cambio aguas abajo.")

        utm = mv.leer_utm(ruta_utm_efectiva)
        k = int(apoyo_numero) - 1
        alfa_actual = mv.angulos_linea_utm(utm)[k]
        angulo_anterior = round(alfa_actual, 3)

        delta = alfa - alfa_actual
        if abs(delta) > 1e-9:
            utm_rotada = mv.rotar_aguas_abajo(utm, k, delta)
            apoyos_movidos = [i + 1 for i in range(k + 1, len(utm_rotada))]
        else:
            utm_rotada = [dict(p) for p in utm]

        p = utm_rotada[k]
        res = mv.mover_apoyo_en_linea(
            ruta_excel, ruta_utm_efectiva, int(apoyo_numero),
            nuevo_x=p["x"], nuevo_y=p["y"], nuevo_z=p["cota"],
            salida_excel=salida_excel, utm_inicial=utm_rotada)

        # CSV de Unity regenerado (posiciones y angulos de TODOS los apoyos)
        try:
            csv_actualizado = mv.regenerar_csv_linea(res["utm_editado"])
        except Exception as error_csv:
            csv_actualizado = None
            if aviso_cascada is None:
                aviso_cascada = "CSV: %s" % error_csv
    except Exception as error_cascada:
        aviso_cascada = str(error_cascada)
        apoyos_movidos = []

    # ---- Angulo y S EXACTOS en el Excel ----
    try:
        _escribir_angulo_y_s(salida_excel, int(apoyo_numero), alfa, S)
    except Exception as error_excel:
        if aviso_cascada is None:
            aviso_cascada = str(error_excel)

    # ---- Esfuerzos V/T/L (releen el angulo y el S ya escritos) ----
    try:
        recalcular_esfuerzos_apoyos(salida_excel, salida_excel)
    except Exception as error_esf:
        if aviso_cascada is None:
            aviso_cascada = str(error_esf)

    # Si la cascada no pudo regenerar el CSV, al menos se rota el apoyo en 3D
    if csv_actualizado is None:
        csv_actualizado = _actualizar_angulo_csv(
            salida_excel, int(apoyo_numero), alfa)

    return {
        "ok": True,
        "apoyo": int(apoyo_numero),
        "tipo": tipo_anterior,
        "angulo_anterior": angulo_anterior,
        "angulo_nuevo": round(alfa, 3),
        "S_nuevo": round(S, 4) if S is not None else None,
        "apoyos_movidos": apoyos_movidos,
        "aviso_cascada": aviso_cascada,
        "csv_angulo_actualizado": csv_actualizado,
        "salida_excel": os.path.abspath(salida_excel),
    }


# ---------------------------------------------------------------------------
# CSV de Unity: sobrescribir el angulo de un apoyo
# ---------------------------------------------------------------------------
def _ruta_csv(salida_excel):
    return str(assets_dir() / "coordenadas_linea.csv")


def _actualizar_angulo_csv(salida_excel, apoyo_numero, alfa):
    """Sobrescribe la columna 'Angulo' del apoyo en coordenadas_linea.csv
    (mantiene el resto de columnas y filas). Devuelve la ruta o None."""
    import csv as _csv
    ruta_csv = _ruta_csv(salida_excel)
    if not os.path.exists(ruta_csv):
        # Si falta el CSV, lo regeneramos desde las UTM actuales primero
        try:
            from generar_doc_utm import leer_utm_actual
            utm = leer_utm_actual(os.path.dirname(os.path.abspath(salida_excel)))
            if utm:
                ruta_utm = os.path.join(
                    os.path.dirname(os.path.abspath(salida_excel)),
                    "utm_editado.json")
                if not os.path.exists(ruta_utm):
                    ruta_utm = os.path.join(
                        os.path.dirname(os.path.abspath(salida_excel)),
                        "utm_tmp_angulo.json")
                    with open(ruta_utm, "w", encoding="utf-8") as f:
                        json.dump(utm, f, ensure_ascii=False)
                mv.regenerar_csv_linea(ruta_utm, ruta_csv)
        except Exception:
            return None

    if not os.path.exists(ruta_csv):
        return None

    with open(ruta_csv, "r", encoding="utf-8") as f:
        lineas = f.read().splitlines()
    header = lineas[0] if lineas else ""
    filas = []
    for linea in lineas[1:]:
        partes = linea.split(",")
        if len(partes) >= 5:
            try:
                if int(partes[0]) == int(apoyo_numero):
                    partes[4] = "%.3f" % alfa
            except ValueError:
                pass
        filas.append(",".join(partes))
    with open(ruta_csv, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        f.write("\n".join(filas) + "\n")
    return os.path.abspath(ruta_csv)


# ---------------------------------------------------------------------------
# CLI (JSON) para Unity
# ---------------------------------------------------------------------------
def procesar_peticion_json(ruta_peticion, ruta_resultado=None):
    with open(ruta_peticion, encoding="utf-8-sig") as archivo:
        p = json.load(archivo)
    try:
        excel = p["excel"]
        salida = p.get("salida_excel") or excel
        resultado = editar_angulo(excel, salida,
                                  int(p["apoyo"]), float(p["angulo"]),
                                  ruta_utm=p.get("utm"))
    except Exception as error:
        resultado = {"ok": False, "error": str(error)}
    if ruta_resultado:
        with open(ruta_resultado, "w", encoding="utf-8") as archivo:
            json.dump(resultado, archivo, ensure_ascii=False, indent=2,
                      default=str)
    return resultado


def procesar_listado_json(ruta_peticion, ruta_resultado=None):
    with open(ruta_peticion, encoding="utf-8-sig") as archivo:
        p = json.load(archivo)
    try:
        resultado = {"ok": True, "datos": listar_angulos(p["excel"])}
    except Exception as error:
        resultado = {"ok": False, "error": str(error)}
    if ruta_resultado:
        with open(ruta_resultado, "w", encoding="utf-8") as archivo:
            json.dump(resultado, archivo, ensure_ascii=False, indent=2,
                      default=str)
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

    if "--listado" in sys.argv:
        idx = sys.argv.index("--listado")
        ruta_peticion = sys.argv[idx + 1]
        ruta_resultado = None
        if "--resultado" in sys.argv:
            ruta_resultado = sys.argv[sys.argv.index("--resultado") + 1]
        print(json.dumps(procesar_listado_json(ruta_peticion, ruta_resultado),
                         ensure_ascii=False, indent=2, default=str))
    elif "--peticion" in sys.argv:
        idx = sys.argv.index("--peticion")
        ruta_peticion = sys.argv[idx + 1]
        ruta_resultado = None
        if "--resultado" in sys.argv:
            ruta_resultado = sys.argv[sys.argv.index("--resultado") + 1]
        print(json.dumps(procesar_peticion_json(ruta_peticion, ruta_resultado),
                         ensure_ascii=False, indent=2, default=str))
    else:
        print("Uso: py editar_angulo.py --listado p.json [--resultado r.json]")
        print("     py editar_angulo.py --peticion p.json [--resultado r.json]")
