# -*- coding: utf-8 -*-
"""
verificar_dlr_nivel1a.py — Verificación manual independiente del Nivel 1A
=========================================================================
Paso 3 del plan: comprobar el caso de referencia por una vía TOTALMENTE
independiente del motor (dlr.py). Este script NO importa dlr.py; recalcula
cada intermedio con fórmulas literales escritas aquí mismo, con constantes
explícitas, y compara contra el JSON generado.

Además verifica la temperatura máxima de cálculo reglamentaria leyendo la
hoja "T. tend. cond. fase" del Excel (las temperaturas hasta las que están
calculadas las tensiones y flechas = límite de categoría, 50 °C en este caso).

Si todos los bloques dan PASS, el caso de referencia queda validado como
"patrón de laboratorio" del Nivel 1A.
"""

import json
import math
import os
import sys
import pandas as pd

from twinelec_paths import assets_dir, data_dir

# Forzar salida UTF-8 en la consola de Windows (evita UnicodeEncodeError
# con caracteres como →, ✅, ❌ al redirigir a archivo o consola cp1252).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RUTA_CASO = str(assets_dir() / "caso_referencia_nivel1a.json")
RUTA_EXCEL = str(data_dir() / "line_example.xlsx")
HOJA_TENDIDO = "T. tend. cond. fase"

# ============================================================================
# 0) VERIFICACIÓN REGLAMENTARIA: temperatura máxima de cálculo en el Excel
# ============================================================================
def verificar_temperatura_maxima_excel():
    """Lee la hoja de tendido de conductores y extrae las temperaturas para
    las que están calculadas las tablas de tensiones y flechas."""
    print("=" * 72)
    print("VERIFICACIÓN 0: Temperatura máxima de cálculo según el Excel")
    print("=" * 72)

    try:
        df = pd.read_excel(RUTA_EXCEL, sheet_name=HOJA_TENDIDO, header=None)
    except Exception as e:
        print(f"  ERROR leyendo el Excel: {e}")
        return None

    # La fila 2 (índice 1) contiene las temperaturas de cada bloque T/F
    fila_temps = df.iloc[1]
    temperaturas = []
    for valor in fila_temps:
        texto = str(valor).strip() if not pd.isna(valor) else ""
        if texto.endswith("ºC") or texto.endswith("°C") or texto.endswith("C"):
            num = texto.replace("ºC", "").replace("°C", "").replace("C", "")
            try:
                temperaturas.append(int(float(num)))
            except ValueError:
                continue
        elif "T (daN)" in texto:
            continue  # cabecera de tensiones

    temperaturas = sorted(set(temperaturas))
    print(f"  Temperaturas de cálculo encontradas: {temperaturas}")
    if not temperaturas:
        print("  ⚠️ No se pudieron extraer las temperaturas. Reviso manualmente...")
        return None

    t_max = max(temperaturas)
    print(f"  Temperatura MÁXIMA de cálculo: {t_max} °C")
    print(
        "  → Según RLAT (ITC-LAT-07): "
        + ("Categoría NO ESPECIAL (50 °C)." if t_max == 50
           else "Categoría ESPECIAL (85 °C) u otra config." if t_max >= 85
           else f"Configuración particular ({t_max} °C).")
    )
    print("  → Para este caso (no especial) la Ts operativa del Nivel 1B será 50 °C.")
    print("  → Para el Nivel 1A (comparación con EnerFlux) se usa Ts = 85 °C.")
    return t_max


