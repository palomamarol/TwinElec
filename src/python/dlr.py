# -*- coding: utf-8 -*-
"""
dlr.py — Motor de cálculo DLR (Dynamic Line Rating) basado en IEEE Std 738-2023
===============================================================================
Módulo del Nivel 1A del plan de aplicación del DLR al gemelo digital (Unity).

Este archivo es un MOTOR DE CÁLCULO PURO Y GENÉRICO: no conoce ninguna línea
concreta (ni una ubicación, ni un conductor, ni un Excel). Recibe propiedades del
conductor, meteorología, geometría y posición, y devuelve la corriente máxima
admisible junto con TODOS los resultados intermedios del balance térmico.

Dos modos de cálculo:
    - "ieee738" : implementación literal de la norma IEEE 738-2023
                  (referencia de laboratorio del Nivel 1A).
    - "enerflux": réplica del comportamiento exacto de EnerFlux (main1.py del
                  TFG de Manuel), con sus bugs incluidos, para comparación
                  en el Nivel 2.

Balance térmico en régimen estacionario (steady-state):

        qc + qr = qs + I^2 * R(Tavg)      =>      I = sqrt((qc+qr-qs)/R(Tavg))

FUNCIONES PÚBLICAS DE ALTO NIVEL
---------------------------------
    calcular_dlr(entradas, modo="ieee738")
        Calcula un caso DLR completo y devuelve un dict con todos los intermedios.

    generar_caso_referencia(...)
        Genera el JSON del caso de referencia a partir de datos genéricos
        (los mismos que extrae principal.py de cualquier Excel/.doc).

    calcular_r(conductor, ts_C, ...)
        Interpolación lineal de R(T) (función auxiliar exportada).

Referencias:
    - IEEE Std 738-2023 "IEEE Standard for Calculating the Current-Temperature
      Relationship of Bare Overhead Conductors".
    - Pérez Ayuso, M.A. (2025). "Modelo de predicción y optimización de una
      línea eléctrica aérea basada en las condiciones climáticas". TFG. EPS Jaén.
    - ISO 2533:1975 "Standard Atmosphere" (presión del aire).

Versión: 1.0 (Nivel 1A). Autoría: TwinElec (Unity Digital Twin).
"""

import math
import json
import os
import sys
from datetime import datetime

from twinelec_paths import assets_dir, data_dir

# Forzar salida UTF-8 en la consola de Windows (evita UnicodeEncodeError con
# emojis/acentos al redirigir la salida a archivo o en consolas cp1252).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pandas as pd
except ImportError:
    pd = None  # La detección de T_máx del Excel requiere pandas

# ============================================================================
# CONSTANTES FÍSICAS Y COEFICIENTES DE LA NORMA
# ============================================================================

# Aire / atmósfera estándar ISO 2533
PRESION_ATM_HPA = 1013.25          # hPa
BETA_TROPOSFERA = 0.0065           # K/m (gradiente térmico de la troposfera)
TB_TROPOSFERA = 288.15             # K   (temperatura base de la troposfera)
GRAVEDAD = 9.81                    # m/s²
R_GAS = 8.314                      # J/(mol·K)  (constante usada por EnerFlux)
M_AIRE = 0.0289652                 # kg/mol     (masa molar usada por EnerFlux)

# Coeficientes del polinomio Qs (intensidad solar a nivel del mar, W/m²) para
# cielo claro (cielo = 0).  Fuente: IEEE 738 / main1.py de EnerFlux.
# NOTA: el coeficiente G usa el valor de la norma IEEE 738-2023
# (Tabla 4, -4.07608e-9).  EnerFlux usaba -4.07679e-9 (valor de una
# versión anterior); la diferencia es insignificante pero para reproducir
# exactamente el caso de validación oficial se usa el valor de la 2023.
COEF_QS_CIELO_CLARO = {
    "A": -42.2391,
    "B": 63.8044,
    "C": -1.9220,
    "D": 3.46921e-2,
    "E": -3.61118e-4,
    "F": 1.94318e-6,
    "G": -4.07608e-9,
}

# Coeficientes de la corrección por elevación de la intensidad solar (Ksolar):
#   - K_SOLAR_B y K_SOLAR_C se aplican de una u otra forma según el modo.
K_SOLAR_B = 1.148e-4
K_SOLAR_C = -1.108e-8

# Elipsoide WGS84 para conversión UTM -> lat/lon (a falta de la librería utm)
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
WGS84_K0 = 0.9996


# ============================================================================
# UTILIDADES GEOMÉTRICAS, DE TIEMPO Y DE CATÁLOGO
# ============================================================================

def utm_a_latlon(x, y, huso, hemisferio="N"):
    """Convierte coordenadas UTM (WGS84) a latitud/longitud en grados.

    Parámetros
    ----------
    x : float        Coordenada Este  UTM (m).
    y : float        Coordenada Norte UTM (m).
    huso : int       Número de huso UTM (p.ej. 30 para España peninsular).
    hemisferio : str "N" (norte) o "S" (sur).

    Devuelve
    --------
    (lat_deg, lon_deg) : tupla de floats en grados decimales.
    """
    if hemisferio.upper() == "S":
        y = y - 10000000.0

    a = WGS84_A
    e2 = WGS84_E2
    ep2 = e2 / (1.0 - e2)
    k0 = WGS84_K0
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))

    # Meridiano central del huso (grados)
    lon_central = -183.0 + 6.0 * huso

    # Arco meridional -> latitud "pie" (footpoint)
    m = y / k0
    mu = m / (a * (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * e2 ** 3 / 256.0))
    phi1 = (mu
            + (3.0 * e1 / 2.0 - 27.0 * e1 ** 3 / 32.0) * math.sin(2.0 * mu)
            + (21.0 * e1 ** 2 / 16.0 - 55.0 * e1 ** 4 / 32.0) * math.sin(4.0 * mu)
            + (151.0 * e1 ** 3 / 96.0) * math.sin(6.0 * mu)
            + (1097.0 * e1 ** 4 / 512.0) * math.sin(8.0 * mu))

    c1 = ep2 * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = a / math.sqrt(1.0 - e2 * math.sin(phi1) ** 2)
    r1 = a * (1.0 - e2) / (1.0 - e2 * math.sin(phi1) ** 2) ** 1.5
    # IMPORTANTE: la coordenada X UTM es un valor absoluto con falso este de
    # 500 000 m. Para el cálculo de la longitud hay que restar el falso este.
    # (Este bug no se notaba antes porque el DLR solo usaba la latitud; la
    # longitud es necesaria para localizar estaciones meteorológicas.)
    falso_este = 500000.0
    d = (x - falso_este) / (n1 * k0)

    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2.0
        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 ** 2 - 9.0 * ep2) * d ** 4 / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 ** 2
           - 252.0 * ep2 - 3.0 * c1 ** 2) * d ** 6 / 720.0
    )
    lon = (d
           - (1.0 + 2.0 * t1 + c1) * d ** 3 / 6.0
           + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 ** 2
              + 24.0 * t1 ** 2) * d ** 5 / 120.0
           ) / math.cos(phi1)

    return math.degrees(lat), lon_central + math.degrees(lon)


