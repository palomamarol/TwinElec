# -*- coding: utf-8 -*-
"""
verificar_dlr_nivel2.py — Verificación contra el caso oficial de la IEEE 738
============================================================================
Paso del Nivel 2: ejecutar el motor DLR con el caso de validación publicado
en la norma IEEE 738-2023 (sección 4.6.1) y comparar TODOS los intermedios
contra los valores oficiales.

El caso oficial es un conductor 795 kcmil 26/7 Drake ACSR con:
    Vw = 0.61 m/s, phi = 90° (perpendicular), e = 0.8, a = 0.8,
    Ta = 40 °C, Ts = 100 °C, D0 = 28.14 mm,
    R(25 °C) = 7.283e-5 ohm/m, R(75 °C) = 8.688e-5 ohm/m,
    Zl = 90° (línea E-O), Lat = 30° N, aire claro, He = 0 m,
    fecha 10 de junio (N = 161), 11:00 a.m.

Valores oficiales publicados:
    qcn = 42.42 W/m, Re = 865, qc1 = 82.10 W/m, qc2 = 77.06 W/m,
    qc = 82.10 W/m, qr = 39.11 W/m, Qs = 1027 W/m², Hc = 74.9°,
    Zc = 114°, theta = 76.2°, qs = 22.45 W/m,
    R(100 °C) = 9.391e-5 ohm/m, I = 1025 A.

Si todos los bloques dan PASS con tolerancia razonable (<= 1%),
el motor queda VALIDADO CONTRA LA NORMA (estándar de oro).
"""

import sys
import json
import os
import math

import dlr
from twinelec_paths import assets_dir

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ============================================================================
# 1) DATOS DE ENTRADA DEL CASO OFICIAL (IEEE 738-2023, sección 4.6.1)
# ============================================================================
def caso_drake_oficial():
    """Construye las entradas del motor con los datos exactos de la norma."""
    conductor = {
        "designacion": "795 kcmil 26/7 Drake ACSR (caso oficial IEEE 738)",
        "diametro_mm": 28.14,
        "seccion_mm2": 402.6,           # 795 kcmil ~ 402.6 mm² (aprox)
        "composicion": "26/7",
        # La norma da R en ohm/m; el motor espera ohm/km y divide por 1000.
        "r_low_ohm_km": 7.283e-5 * 1000.0,   # R(25 °C) = 0.07283 ohm/km
        "r_high_ohm_km": 8.688e-5 * 1000.0,  # R(75 °C) = 0.08688 ohm/km
        "t_low_C": 25.0,
        "t_high_C": 75.0,               # La norma usa Thigh=75 °C para Tavg<=100
        "emisividad": 0.8,
        "absortividad": 0.8,
    }
    meteorologia = {
        "ta_C": 40.0,
        "vw_m_s": 0.61,
        # Para conseguir phi=90° con Zl=90°, el viento llega desde 180°.
        "direccion_viento_deg": 180.0,  # 180 - 90 = 90 => phi = 90°
    }
    geometria = {
        "he_m": 0.0,        # nivel del mar
        "lat_deg": 30.0,    # 30° North
        "zl_deg": 90.0,     # línea este-oeste
    }
    entradas = {
        "conductor": conductor,
        "meteorologia": meteorologia,
        "geometria": geometria,
        "fecha": "2025-06-10",   # N = 161
        "hora_solar": 11.0,      # 11:00 a.m. => omega = -15°
        "limite": {"ts_C": 100.0},
    }
    return entradas


# ============================================================================
# 2) VALORES ESPERADOS PUBLICADOS EN LA NORMA
# ============================================================================
def valores_oficiales():
    """Valores de referencia publicados en IEEE 738-2023 sección 4.6.1."""
    return [
        # (clave intermedio, valor oficial, unidad, tolerancia %)
        ("r_tavg_ohm_m", 9.391e-5, "ohm/m", 0.5),
        ("densidad_aire_qcn_kg_m3", 1.029, "kg/m³", 1.0),
        ("viscosidad_kg_ms", 2.043e-5, "kg/(m·s)", 1.0),
        ("conductividad_termica_kf_W_mC", 0.02945, "W/(m·°C)", 1.0),
        ("reynolds", 865.0, "-", 1.0),
        ("qcn_W_m", 42.42, "W/m", 1.0),
        ("qc1_W_m", 82.10, "W/m", 1.0),
        ("qc2_W_m", 77.06, "W/m", 1.0),
        ("qc_W_m", 82.10, "W/m", 1.0),
        ("qr_W_m", 39.11, "W/m", 1.0),
        ("declinacion_solar_deg", 23.0, "°", 1.5),
        ("angulo_horario_deg", -15.0, "°", 0.1),
        ("altitud_solar_hc_deg", 74.9, "°", 1.0),
        ("acimut_solar_zc_deg", 114.0, "°", 2.0),
        ("theta_incidencia_deg", 76.2, "°", 1.0),
        ("qs_nivel_mar_W_m2", 1027.0, "W/m²", 1.0),
        ("qs_W_m", 22.45, "W/m", 1.5),
    ]


