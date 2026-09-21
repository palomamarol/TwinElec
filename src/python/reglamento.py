# -*- coding: utf-8 -*-
"""
reglamento.py
=============
Constantes y funciones del Reglamento (ITC-LAT 07) necesarias para los
graficos de utilizacion del Tema 10:

  - DPP   : distancia minima aerea para prevenir descarga disruptiva [m]
            (tabla de la ITC-LAT-07, segun la tension mas elevada de la red)
  - K'    : coeficiente segun la categoria de la linea (0.85 especial / 0.75 resto)
  - K     : coeficiente del vano maximo (Tabla 16 ITC-LAT-07), funcion del
            angulo de oscilacion de los conductores y de la tension de la linea
  - viento: regla 120/140 km/h segun la categoria (especial -> 140)

Reglas de categoria (segun la tension de la linea):
  - tension >= 220 kV  -> linea de categoria ESPECIAL
  - tension <  220 kV  -> linea de categoria NO ESPECIAL

USO:
    from reglamento import (dpp_segun_tension, k_prima_segun_categoria,
                            k_segun_angulo, angulo_oscilacion,
                            viento_kmh_segun_tension)
"""
import math

# ---------------------------------------------------------------------------
# DPP segun la tension mas elevada de la red (ITC-LAT 07)
# (tension_kv, DPP_m). Si la tension no figura, se toma el valor superior.
# ---------------------------------------------------------------------------
TABLA_DPP = [
    (3.6, 0.10),
    (7.2, 0.10),
    (12.0, 0.15),
    (17.5, 0.20),
    (24.0, 0.25),
    (30.0, 0.33),
    (36.0, 0.40),
    (52.0, 0.70),
    (72.5, 0.80),
    (123.0, 1.15),
    (145.0, 1.40),
    (170.0, 1.50),
    (245.0, 2.00),
    (420.0, 3.20),
]

# Umbral de tension que define la categoria especial
UMBRAL_CATEGORIA_ESPECIAL_KV = 220.0

# Umbral de tension para elegir la columna de la tabla de K
UMBRAL_K_30KV = 30.0


def dpp_segun_tension(tension_kv):
    """DPP [m] segun la tension mas elevada de la red (ITC-LAT 07).
    Si la tension no esta en la tabla, se toma el inmediato superior."""
    tension_kv = float(tension_kv)
    for umbral, dpp in TABLA_DPP:
        if tension_kv <= umbral:
            return dpp
    return TABLA_DPP[-1][1]  # por encima del ultimo umbral -> 3.20


def categoria_segun_tension(tension_kv):
    """'especial' si tension >= 220 kV; 'no_especial' en caso contrario."""
    return "especial" if float(tension_kv) >= UMBRAL_CATEGORIA_ESPECIAL_KV \
        else "no_especial"


def k_prima_segun_categoria(categoria):
    """K' = 0.85 para categoria especial, 0.75 para el resto (ITC-LAT 07)."""
    return 0.85 if str(categoria).lower() == "especial" else 0.75


def viento_kmh_segun_tension(tension_kv):
    """Viento de la hipotesis reglamentaria: especial -> 140 km/h,
    resto -> 120 km/h."""
    return 140.0 if float(tension_kv) >= UMBRAL_CATEGORIA_ESPECIAL_KV \
        else 120.0


def angulo_oscilacion(zona, v_daN_m2, d_m, p_daN_m, sh_daN_m):
    """Angulo de oscilacion de los conductores gamma [grados]:
        zona A    -> tg(gamma) = v*d/p
        zonas B/C -> tg(gamma) = v*d/SH
    (v = presion del viento [daN/m2], d = diametro [m],
     p = peso del conductor [daN/m], SH = sobrecarga de hielo [daN/m])"""
    if str(zona).upper() == "A":
        denominador = p_daN_m
    else:
        denominador = sh_daN_m
    if denominador is None or denominador <= 0:
        return None
    return math.degrees(math.atan((v_daN_m2 * d_m) / denominador))


def k_segun_angulo(gamma_grados, tension_kv):
    """Constante K (Tabla 16 ITC-LAT 07) segun el angulo de oscilacion y la
    tension de la linea:
        gamma > 65 grad        -> 0.70 (lineas >30 kV) / 0.65 (<=30 kV)
        40 <= gamma <= 65      -> 0.65 (lineas >30 kV) / 0.60 (<=30 kV)
        gamma < 40 grad        -> 0.60 (lineas >30 kV) / 0.55 (<=30 kV)"""
    if gamma_grados is None:
        return None
    columna_30 = float(tension_kv) <= UMBRAL_K_30KV
    if gamma_grados > 65.0:
        return 0.65 if columna_30 else 0.70
    if gamma_grados >= 40.0:
        return 0.60 if columna_30 else 0.65
    return 0.55 if columna_30 else 0.60


if __name__ == "__main__":
    print("== REGLAMENTO (ITC-LAT 07) ==")
    for kv in (20, 24, 45, 110, 220, 400):
        dpp = dpp_segun_tension(kv)
        cat = categoria_segun_tension(kv)
        kp = k_prima_segun_categoria(cat)
        v = viento_kmh_segun_tension(kv)
        print("  %4d kV -> DPP=%.2f m  categoria=%s  K'=%.2f  viento=%d km/h"
              % (kv, dpp, cat, kp, v))
    print("\n  Ejemplos de K (Tema 10):")
    print("    zona C, gamma=32.86 -> K=%.2f (esperado 0.55, linea <=30 kV)"
          % k_segun_angulo(32.86, 20))
    print("    zona A, gamma=64.81 -> K=%.2f (esperado 0.60, linea <=30 kV)"
          % k_segun_angulo(64.81, 20))