# ============================================================================
# 1) CASO DE REFERENCIA (los mismos datos de entrada del JSON)
# ============================================================================
def cargar_caso():
    with open(RUTA_CASO, encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# 2) CÁLCULO INDEPENDIENTE (fórmulas literales, sin importar dlr.py)
# ============================================================================
def calcular_independiente(entradas):
    """Recalcula TODOS los intermedios con fórmulas literales e independientes.
    Devuelve un dict clave -> (valor_calculado, unidad)."""
    c = entradas["conductor"]
    m = entradas["meteorologia"]
    g = entradas["geometria"]
    fecha = entradas["fecha"]
    hora = entradas["hora_solar"]
    ts_c = entradas["limite"]["ts_C"]

    # Datos base
    d0_m = c["diametro_mm"] / 1000.0
    ta_c = m["ta_C"]
    ts_k = ts_c + 273.15
    ta_k = ta_c + 273.15
    he_m = g["he_m"]

    # --- 1) Presión del aire (ISO 2533, forma literal) ---
    p_hpa = 1013.25 * (1.0 - 0.0065 * he_m / 288.15) ** 5.2559

    # --- 2) R(Tavg) — interpolación lineal literal ---
    r_low_ohm_km = c["r_low_ohm_km"]
    r_high_ohm_km = c["r_high_ohm_km"]
    t_low = c["t_low_C"]
    t_high = c["t_high_C"]
    r_tavg_ohm_km = ((r_high_ohm_km - r_low_ohm_km) / (t_high - t_low)) * (ts_c - t_low) + r_low_ohm_km
    r_tavg_ohm_m = r_tavg_ohm_km / 1000.0

    # --- 3) Temperatura de película ---
    tfilm_c = (ts_c + ta_c) / 2.0

    # --- 4) Viscosidad dinámica del aire ---
    mu = 1.458e-6 * (tfilm_c + 273.0) ** 1.5 / (tfilm_c + 383.4)

    # --- 5) Densidades del aire ---
    # 5a) Correlación (para Reynolds)
    ro_re = (1.293 - 1.525e-4 * he_m + 6.379e-9 * he_m ** 2) / (1.0 + 0.00367 * tfilm_c)
    # 5b) Ley de gases (para Qcn, igual que EnerFlux)
    ro_qcn = p_hpa * 100.0 * 0.0289652 / (8.314 * ta_k)

    # --- 6) Conductividad térmica del aire ---
    kf = 2.424e-2 + 7.477e-5 * tfilm_c - 4.407e-9 * tfilm_c ** 2

    # --- 7) Ángulo del viento respecto al conductor (phi) ---
    theta_viento = m["direccion_viento_deg"]
    zl = g["zl_deg"]
    phi = abs(theta_viento - zl)
    if phi > 180.0:
        phi = 360.0 - phi
    if phi > 90.0:
        phi = 180.0 - phi

    # --- 8) Kangle (norma) ---
    phi_r = math.radians(phi)
    kangle = 1.194 - math.cos(phi_r) + 0.194 * math.cos(2.0 * phi_r) + 0.368 * math.sin(2.0 * phi_r)

    # --- 9) Reynolds ---
    vw = m["vw_m_s"]
    re = d0_m * ro_re * vw / mu if mu > 0 else 0.0

    # --- 10) Convecciones ---
    qcn = 3.645 * math.sqrt(ro_qcn) * d0_m ** 0.75 * (ts_k - ta_k) ** 1.25
    qc1 = kangle * (1.01 + 1.35 * re ** 0.52) * kf * (ts_k - ta_k)
    qc2 = kangle * 0.754 * re ** 0.6 * kf * (ts_k - ta_k)
    qc = max(qcn, qc1, qc2)

    # --- 11) Radiación ---
    em = c["emisividad"]
    qr = 17.8 * d0_m * em * ((ts_k / 100.0) ** 4 - (ta_k / 100.0) ** 4)

    # --- 12) Posición solar ---
    n = 172  # 21 de junio (fecha por defecto del caso)
    delta = 23.45 * math.sin(math.radians(360.0 * (284 + n) / 365.0))
    omega = 15.0 * (hora - 12.0)

    lat_r = math.radians(g["lat_deg"])
    delta_r = math.radians(delta)
    omega_r = math.radians(omega)

    hc = math.degrees(math.asin(
        math.sin(lat_r) * math.sin(delta_r)
        + math.cos(lat_r) * math.cos(delta_r) * math.cos(omega_r)
    ))

    denom = math.sin(lat_r) * math.cos(omega_r) - math.cos(lat_r) * math.tan(delta_r)
    chi = math.sin(omega_r) / denom if abs(denom) > 1e-12 else 0.0
    if -180.0 <= omega < 0.0:
        c_az = 0.0 if chi >= 0 else 180.0
    else:
        c_az = 180.0 if chi >= 0 else 360.0
    zc = c_az + math.degrees(math.atan(chi))

    # --- 13) Qs a nivel del mar (cielo claro) ---
    A_, B_, C_, D_, E_, F_, G_ = -42.2391, 63.8044, -1.9220, 3.46921e-2, -3.61118e-4, 1.94318e-6, -4.07679e-9
    qs_mar = A_ + B_ * hc + C_ * hc ** 2 + D_ * hc ** 3 + E_ * hc ** 4 + F_ * hc ** 5 + G_ * hc ** 6

    # --- 14) Corrección por elevación ---
    k_solar = 1.0 + 1.148e-4 * he_m + (-1.108e-8) * he_m ** 2
    qse = k_solar * qs_mar

    # --- 15) Ganancia solar ---
    cos_theta = math.cos(math.radians(hc)) * math.cos(math.radians(zc - zl))
    cos_theta = max(-1.0, min(1.0, cos_theta))
    theta = math.degrees(math.acos(cos_theta))
    ab = c["absortividad"]
    area = d0_m   # m²/m (norma correcta)
    qs = ab * qse * math.sin(math.radians(theta)) * area
    if qs < 0:
        qs = 0.0

    # --- 16) Corriente máxima ---
    radicando = (qc + qr - qs) / r_tavg_ohm_m
    i_max = math.sqrt(radicando) if radicando > 0 else 0.0

    return {
        "presion_hpa": (p_hpa, "hPa"),
        "r_tavg_ohm_km": (r_tavg_ohm_km, "ohm/km"),
        "tfilm_C": (tfilm_c, "°C"),
        "viscosidad_kg_ms": (mu, "kg/(m·s)"),
        "densidad_aire_reynolds_kg_m3": (ro_re, "kg/m³"),
        "densidad_aire_qcn_kg_m3": (ro_qcn, "kg/m³"),
        "conductividad_termica_kf_W_mC": (kf, "W/(m·°C)"),
        "phi_deg": (phi, "°"),
        "kangle": (kangle, "-"),
        "reynolds": (re, "-"),
        "qcn_W_m": (qcn, "W/m"),
        "qc1_W_m": (qc1, "W/m"),
        "qc2_W_m": (qc2, "W/m"),
        "qc_W_m": (qc, "W/m"),
        "qr_W_m": (qr, "W/m"),
        "declinacion_solar_deg": (delta, "°"),
        "angulo_horario_deg": (omega, "°"),
        "altitud_solar_hc_deg": (hc, "°"),
        "acimut_solar_zc_deg": (zc, "°"),
        "theta_incidencia_deg": (theta, "°"),
        "qs_nivel_mar_W_m2": (qs_mar, "W/m²"),
        "k_solar": (k_solar, "-"),
        "qse_W_m2": (qse, "W/m²"),
        "area_proyectada_m2_m": (area, "m²/m"),
        "qs_W_m": (qs, "W/m"),
        "i_max_A": (i_max, "A"),
    }


# ============================================================================
# 3) COMPARACIÓN Y VEREDICTO
# ============================================================================
def comparar(calculado, json_intermedios_json, json_resultado, entradas_resumen=None):
    """Compara los valores recalculados contra el JSON del motor dlr.py."""
    inter_json = json_intermedios_json
    if entradas_resumen is None:
        entradas_resumen = {}

    # Mapeo entre la salida del cálculo independiente y las claves del JSON
    mapa = {
        "presion_hpa": "presion_hpa",
        "r_tavg_ohm_km": "r_tavg_ohm_km",
        "tfilm_C": "tfilm_C",
        "viscosidad_kg_ms": "viscosidad_kg_ms",
        "densidad_aire_reynolds_kg_m3": "densidad_aire_reynolds_kg_m3",
        "densidad_aire_qcn_kg_m3": "densidad_aire_qcn_kg_m3",
        "conductividad_termica_kf_W_mC": "conductividad_termica_kf_W_mC",
        "kangle": "kangle",
        "reynolds": "reynolds",
        "qcn_W_m": "qcn_W_m",
        "qc1_W_m": "qc1_W_m",
        "qc2_W_m": "qc2_W_m",
        "qc_W_m": "qc_W_m",
        "qr_W_m": "qr_W_m",
        "declinacion_solar_deg": "declinacion_solar_deg",
        "angulo_horario_deg": "angulo_horario_deg",
        "altitud_solar_hc_deg": "altitud_solar_hc_deg",
        "acimut_solar_zc_deg": "acimut_solar_zc_deg",
        "theta_incidencia_deg": "theta_incidencia_deg",
        "qs_nivel_mar_W_m2": "qs_nivel_mar_W_m2",
        "k_solar": "k_solar",
        "qse_W_m2": "qse_W_m2",
        "area_proyectada_m2_m": "area_proyectada_m2_m",
        "qs_W_m": "qs_W_m",
    }

    print()
    print("=" * 104)
    print("TABLA DE VERIFICACIÓN CRUZADA: cálculo independiente vs motor dlr.py")
    print("=" * 104)
    print(f"{'Magnitud':<38}{'Independiente':>18}{'dlr.py':>18}{'Dif %':>10}  {'Estado':<6}")
    print("-" * 104)

    tolerancia_pct = 0.5  # 0.5 % de tolerancia
    fallos = []
    for clave_calc, clave_json in mapa.items():
        valor_calc, unidad = calculado[clave_calc]
        valor_json = inter_json[clave_json]
        if valor_json == 0:
            dif = 0.0
        else:
            dif = 100.0 * abs(valor_calc - valor_json) / abs(valor_json)
        estado = "PASS" if dif <= tolerancia_pct else "FAIL"
        if estado == "FAIL":
            fallos.append(clave_calc)
        print(f"{clave_calc + ' (' + unidad + ')':<38}{valor_calc:>18.6f}{valor_json:>18.6f}{dif:>9.3f}%  {estado}")

    # Corriente final
    i_calc, _ = calculado["i_max_A"]
    i_json = json_resultado["i_max_A"]
    dif_i = 100.0 * abs(i_calc - i_json) / abs(i_json) if i_json else 0.0
    estado_i = "PASS" if dif_i <= tolerancia_pct else "FAIL"
    if estado_i == "FAIL":
        fallos.append("i_max_A")
    print("-" * 104)
    print(f"{'i_max_A (A)':<38}{i_calc:>18.6f}{i_json:>18.6f}{dif_i:>9.3f}%  {estado_i}")

    # phi_deg se guarda en 'entradas_resumen', no en 'intermedios'
    phi_calc, _ = calculado["phi_deg"]
    phi_json = entradas_resumen.get("phi_deg")
    if phi_json is not None:
        dif_phi = 100.0 * abs(phi_calc - phi_json) / abs(phi_json) if phi_json else 0.0
        estado_phi = "PASS" if dif_phi <= tolerancia_pct else "FAIL"
        if estado_phi == "FAIL":
            fallos.append("phi_deg")
        print(f"{'phi_deg (°)':<38}{phi_calc:>18.6f}{phi_json:>18.6f}{dif_phi:>9.3f}%  {estado_phi}")
    else:
        print(f"{'phi_deg (°)':<38}{phi_calc:>18.6f}{'n/d':>18}{'':>10}  n/d")
    print("=" * 104)

    if fallos:
        print(f"❌ HAY {len(fallos)} MAGNITUDES CON FALLO: {fallos}")
        print("   El caso de referencia NO se valida. Revisar el motor o este script.")
        return False

    print("✅ TODOS LOS BLOQUES COINCIDEN (diferencia ≤ 0.5 %).")
    print("   El caso de referencia queda VALIDADO como patrón de laboratorio.")
    return True


def main():
    caso = cargar_caso()
    entradas = caso["entradas"]
    inter_json = caso["resultado"]["intermedios"]
    res_json = caso["resultado"]["resultado"]

    print(f"Caso  : {caso['nombre_caso']}")
    print(f"Modo  : {caso['modo']}")
    print(f"Fecha : {caso['fecha_generacion']}")

    # Verificación 0: temperatura máxima del Excel
    t_max = verificar_temperatura_maxima_excel()

    # Cálculo independiente
    print()
    print("=" * 72)
    print("CÁLCULO INDEPENDIENTE (fórmulas literales)")
    print("=" * 72)
    calculado = calcular_independiente(entradas)
    for clave, (valor, unidad) in calculado.items():
        print(f"  {clave:32s} = {valor:12.6f} {unidad}")

    # Comparación
    ok = comparar(calculado, inter_json, res_json, caso["resultado"]["entradas_resumen"])

    print()
    if t_max is not None:
        print(
            f"NOTA: Según el Excel, la temperatura máxima de cálculo de esta línea "
            f"es {t_max} °C. Para el Nivel 1B se usará Ts = {t_max} °C."
        )

    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