def dia_del_ano(fecha_str):
    """Día del año (1..366) para una fecha 'YYYY-MM-DD' o 'YYYY/MM/DD'."""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(fecha_str, fmt).timetuple().tm_yday
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no reconocido: {fecha_str}")


def normalizar_angulo_viento_conductor(theta_viento, theta_conductor):
    """Ángulo phi (0..90) entre la dirección del viento y el eje del conductor.

    phi = 0  -> viento paralelo al conductor (peor refrigeración).
    phi = 90 -> viento perpendicular (mejor refrigeración).
    Devuelve None si theta_viento es None (calma / sin viento).
    """
    if theta_viento is None:
        return None
    phi = abs(theta_viento - theta_conductor)
    if phi > 180.0:
        phi = 360.0 - phi
    if phi > 90.0:
        phi = 180.0 - phi
    return phi


def orientacion_primer_vano(apoyos_utm):
    """Acimut de la línea (Zl, grados desde el Norte) del primer vano a partir
    de los dos primeros apoyos UTM, con la misma convención que EnerFlux:
        deltaE = atan2(dy, dx);  deltaN = 90 - deltaE;  normalizado a [0,360)"""
    if len(apoyos_utm) < 2:
        return 0.0
    p1 = apoyos_utm[0]
    p2 = apoyos_utm[1]
    dx = float(p2["x"]) - float(p1["x"])
    dy = float(p2["y"]) - float(p1["y"])
    delta_e = math.degrees(math.atan2(dy, dx))
    delta_n = 90.0 - delta_e
    if delta_n < 0.0:
        delta_n += 360.0
    # Normalizar a [0, 360)
    delta_n = delta_n % 360.0
    return delta_n


def altitud_media(apoyos_utm):
    """Altitud media (m) de las cotas de los apoyos."""
    if not apoyos_utm:
        return 0.0
    return sum(float(p.get("cota", 0.0)) for p in apoyos_utm) / len(apoyos_utm)


def latitud_media(apoyos_utm, huso, hemisferio="N"):
    """Latitud media (grados) de los apoyos UTM."""
    if not apoyos_utm:
        return 0.0
    lats = [
        utm_a_latlon(float(p["x"]), float(p["y"]), huso, hemisferio)[0]
        for p in apoyos_utm
    ]
    return sum(lats) / len(lats)


def intensidad_reglamento(seccion_mm2, codigo_antiguo, composicion=None):
    """Calcula la intensidad máxima admisible por el RLAT (reglamento).

    Corresponde al apartado 8.1.3 de EnerFlux (main1.py): densidad de
    corriente máxima de la tabla 5 del RLAT (ITC-LAT-07) en función del
    material y la sección, corregida por el factor de composición.

    Parámetros
    ----------
    seccion_mm2 : float
        Sección total del conductor (mm²).
    codigo_antiguo : str
        Código antiguo del conductor (p.ej. 'LA-56', 'DA 110', 'LARL 56'...).
    composicion : str | None
        Composición (p.ej. '6+1', '30+7'). Si es None, factor = 1.

    Devuelve
    --------
    dict con {densidad_A_mm2, factor_reduccion, intensidad_A} o error.
    """
    # Tabla 5 del RLAT: [Sección (mm²), Cobre, Aluminio, Aleación de aluminio]
    tabla_rlat = [
        [10, 8.75, None, None],
        [15, 7.60, 6.00, 5.60],
        [25, 6.35, 5.00, 4.65],
        [35, 5.75, 4.55, 4.25],
        [50, 5.10, 4.00, 3.70],
        [70, 4.50, 3.55, 3.30],
        [95, 4.05, 3.20, 3.00],
        [125, 3.70, 2.90, 2.70],
        [160, 3.40, 2.70, 2.50],
        [200, 3.20, 2.50, 2.30],
        [250, 2.90, 2.30, 2.15],
        [300, 2.75, 2.15, 2.00],
        [400, 2.50, 1.95, 1.80],
        [500, 2.30, 1.80, 1.70],
        [600, 2.10, 1.65, 1.55],
    ]

    # Índice de columna según el prefijo del código antiguo (robusto)
    codigo_mayus = (codigo_antiguo or "").upper().replace(" ", "")
    indice_material = None
    if codigo_mayus.startswith("LARL"):
        indice_material = 3  # aleación de aluminio-acero
    elif codigo_mayus.startswith("DA"):
        indice_material = 3  # aleación de aluminio-acero
    elif codigo_mayus.startswith("D"):
        indice_material = 3  # aleación de aluminio
    elif codigo_mayus.startswith("LA"):
        indice_material = 3  # aluminio-acero (se toma como aleación de aluminio)
    elif codigo_mayus.startswith("L"):
        indice_material = 2  # aluminio
    else:
        return {"error": f"Material no reconocido para '{codigo_antiguo}'"}

    # Buscar la sección inmediatamente superior
    densidad = None
    for fila in tabla_rlat:
        if fila[0] >= seccion_mm2:
            densidad = fila[indice_material]
            break
    if densidad is None:
        densidad = tabla_rlat[-1][indice_material]  # última fila

    # Factor de reducción por composición (RLAT 4.2.1)
    factor = 1.0
    comp = (composicion or "").replace(" ", "")
    if comp == "30+7":
        factor = 0.916
    elif comp in ("6+1", "26+7"):
        factor = 0.937
    elif comp == "54+7":
        factor = 0.95
    elif comp == "45+7":
        factor = 0.97

    densidad_corregida = densidad * factor
    intensidad = densidad_corregida * seccion_mm2

    return {
        "seccion_mm2": seccion_mm2,
        "material": codigo_mayus[:2] if len(codigo_mayus) >= 2 else codigo_mayus,
        "densidad_tabla_A_mm2": densidad,
        "factor_reduccion": factor,
        "densidad_corregida_A_mm2": densidad_corregida,
        "intensidad_reglamento_A": intensidad,
    }