# ============================================================================
# 3) COMPARACIÓN Y VEREDICTO
# ============================================================================
def main():
    print("=" * 100)
    print("NIVEL 2 — VERIFICACIÓN CONTRA EL CASO OFICIAL DE LA IEEE 738-2023")
    print("Conductor: 795 kcmil 26/7 Drake ACSR (sección 4.6.1 de la norma)")
    print("=" * 100)

    entradas = caso_drake_oficial()
    resultado = dlr.calcular_dlr(entradas, modo="ieee738")
    inter = resultado["intermedios"]
    res = resultado["resultado"]

    print("\nEntradas del caso:")
    print(f"  Ts = {entradas['limite']['ts_C']:.0f} °C, Ta = {entradas['meteorologia']['ta_C']:.0f} °C")
    print(f"  Vw = {entradas['meteorologia']['vw_m_s']:.2f} m/s, phi = 90°")
    print(f"  D0 = {entradas['conductor']['diametro_mm']:.2f} mm, Zl = 90°, Lat = 30° N")
    print(f"  Fecha = {entradas['fecha']} (N=161), Hora = 11:00, He = 0 m")
    print(f"  R(25°C) = {7.283e-5:.3e} ohm/m, R(75°C) = {8.688e-5:.3e} ohm/m")

    print("\n" + "=" * 100)
    print("TABLA DE VERIFICACIÓN: motor DLR vs valores oficiales IEEE 738-2023")
    print("=" * 100)
    print(f"{'Magnitud':<38}{'Motor DLR':>16}{'Oficial':>14}{'Dif %':>9}  Estado")
    print("-" * 100)

    fallos = []
    for clave, oficial, unidad, tol in valores_oficiales():
        valor_calc = inter[clave]
        if oficial == 0:
            dif = 0.0
        else:
            dif = 100.0 * abs(valor_calc - oficial) / abs(oficial)
        estado = "PASS" if dif <= tol else "FAIL"
        if estado == "FAIL":
            fallos.append(clave)
        print(f"{clave + ' (' + unidad + ')':<38}{valor_calc:>16.6f}{oficial:>14.6f}{dif:>8.3f}%  {estado}")

    # Corriente final
    i_calc = res["i_max_A"]
    i_oficial = 1025.0
    dif_i = 100.0 * abs(i_calc - i_oficial) / i_oficial
    estado_i = "PASS" if dif_i <= 1.0 else "FAIL"
    if estado_i == "FAIL":
        fallos.append("i_max_A")
    print("-" * 100)
    print(f"{'i_max_A (A)':<38}{i_calc:>16.2f}{i_oficial:>14.2f}{dif_i:>8.2f}%  {estado_i}")
    print("=" * 100)

    if fallos:
        print(f"\n❌ HAY {len(fallos)} MAGNITUDES CON FALLO: {fallos}")
        print("   Revisar el motor en esos bloques.")
        return 1

    print("\n✅ TODOS LOS BLOQUES COINCIDEN con el caso oficial de la norma.")
    print("   El motor DLR queda VALIDADO CONTRA IEEE 738-2023 (estándar de oro).")

    # Guardar resultados en JSON
    ruta_salida = str(assets_dir() / "verificacion_nivel2.json")
    documento = {
        "nombre": "Verificación Nivel 2 - Caso oficial IEEE 738-2023",
        "conductor": "795 kcmil 26/7 Drake ACSR",
        "entradas": entradas,
        "resultado_motor": resultado,
        "valores_oficiales": valores_oficiales(),
        "corriente_oficial_A": i_oficial,
        "veredicto": "PASS todos los bloques" if not fallos else f"FALLOS: {fallos}",
    }
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en {ruta_salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
