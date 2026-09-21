# -*- coding: utf-8 -*-
"""
generar_graficos_utilizacion.py
===============================
Genera Assets/graficos_utilizacion.json para Unity.

Para cada apoyo de la linea calcula las rectas (a*L+b*N+c=0) del grafico de
utilizacion y la zona utilizable (izquierda y arriba), siguiendo la misma
convencion que el resto del proyecto (Python -> JSON -> Unity).

USO:
    py generar_graficos_utilizacion.py
"""
import json
import os

import datos_apoyos_excel as dae
import motor_graficos_utilizacion as motor
from twinelec_paths import assets_dir, data_dir

RUTA_EXCEL = str(data_dir() / "line_example.xlsx")
RUTA_SALIDA = str(assets_dir() / "graficos_utilizacion.json")


def _rectas_con_sentido(rectas):
    """Anade a cada recta el sentido utilizable:
       - hipotesis y vano maximo: 'left'  (L <= L_linea)
       - desviacion de cadena:    'above' (N >= N_linea)"""
    for clave, r in rectas.items():
        r["sentido"] = "above" if "desviacion" in clave else "left"
    return rectas


def calcular_zona_utilizable(rectas, n_lo=-1.0, n_hi=1.0, pasos=40):
    """Poligono (L, N) de la zona utilizable del grafico.

    La zona valida es la que cumple TODAS las restricciones:
      - lineas 'left'  (hipotesis, vano max):  L <= L_linea(N)
      - lineas 'above' (desviacion cadena):    N >= N_linea(L)
    Se muestrean N y L para construir el contorno del poligono.
    """
    import math

    left = []   # (funcion L(N))
    above = []  # (funcion N(L))
    for clave, r in rectas.items():
        if r.get("tipo") == "vertical":
            left.append(("vertical", r["L"]))
            continue
        a, b, c = r["a"], r["b"], r["c"]
        if r.get("sentido") == "above":
            if abs(b) > 1e-9:
                above.append(("linea", a, b, c))
        else:
            if abs(a) > 1e-9:
                left.append(("linea", a, b, c))

    def l_limite(n):
        """Minimo L permitido por las restricciones 'left'."""
        mejor = None
        for item in left:
            if item[0] == "vertical":
                l = item[1]
            else:
                _, a, b, c = item
                l = (-b * n - c) / a
            if mejor is None or l < mejor:
                mejor = l
        return mejor

    def n_limite(l):
        """Maximo N minimo exigido por las restricciones 'above'."""
        mejor = None
        for _, a, b, c in above:
            n = (-a * l - c) / b
            if mejor is None or n > mejor:
                mejor = n
        return mejor if mejor is not None else n_lo

    if not left:
        return []

    # limite inferior de N (en L=0) y superior de muestreo
    n_bajo = n_limite(0.0)
    if n_bajo < n_lo:
        n_bajo = n_lo
    l0 = l_limite(n_bajo)
    if l0 is None or l0 <= 0:
        return []

    # Poligono cerrado de la zona utilizable:
    #   - borde inferior:  N = N_limite(L), L en [0, l0]
    #   - borde derecho:   L = L_limite(N), N en [n_bajo, n_hi]
    #   - cierre por arriba y por la izquierda
    poligono = []
    for i in range(pasos + 1):
        l = l0 * i / pasos
        poligono.append((l, n_limite(l)))
    for i in range(1, pasos + 1):
        n = n_bajo + (n_hi - n_bajo) * i / pasos
        l = l_limite(n)
        if l is not None and l > 0:
            poligono.append((l, n))
    poligono.append((0.0, n_hi))
    poligono.append((0.0, n_bajo))
    return poligono


def generar_json(archivo_excel=RUTA_EXCEL, salida=RUTA_SALIDA,
                 viento_kmh=None, cadenas_por_apoyo=None):
    datos = dae.datos_completos_para_graficos(
        archivo_excel, viento_kmh=viento_kmh,
        cadenas_por_apoyo=cadenas_por_apoyo)

    apoyos_json = []
    for a in datos["apoyos"]:
        sob = datos["sobrecargas_por_zona"].get(a["zona"])
        rectas = motor.calcular_rectas_apoyo(
            a, sob, datos["conductor"], datos["viento_kmh"],
            datos["tension_linea_kv"])
        _rectas_con_sentido(rectas)
        zona_poly = calcular_zona_utilizable(rectas)

        apoyo = {
            "numero": a["numero"],
            "tipo": a["tipo_clave"],
            "tipo_texto": a["tipo_texto"],
            "zona": a["zona"],
            "zona_clave": a["zona_clave"],
            "montaje": a.get("montaje"),
            "angulo": a.get("angulo_sexagesimal"),
            "d1_m": a.get("d1_m"),
            "h_m": a.get("h_m"),
            "href_m": a.get("href_m"),
            "sep_conductores_m": a.get("sep_conductores_m"),
            "lcad_m": a.get("lcad_m"),
            "Fu_daN": a.get("Fu_daN"),
            "n_cadenas": a.get("n_cadenas"),
            "D_m": a.get("D_m"),
            "gammamax_grados": a.get("gammamax_grados"),
            "K_vano_maximo": a.get("K_vano_maximo"),
            "K_prima": a.get("K_prima"),
            "DPP_m": a.get("DPP_m"),
            "punto_real": {"L": a.get("L"), "N": a.get("N")},
            "punto_real_L": a.get("L"),
            "punto_real_N": a.get("N"),
            "rectas": rectas,
            "zona_utilizable": [list(p) for p in zona_poly],
        }
        apoyos_json.append(apoyo)

    # Orden estable por numero: el JSON debe quedar SIEMPRE correlacionado con
    # los PNG 'apoyo_N.png' y con la ventana Unity (que busca por numero), sea
    # cual sea el orden de las filas del Excel de origen.
    apoyos_json.sort(key=lambda a: (a.get("numero")
                                    if isinstance(a.get("numero"), (int, float)) else 0))

    documento = {
        "version_esquema": 1,
        "fuente_excel": os.path.basename(archivo_excel),
        "linea": {
            "conductor": datos["conductor"]["designacion"],
            "tension_linea_kv": datos["tension_linea_kv"],
            "categoria": datos["categoria"],
            "viento_kmh": datos["viento_kmh"],
            "zonas_de_tendido_m": datos["zonas_de_tendido_m"],
        },
        "apoyos": apoyos_json,
    }

    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)
    print("JSON generado en:", salida)
    print("Apoyos:", len(apoyos_json))
    return documento


if __name__ == "__main__":
    generar_json()