def detectar_temperatura_maxima_excel(ruta_excel, hoja_tendido="T. tend. cond. fase"):
    """Detecta la temperatura máxima de cálculo de CUALQUIER Excel de línea.

    Lee la cabecera de la hoja de tendido de conductores (la que contiene las
    tablas de tensiones y flechas por temperatura) y extrae todas las
    temperaturas para las que está calculada. La máxima es la temperatura
    límite operativa real de la línea según el RLAT (categoría no especial
    50 °C, categoría especial 85 °C, u otra configuración particular).

    Parámetros
    ----------
    ruta_excel : str
        Ruta al archivo .xlsx de la línea (cualquiera).
    hoja_tendido : str
        Nombre de la hoja de tendido (por defecto "T. tend. cond. fase",
        que es la hoja estándar de los Excel tipo Andel).

    Devuelve
    --------
    float con la temperatura máxima en °C, o None si no se pudo detectar.

    Nota: esta es la pieza clave que hace el sistema GENÉRICO: el límite
    térmico NO se fija a 50 ni a 85 en el código; se detecta de cada Excel.
    """
    if pd is None:
        print("  ⚠️ pandas no disponible: no se puede detectar T_máx del Excel.")
        return None

    try:
        df = pd.read_excel(ruta_excel, sheet_name=hoja_tendido, header=None)
    except Exception as e:
        print(f"  ⚠️ No se pudo leer la hoja '{hoja_tendido}' de {ruta_excel}: {e}")
        return None

    # Se recorre la primera fila de cabeceras (y las siguientes si hiciera
    # falta) buscando etiquetas de temperatura del tipo "-5ºC", "0ºC", "50ºC".
    temperaturas = []
    for indice_fila in range(min(5, df.shape[0])):
        fila = df.iloc[indice_fila]
        for valor in fila:
            if pd.isna(valor):
                continue
            texto = str(valor).strip()
            # Patrones: "-5ºC", "0°C", "T (daN)" (cabecera de tensión)
            for sufijo in ("ºC", "°C", "C"):
                if texto.endswith(sufijo) and len(texto) > len(sufijo):
                    num_texto = texto[:-len(sufijo)].strip()
                    try:
                        temperaturas.append(float(num_texto))
                    except ValueError:
                        pass
                    break

    if not temperaturas:
        print(
            f"  ⚠️ No se encontraron temperaturas en la hoja '{hoja_tendido}' "
            f"de {ruta_excel}. Se usará 85 °C por defecto (categoría especial)."
        )
        return None

    t_max = max(temperaturas)
    print(f"  -> T_máx detectada del Excel = {t_max:.0f} °C "
          f"(temperaturas: {sorted(set(temperaturas))})")
    return t_max


# ============================================================================
# BLOQUES DE CÁLCULO DE LA IEEE 738
# ============================================================================

def presion_aire(he_m):
    """Presión atmosférica (hPa) según ISO 2533 (ec. 12, sección 27):
    p = p_atm * [1 + beta/Tb * (H-Hb)]^(-gn/(beta*R))
    Expresión equivalente usada por EnerFlux (main1.py):
    p = 1013.25 * (1 - 0.0065*He/288.15)^5.2559
    """
    return PRESION_ATM_HPA * (1.0 - BETA_TROPOSFERA * he_m / TB_TROPOSFERA) ** 5.2559


def resistencia_conductor(r_low, r_high, t_low, t_high, t_avg):
    """Interpolación lineal de R(T) (IEEE 738, apartado 4.4.6):
        R(Tavg) = (R(Thigh)-R(Tlow))/(Thigh-Tlow) * (Tavg-Tlow) + R(Tlow)
    Entradas y salida en ohm/m (convertir desde ohm/km antes de llamar).
    """
    if t_high == t_low:
        return (r_low + r_high) / 2.0
    return ((r_high - r_low) / (t_high - t_low)) * (t_avg - t_low) + r_low


def viscosidad_aire(tfilm_c):
    """Viscosidad dinámica del aire (kg/(m·s)) a Tfilm:
        mu = 1.458e-6 * (Tfilm+273)^1.5 / (Tfilm+383.4)"""
    return (1.458e-6 * (tfilm_c + 273.0) ** 1.5) / (tfilm_c + 383.4)


def densidad_aire_correlacion(he_m, tfilm_c):
    """Densidad del aire (kg/m³) por correlación con altitud y Tfilm
    (IEEE 738, sección 6.2.4.2), usada para el número de Reynolds:
        ro = (1.293 - 1.525e-4*He + 6.379e-9*He^2) / (1 + 0.00367*Tfilm)"""
    return (
        (1.293 - 1.525e-4 * he_m + 6.379e-9 * he_m ** 2)
        / (1.0 + 0.00367 * tfilm_c)
    )


def densidad_aire_ley_gases(p_hpa, ta_k):
    """Densidad del aire (kg/m³) por ley de gases (usada por EnerFlux para la
    convección natural):  ro = p*100*M/(R*T)"""
    return p_hpa * 100.0 * M_AIRE / (R_GAS * ta_k)


def conductividad_termica_aire(tfilm_c):
    """Conductividad térmica del aire (W/(m·°C)):
        kf = 2.424e-2 + 7.477e-5*Tfilm - 4.407e-9*Tfilm^2"""
    return 2.424e-2 + 7.477e-5 * tfilm_c - 4.407e-9 * tfilm_c ** 2


def numero_reynolds(d0_m, ro, vw, mu):
    """Número de Reynolds:  Re = D0*ro*vw/mu"""
    if mu <= 0.0:
        return 0.0
    return d0_m * ro * vw / mu


def factor_direccion_viento(phi_deg, modo="ieee738"):
    """Factor de dirección del viento Kangle (adimensional).

    - modo "ieee738" (norma, sección 6.2.5):
        Kangle = 1.194 - cos(phi) + 0.194*cos(2*phi) + 0.368*sin(2*phi)
    - modo "enerflux" (BUG de main1.py de EnerFlux, línea 174):
        Kangle = 1.194 - sin(phi) - 0.194*cos(2*phi) + 0.368*sin(2*phi)

    Nota: con phi=90° (viento perpendicular) la norma da 1.000;
    EnerFlux da aproximadamente 0.388 (error del código).
    """
    phi_r = math.radians(phi_deg)
    if modo == "enerflux":
        return 1.194 - math.sin(phi_r) - 0.194 * math.cos(2.0 * phi_r) \
            + 0.368 * math.sin(2.0 * phi_r)
    return 1.194 - math.cos(phi_r) + 0.194 * math.cos(2.0 * phi_r) \
        + 0.368 * math.sin(2.0 * phi_r)


def conveccion_natural(d0_m, ro_qcn, ts_k, ta_k):
    """Convección natural (W/m), IEEE 738 sección 6.2.1:
        qcn = 3.645 * ro^0.5 * D0^0.75 * (Ts-Ta)^1.25"""
    return 3.645 * math.sqrt(ro_qcn) * d0_m ** 0.75 * (ts_k - ta_k) ** 1.25


def conveccion_forzada(qc1, qc2):
    """Devuelve la convección forzada elegida: la mayor de qc1 y qc2
    (IEEE 738 sección 6.2.2)."""
    return max(qc1, qc2)


def perdida_radiacion(d0_m, emisividad, ts_k, ta_k):
    """Pérdida de calor por radiación (W/m), IEEE 738 sección 6.3 (ley de
    Stefan-Boltzmann en forma compacta para uso directo en Kelvin):
        qr = 17.8 * D0 * e * ((Ts/100)^4 - (Ta/100)^4)   con T en Kelvin."""
    return 17.8 * d0_m * emisividad * ((ts_k / 100.0) ** 4 - (ta_k / 100.0) ** 4)


def posicion_solar(lat_deg, n, hora_solar):
    """Cálculo de la posición solar (IEEE 738, sección 6.4):
        delta : declinación solar (grados)
        omega : ángulo horario (grados)
        Hc    : altitud solar (grados)
        chi   : variable auxiliar para el acimut
        Zc    : acimut solar (grados, desde el Norte)
    Devuelve un dict con (delta_deg, omega_deg, hc_deg, zc_deg).
    """
    delta = 23.45 * math.sin(math.radians(360.0 * (284 + n) / 365.0))
    omega = 15.0 * (hora_solar - 12.0)

    lat_r = math.radians(lat_deg)
    delta_r = math.radians(delta)
    omega_r = math.radians(omega)

    # Altitud solar Hc
    hc = math.degrees(math.asin(
        math.sin(lat_r) * math.sin(delta_r)
        + math.cos(lat_r) * math.cos(delta_r) * math.cos(omega_r)
    ))

    # Variable auxiliar chi
    denominador = (math.sin(lat_r) * math.cos(omega_r)
                   - math.cos(lat_r) * math.tan(delta_r))
    if abs(denominador) < 1e-12:
        chi = 0.0
    else:
        chi = math.sin(omega_r) / denominador

    # Constante C en función del signo de omega y chi (IEEE 738, tabla 3)
    if -180.0 <= omega < 0.0:
        c_az = 0.0 if chi >= 0.0 else 180.0
    elif 0.0 <= omega < 180.0:
        c_az = 180.0 if chi >= 0.0 else 360.0
    else:
        c_az = 0.0

    zc = c_az + math.degrees(math.atan(chi))
    return {"delta_deg": delta, "omega_deg": omega, "hc_deg": hc, "zc_deg": zc}


def intensidad_solar_nivel_mar(hc_deg):
    """Intensidad total del calor irradiado por el sol y el cielo a nivel del
    mar (W/m²) para cielo claro (coeficientes IEEE 738, sección 6.4):
        Qs = A + B*Hc + C*Hc^2 + D*Hc^3 + E*Hc^4 + F*Hc^5 + G*Hc^6"""
    c = COEF_QS_CIELO_CLARO
    h = hc_deg
    return (c["A"] + c["B"] * h + c["C"] * h ** 2 + c["D"] * h ** 3
            + c["E"] * h ** 4 + c["F"] * h ** 5 + c["G"] * h ** 6)


def correccion_altitud_solar(qs, he_m, modo="ieee738"):
    """Corrige la intensidad solar a la elevación real del apoyo:
        Qse = Ksolar * Qs
        Ksolar = 1 + 1.148e-4*He - 1.108e-8*He^2   (IEEE 738)
        Ksolar = 1 + 1.148e-4*He - 1.108e-8*He    (BUG de EnerFlux)
    Devuelve (Qse, Ksolar)."""
    if modo == "enerflux":
        k_solar = 1.0 + K_SOLAR_B * he_m + K_SOLAR_C * he_m
    else:
        k_solar = 1.0 + K_SOLAR_B * he_m + K_SOLAR_C * he_m ** 2
    return k_solar * qs, k_solar


def ganancia_solar(alpha, qse, hc_deg, zc_deg, zl_deg, d0_m, modo="ieee738"):
    """Ganancia de calor solar (W/m), IEEE 738 sección 6.4:
        theta = arccos(cos(Hc)*cos(Zc-Zl))
        qs = alpha * Qse * sin(theta) * A'
    donde A' es el área proyectada del conductor por unidad de longitud:
        - "ieee738" : A' = D0 (m²/m)              <- norma correcta
        - "enerflux": A' = seccion_mm2/1e6 (m²/m) <- BUG de EnerFlux

    Se escoge el theta que hace sin(theta) máximo (más cercano a 90°), que es
    el caso más conservador (mayor qs posible), igual que hace EnerFlux.
    Devuelve (qs, theta_sel_deg).
    """
    cos_theta = (math.cos(math.radians(hc_deg))
                 * math.cos(math.radians(zc_deg - zl_deg)))
    cos_theta = max(-1.0, min(1.0, cos_theta))  # clamp numérico
    theta = math.degrees(math.acos(cos_theta))

    # Selección conservadora: ángulo más cercano a 90° (seno máximo)
    theta_sel = theta
    for candidato in (theta, 180.0 - theta, theta + 360.0, 180.0 - theta + 360.0):
        if abs(candidato - 90.0) < abs(theta_sel - 90.0):
            theta_sel = candidato
    theta_sel = theta_sel % 360.0

    sin_theta = math.sin(math.radians(theta_sel))
    qs = alpha * qse * sin_theta * d0_m
    if qs < 0.0:
        qs = 0.0
    return qs, theta_sel


# ============================================================================
# CÁLCULO COMPLETO DEL DLR (STEADY-STATE) — Paso 1
# ============================================================================

def calcular_dlr(entradas, modo="ieee738"):
    """Calcula la corriente máxima admisible (IEEE 738 steady-state) y todos
    los resultados intermedios.

    Parámetros
    ----------
    entradas : dict
        {
            "conductor": {
                "designacion": str,
                "diametro_mm": float,
                "seccion_mm2": float,
                "composicion": str,
                "r_low_ohm_km": float,   # R(Tlow) en ohm/km
                "r_high_ohm_km": float,  # R(Thigh) en ohm/km
                "t_low_C": float,        # Tlow (por defecto 25)
                "t_high_C": float,       # Thigh (por defecto 70)
                "emisividad": float,     # 0..1
                "absortividad": float,   # 0..1
            },
            "meteorologia": {
                "ta_C": float,                  # temperatura ambiente (°C)
                "vw_m_s": float,                # velocidad del viento (m/s)
                "direccion_viento_deg": float,  # dirección viento (deg, desde Norte)
            },
            "geometria": {
                "he_m": float,     # altitud del apoyo (m)
                "lat_deg": float,  # latitud (deg)
                "zl_deg": float,   # acimut de la línea (deg, desde Norte)
            },
            "fecha": "YYYY-MM-DD",   # día del año N
            "hora_solar": float,     # hora solar (12 = mediodía)
            "limite": {"ts_C": float},  # temperatura máxima del conductor (°C)
        }
    modo : str
        "ieee738" (norma, referencia) o "enerflux" (réplica EnerFlux).

    Devuelve
    --------
    dict con todas las magnitudes intermedias y la corriente final (A).
    """
    c = entradas["conductor"]
    m = entradas["meteorologia"]
    g = entradas["geometria"]
    lim = entradas["limite"]

    # --- Datos base en unidades del SI (con validación de robustez) ---
    # El motor debe sobrevivir a entradas inválidas o ausentes (datos reales
    # de estaciones meteorológicas defectuosos, mediciones fallidas, etc.).
    diametro_mm = float(c.get("diametro_mm", 0.0))
    if diametro_mm <= 0.0:
        raise ValueError("El diámetro del conductor debe ser mayor que 0 mm.")
    d0_m = diametro_mm / 1000.0
    ts_c = float(lim.get("ts_C", 50.0))
    ta_c = float(m.get("ta_C", 20.0))
    ts_k = ts_c + 273.15
    ta_k = ta_c + 273.15
    he_m = float(g.get("he_m", 0.0))

    # --- 1) Presión del aire (ISO 2533) ---
    p_hpa = presion_aire(he_m)

    # --- 2) Resistencia a la temperatura media R(Tavg); steady: Tavg = Ts ---
    t_low = float(c.get("t_low_C", 25.0))
    t_high = float(c.get("t_high_C", 70.0))
    r_low = float(c["r_low_ohm_km"]) / 1000.0   # ohm/m
    r_high = float(c["r_high_ohm_km"]) / 1000.0
    r_tavg = resistencia_conductor(r_low, r_high, t_low, t_high, ts_c)

    # --- 3) Temperatura de película ---
    tfilm_c = (ts_c + ta_c) / 2.0

    # --- 4) Propiedades del aire ---
    mu = viscosidad_aire(tfilm_c)                                   # kg/(m·s)
    ro_reynolds = densidad_aire_correlacion(he_m, tfilm_c)          # para Re
    # Densidad para la convección natural: la norma (IEEE 738, 4.4.3.1)
    # usa la densidad del aire evaluada a la temperatura de película Tfilm.
    # EnerFlux usaba la ley de gases a Ta (bug); el modo "ieee738" usa la
    # correlación a Tfilm, como manda la norma.
    if modo == "enerflux":
        ro_qcn = densidad_aire_ley_gases(p_hpa, ta_k)
    else:
        ro_qcn = densidad_aire_correlacion(he_m, tfilm_c)
    kf = conductividad_termica_aire(tfilm_c)                        # W/(m·°C)

    # --- 5) Ángulo del viento respecto al conductor (phi) ---
    theta_viento = m.get("direccion_viento_deg")
    theta_conductor = float(g.get("zl_deg", 0.0))
    phi = normalizar_angulo_viento_conductor(theta_viento, theta_conductor)
    hay_viento = (theta_viento is not None
                  and float(m.get("vw_m_s", 0.0)) > 0.0)

    if hay_viento and phi is not None:
        kangle = factor_direccion_viento(phi, modo=modo)
    else:
        phi = None
        kangle = 0.0  # convención de EnerFlux: sin viento, kangle = 0

    # --- 6) Convecciones ---
    # Convección natural (solo si Ts > Ta; si no, no hay enfriamiento natural útil)
    if ts_k > ta_k:
        qcn = conveccion_natural(d0_m, ro_qcn, ts_k, ta_k)
    else:
        qcn = 0.0

    # Convección forzada
    if hay_viento and phi is not None and float(m.get("vw_m_s", 0.0)) > 0.0:
        vw = float(m.get("vw_m_s", 0.0))
        re = numero_reynolds(d0_m, ro_reynolds, vw, mu)
        qc1 = kangle * (1.01 + 1.35 * re ** 0.52) * kf * (ts_k - ta_k)
        qc2 = kangle * 0.754 * re ** 0.6 * kf * (ts_k - ta_k)
    else:
        re = 0.0
        qc1 = 0.0
        qc2 = 0.0

    # Convección finalmente seleccionada: la mayor de qcn, qc1, qc2
    qc = max(qcn, qc1, qc2)

    # --- 7) Pérdida por radiación ---
    emisividad = float(c.get("emisividad", 0.8))
    qr = perdida_radiacion(d0_m, emisividad, ts_k, ta_k)

    # --- 8) Ganancia solar ---
    absortividad = float(c.get("absortividad", 0.8))
    n = dia_del_ano(entradas["fecha"])
    hora_solar = float(entradas.get("hora_solar", 12.0))
    solar = posicion_solar(float(g.get("lat_deg", 0.0)), n, hora_solar)
    qs_nivel_mar = intensidad_solar_nivel_mar(solar["hc_deg"])
    qse, k_solar = correccion_altitud_solar(qs_nivel_mar, he_m, modo=modo)

    # En modo "enerflux" el área proyectada es la sección en m² (bug); en
    # "ieee738" es el diámetro (norma correcta).
    if modo == "enerflux":
        area_proyectada = float(c["seccion_mm2"]) / 1.0e6   # m²/m (bug EnerFlux)
    else:
        area_proyectada = d0_m                               # m²/m (norma)

    qs, theta_sel = ganancia_solar(
        absortividad, qse, solar["hc_deg"], solar["zc_deg"],
        float(g["zl_deg"]), area_proyectada, modo=modo
    )

    # --- 9) Corriente máxima admisible ---
    if r_tavg > 0.0:
        radicando = (qc + qr - qs) / r_tavg
        i_max = math.sqrt(radicando) if radicando > 0.0 else 0.0
    else:
        i_max = 0.0
        radicando = 0.0

    return {
        "modo": modo,
        "entradas_resumen": {
            "conductor": c.get("designacion", ""),
            "ts_C": ts_c,
            "ta_C": ta_c,
            "vw_m_s": float(m.get("vw_m_s", 0.0)),
            "phi_deg": phi,
            "he_m": he_m,
            "lat_deg": float(g["lat_deg"]),
            "zl_deg": float(g["zl_deg"]),
            "fecha": entradas["fecha"],
            "hora_solar": hora_solar,
            "emisividad": emisividad,
            "absortividad": absortividad,
        },
        "intermedios": {
            "presion_hpa": p_hpa,
            "r_tavg_ohm_m": r_tavg,
            "r_tavg_ohm_km": r_tavg * 1000.0,
            "tfilm_C": tfilm_c,
            "viscosidad_kg_ms": mu,
            "densidad_aire_reynolds_kg_m3": ro_reynolds,
            "densidad_aire_qcn_kg_m3": ro_qcn,
            "conductividad_termica_kf_W_mC": kf,
            "reynolds": re,
            "kangle": kangle,
            "qcn_W_m": qcn,
            "qc1_W_m": qc1,
            "qc2_W_m": qc2,
            "qc_W_m": qc,
            "qr_W_m": qr,
            "declinacion_solar_deg": solar["delta_deg"],
            "angulo_horario_deg": solar["omega_deg"],
            "altitud_solar_hc_deg": solar["hc_deg"],
            "acimut_solar_zc_deg": solar["zc_deg"],
            "theta_incidencia_deg": theta_sel,
            "qs_nivel_mar_W_m2": qs_nivel_mar,
            "k_solar": k_solar,
            "qse_W_m2": qse,
            "area_proyectada_m2_m": area_proyectada,
            "qs_W_m": qs,
            "radicando_A2": radicando,
        },
        "resultado": {"i_max_A": i_max},
    }


# ============================================================================
# GENERADOR DE CASO DE REFERENCIA — Paso 2
# ============================================================================

def generar_caso_referencia(
    conductor,
    apoyos_utm,
    huso,
    hemisferio="N",
    meteorologia=None,
    ts_C=85.0,
    fecha="2025-06-21",
    hora_solar=12.0,
    modo="ieee738",
    ruta_salida=None,
    nombre_caso=None,
    descripcion=None,
):
    """Genera el caso de referencia DLR completo y (opcionalmente) lo guarda en
    un archivo JSON.  Totalmente genérico: funciona para CUALQUIER línea (los
    datos llegan igual que los extrae principal.py de cada Excel/.doc).

    Parámetros
    ----------
    conductor : dict
        Propiedades del conductor (igual estructura que "conductor" de
        calcular_dlr, o con los campos extra del catálogo: designacion,
        diametro_mm, seccion_mm2, composicion, r_low_ohm_km, r_high_ohm_km,
        t_low_C, t_high_C, emisividad, absortividad).
    apoyos_utm : list[dict]
        Lista de apoyos con {"id", "x" (UTM Este), "y" (UTM Norte), "cota"}.
    huso : int
        Huso UTM (30 para España peninsular).
    hemisferio : str
        "N" o "S".
    meteorologia : dict | None
        {"ta_C", "vw_m_s", "direccion_viento_deg"}. Si es None, se usa la
        meteorología fija de calibración del Nivel 1A (30 °C, 2 m/s, 90°).
    ts_C : float
        Temperatura máxima admisible del conductor (°C). 85 para Nivel 1A.
    fecha : str
        Fecha "YYYY-MM-DD" del escenario (por defecto 21/06, N=172).
    hora_solar : float
        Hora solar (por defecto 12:00, mediodía).
    modo : str
        "ieee738" o "enerflux".
    ruta_salida : str | None
        Si se proporciona, guarda el JSON en esa ruta.
    nombre_caso : str | None
        Nombre del caso (p. ej. "Nivel 1B - Línea de demostración"). Por defecto,
        "Nivel 1A - Caso de referencia".
    descripcion : str | None
        Descripción del caso. Por defecto, la del Nivel 1A.

    Devuelve
    --------
    dict con el caso de referencia completo (entradas + intermedios + resultado).
    """
    if meteorologia is None:
        meteorologia = {
            "ta_C": 30.0,
            "vw_m_s": 2.0,
            "direccion_viento_deg": 90.0,
        }

    # Geometría derivada automáticamente de los apoyos (genérico)
    zl_deg = orientacion_primer_vano(apoyos_utm)
    he_m = altitud_media(apoyos_utm)
    lat_deg = latitud_media(apoyos_utm, huso, hemisferio)

    entradas = {
        "conductor": {
            "designacion": conductor["designacion"],
            "diametro_mm": conductor["diametro_mm"],
            "seccion_mm2": conductor["seccion_mm2"],
            "composicion": conductor.get("composicion", ""),
            "r_low_ohm_km": conductor["r_low_ohm_km"],
            "r_high_ohm_km": conductor["r_high_ohm_km"],
            "t_low_C": conductor.get("t_low_C", 25.0),
            "t_high_C": conductor.get("t_high_C", 70.0),
            "emisividad": conductor.get("emisividad", 0.8),
            "absortividad": conductor.get("absortividad", 0.8),
        },
        "meteorologia": meteorologia,
        "geometria": {
            "he_m": he_m,
            "lat_deg": lat_deg,
            "zl_deg": zl_deg,
        },
        "fecha": fecha,
        "hora_solar": hora_solar,
        "limite": {"ts_C": ts_C},
    }

    resultado = calcular_dlr(entradas, modo=modo)

    caso = {
        "nombre_caso": nombre_caso or "Nivel 1A - Caso de referencia",
        "descripcion": descripcion or (
            "Caso de referencia estático IEEE 738 para validar el motor DLR. "
            "Se genera automáticamente para cualquier línea (cambia el Excel "
            "y se regenera)."
        ),
        "modo": modo,
        "fecha_generacion": datetime.now().isoformat(timespec="seconds"),
        "geometria_derivada": {
            "num_apoyos": len(apoyos_utm),
            "acimut_linea_zl_deg": zl_deg,
            "altitud_media_m": he_m,
            "latitud_media_deg": lat_deg,
            "huso": huso,
            "hemisferio": hemisferio,
        },
        "entradas": entradas,
        "resultado": resultado,
    }

    if ruta_salida:
        directorio = os.path.dirname(os.path.abspath(ruta_salida))
        if directorio and not os.path.exists(directorio):
            os.makedirs(directorio, exist_ok=True)
        with open(ruta_salida, "w", encoding="utf-8") as archivo:
            json.dump(caso, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")

    return caso


# ============================================================================
# DEMOSTRACIÓN / PRUEBA DEL MOTOR (al ejecutar este archivo directamente)
# ============================================================================

def _conductor_la56():
    """Conductor LA-56 (47-AL1/8-ST1A) con los datos eléctricos del Excel de
    EnerFlux (R a 25 °C y 70 °C) y ε = α = 0.8."""
    return {
        "designacion": "47-AL1/8-ST1A (LA-56)",
        "diametro_mm": 9.45,
        "seccion_mm2": 54.6,
        "composicion": "6+1",
        "r_low_ohm_km": 0.6101,     # R(Tlow=25 °C) en ohm/km
        "r_high_ohm_km": 0.6106,    # R(Thigh=70 °C) en ohm/km
        "t_low_C": 25.0,
        "t_high_C": 70.0,
        "emisividad": 0.8,
        "absortividad": 0.8,
    }


def _apoyos_demostracion():
    """Alineación UTM anonimizada usada por la demostración pública."""
    return [
        {"id": "1", "x": 500000.00, "y": 4200000.00, "cota": 560.56},
        {"id": "2", "x": 499999.00, "y": 4199990.00, "cota": 560.00},
        {"id": "3", "x": 499979.00, "y": 4199903.00, "cota": 556.57},
        {"id": "4", "x": 499929.00, "y": 4199772.00, "cota": 542.97},
    ]


def _imprimir_caso(caso):
    """Imprime de forma legible el caso de referencia."""
    ent = caso["entradas"]
    inter = caso["resultado"]["intermedios"]
    res = caso["resultado"]["resultado"]
    geo = caso["geometria_derivada"]

    print("=" * 72)
    print("CASO DE REFERENCIA DLR (Nivel 1A)")
    print("=" * 72)
    print(f"Modo            : {caso['modo']}")
    print(f"Conductor       : {ent['conductor']['designacion']}")
    print(f"Ts              : {ent['limite']['ts_C']:.1f} °C")
    print(f"Ta              : {ent['meteorologia']['ta_C']:.1f} °C")
    print(f"Viento          : {ent['meteorologia']['vw_m_s']:.2f} m/s")
    print(f"Dir. viento     : {ent['meteorologia']['direccion_viento_deg']:.1f} °")
    print(f"Fechas          : {ent['fecha']}  {ent['hora_solar']:.0f}:00 solar")
    print(f"Acimut línea Zl : {geo['acimut_linea_zl_deg']:.2f} °")
    print(f"Altitud media   : {geo['altitud_media_m']:.2f} m")
    print(f"Latitud media   : {geo['latitud_media_deg']:.4f} °")
    print("-" * 72)
    print("INTERMEDIOS")
    print("-" * 72)
    print(f"  Presión aire              : {inter['presion_hpa']:.2f} hPa")
    print(f"  R(Tavg)                   : {inter['r_tavg_ohm_km']:.6f} ohm/km")
    print(f"  Tfilm                     : {inter['tfilm_C']:.2f} °C")
    print(f"  Viscosidad                : {inter['viscosidad_kg_ms']:.6e} kg/(m·s)")
    print(f"  Densidad (Re)             : {inter['densidad_aire_reynolds_kg_m3']:.5f} kg/m³")
    print(f"  Densidad (qcn)            : {inter['densidad_aire_qcn_kg_m3']:.5f} kg/m³")
    print(f"  Conductividad kf          : {inter['conductividad_termica_kf_W_mC']:.6f} W/(m·°C)")
    print(f"  Reynolds                  : {inter['reynolds']:.2f}")
    print(f"  Kangle                    : {inter['kangle']:.4f}")
    print(f"  qcn (natural)             : {inter['qcn_W_m']:.2f} W/m")
    print(f"  qc1 (forzada 1)           : {inter['qc1_W_m']:.2f} W/m")
    print(f"  qc2 (forzada 2)           : {inter['qc2_W_m']:.2f} W/m")
    print(f"  qc (elegida)              : {inter['qc_W_m']:.2f} W/m")
    print(f"  qr (radiación)            : {inter['qr_W_m']:.2f} W/m")
    print(f"  Declinación solar         : {inter['declinacion_solar_deg']:.2f} °")
    print(f"  Ángulo horario            : {inter['angulo_horario_deg']:.1f} °")
    print(f"  Altitud solar Hc          : {inter['altitud_solar_hc_deg']:.2f} °")
    print(f"  Acimut solar Zc           : {inter['acimut_solar_zc_deg']:.2f} °")
    print(f"  Theta incidencia          : {inter['theta_incidencia_deg']:.2f} °")
    print(f"  Qs nivel del mar          : {inter['qs_nivel_mar_W_m2']:.2f} W/m²")
    print(f"  Ksolar                    : {inter['k_solar']:.6f}")
    print(f"  Qse (corregido)           : {inter['qse_W_m2']:.2f} W/m²")
    print(f"  Área proyectada           : {inter['area_proyectada_m2_m']:.6e} m²/m")
    print(f"  qs (solar)                : {inter['qs_W_m']:.2f} W/m")
    print("-" * 72)
    print(f"  Corriente máxima I        : {res['i_max_A']:.2f} A")
    print("=" * 72)


def main():
    """Prueba del motor: genera los casos de referencia (Nivel 1A y Nivel 1B).

    - Nivel 1A: Ts = 85 °C (patrón de laboratorio, para comparar con EnerFlux).
    - Nivel 1B: Ts = T_máx detectada automáticamente del Excel de la línea
      (en el ejemplo = 50 °C; en otros Excel será la que
      tengan).  El caso se genera SIEMPRE con la T_máx real del Excel, nunca
      con un valor fijado a mano.
    """
    ruta_assets = str(assets_dir())
    ruta_excel = str(data_dir() / "line_example.xlsx")

    # ============ NIVEL 1A: patrón de laboratorio (Ts = 85 °C) ============
    print("\n" + "#" * 72)
    print("# NIVEL 1A — Patrón de laboratorio (Ts = 85 °C para comparar con EnerFlux)")
    print("#" * 72)
    caso_1a = generar_caso_referencia(
        conductor=_conductor_la56(),
        apoyos_utm=_apoyos_demostracion(),
        huso=30,
        hemisferio="N",
        ts_C=85.0,
        modo="ieee738",
        ruta_salida=os.path.join(ruta_assets, "caso_referencia_nivel1a.json"),
        nombre_caso="Nivel 1A - Patrón de laboratorio (Ts=85 °C)",
        descripcion=(
            "Patrón de laboratorio IEEE 738 con Ts=85 °C (límite RLAT cat. "
            "especial). Sirve para comparar contra EnerFlux en el Nivel 2."
        ),
    )
    _imprimir_caso(caso_1a)

    # Diagnóstico Nivel 2: réplica EnerFlux con la misma Ts
    caso_enerflux = generar_caso_referencia(
        conductor=_conductor_la56(),
        apoyos_utm=_apoyos_demostracion(),
        huso=30,
        hemisferio="N",
        ts_C=85.0,
        modo="enerflux",
        ruta_salida=os.path.join(ruta_assets, "caso_referencia_enerflux.json"),
        nombre_caso="Nivel 1A (diagnóstico) - Réplica EnerFlux",
    )

    # ============ NIVEL 1B: línea real (Ts = T_máx detectada del Excel) ============
    print("\n" + "#" * 72)
    print("# NIVEL 1B — Línea real (Ts = T_máx detectada automáticamente del Excel)")
    print("#" * 72)
    t_max_excel = detectar_temperatura_maxima_excel(ruta_excel)
    if t_max_excel is None:
        t_max_excel = 85.0  # fallback documentado (categoría especial)
        print(f"  ⚠️  No se pudo detectar T_máx del Excel; fallback = {t_max_excel:.0f} °C")
    caso_1b = generar_caso_referencia(
        conductor=_conductor_la56(),
        apoyos_utm=_apoyos_demostracion(),
        huso=30,
        hemisferio="N",
        ts_C=t_max_excel,
        modo="ieee738",
        ruta_salida=os.path.join(ruta_assets, "caso_referencia_nivel1b.json"),
        nombre_caso=f"Nivel 1B - Caso real (Ts={t_max_excel:.0f} °C)",
        descripcion=(
            "Caso de referencia de la línea real con su temperatura límite "
            "operativa detectada automáticamente de la hoja 'T. tend. cond. "
            "fase' del Excel. Para CUALQUIER línea: detecta su T_máx real."
        ),
    )
    _imprimir_caso(caso_1b)

    # ============ COMPARACIONES ============
    print("\nCOMPARACIÓN NORMA vs ENERFLUX (Nivel 1A, Ts=85 °C)")
    print("-" * 60)
    for clave in ("qc_W_m", "qr_W_m", "qs_W_m", "r_tavg_ohm_km"):
        v_ieee = caso_1a["resultado"]["intermedios"][clave]
        v_ef = caso_enerflux["resultado"]["intermedios"][clave]
        print(f"  {clave:24s} IEEE={v_ieee:10.3f}  EnerFlux={v_ef:10.3f}")
    print(
        "  I máxima                IEEE="
        f"{caso_1a['resultado']['resultado']['i_max_A']:.2f} A"
        "  EnerFlux="
        f"{caso_enerflux['resultado']['resultado']['i_max_A']:.2f} A"
    )

    print("\nCOMPARACIÓN NIVEL 1A vs NIVEL 1B (misma línea, distinta Ts)")
    print("-" * 60)
    i_1a = caso_1a["resultado"]["resultado"]["i_max_A"]
    i_1b = caso_1b["resultado"]["resultado"]["i_max_A"]
    ts_1a = caso_1a["entradas"]["limite"]["ts_C"]
    ts_1b = caso_1b["entradas"]["limite"]["ts_C"]
    print(f"  Ts 1A = {ts_1a:.0f} °C  ->  I_max = {i_1a:.2f} A")
    print(f"  Ts 1B = {ts_1b:.0f} °C  ->  I_max = {i_1b:.2f} A")
    if i_1b < i_1a:
        print("  ✅ COHERENCIA FÍSICA OK: bajar Ts reduce la corriente admisible.")
    else:
        print("  ⚠️  AVISO: I_1B >= I_1A. Revisar física (no esperado).")

    print("\nArchivos JSON generados:")
    print("  - unity/Assets/caso_referencia_nivel1a.json  (Nivel 1A)")
    print("  - unity/Assets/caso_referencia_enerflux.json (diagnóstico)")
    print(f"  - unity/Assets/caso_referencia_nivel1b.json (Nivel 1B, Ts={t_max_excel:.0f} °C)")


if __name__ == "__main__":
    main()
