# -*- coding: utf-8 -*-
"""
sobrecargas.py
==============
Port a Python del "SUBPROGRAMA 1: SOBRECARGAS" (calculadora HP Prime) que
reutiliza Paloma para los graficos de utilizacion del Tema 10 (ITC-LAT 07).

Calcula las sobrecargas por unidad de longitud del conductor [daN/m]:
    Sv      -> sobrecarga con viento maximo (Vviento, por defecto 120 km/h)
    Sv120   -> sobrecarga con viento a 120 km/h
    Sh      -> sobrecarga de hielo
    S_vm    -> sobrecarga con la mitad de la presion del viento
    S_vh    -> sobrecarga de viento mas hielo
    dmh     -> diametro del manguito de hielo [m]

Tambien expone los valores intermedios (P_daN, P_v_max, C_viento, V_vh, ...)
para poder enlazarlos con las variables de graficos_utilizacion_ecuaciones.py.

USO:
    from sobrecargas import calcular_sobrecargas
    res = calcular_sobrecargas(diametro_mm=14.0, peso_kg_m=0.433, zona="C")
    print(res["Sh"])   # 1.771 daN/m  (ejemplo del Tema 10)

NOTA SOBRE EL VIENTO (120/140 km/h):
    La velocidad de viento de la hipotesis reglamentaria depende de la
    categoria de la linea: categoria especial -> 140 km/h, no especial ->
    120 km/h. El parametro 'viento_kmh' permite elegirlo (por defecto 120).
"""
import math

# Coeficiente K_hielo segun la zona (ITC-LAT 07):
#   Zona A -> no hay hielo
#   Zona B -> manguito estandar 0.18
#   Zona C -> manguito estandar 0.36
K_HIELO_POR_ZONA = {
    "A": 0.0,
    "B": 0.18,
    "C": 0.36,
}

# Presion del viento a 120 km/h [daN/m2] segun el diametro del conductor
C_VIENTO_120 = 60.0   # diametro <= 16 mm
C_VIENTO_120_GRUESO = 50.0   # diametro > 16 mm


def _coeficiente_viento(diametro_mm):
    """60 daN/m2 si el conductor (o manguito) tiene diametro <= 16 mm, si no 50."""
    return C_VIENTO_120 if diametro_mm <= 16.0 else C_VIENTO_120_GRUESO


def calcular_sobrecargas(diametro_mm, peso_kg_m, zona, viento_kmh=120.0,
                         k_hielo=None):
    """Port fiel del subprograma SOBRECARGAS de la HP Prime.

    Parametros:
        diametro_mm: diametro del conductor desnudo [mm].
        peso_kg_m:   peso del conductor [kg/m].
        zona:        "A", "B" o "C" (ITC-LAT 07).
        viento_kmh:  velocidad del viento considerada [km/h] (por defecto 120).
        k_hielo:     coeficiente del manguito de hielo. Si es None se usa el
                     estandar segun la zona (0.18 zona B, 0.36 zona C).

    Devuelve:
        dict con las sobrecargas y valores intermedios (todas en SI).
    """
    zona = str(zona).upper()
    if zona not in K_HIELO_POR_ZONA:
        raise ValueError("Zona desconocida: %r (valores validos: A, B, C)" % zona)

    if k_hielo is None:
        k_hielo = K_HIELO_POR_ZONA[zona]

    # --- CALCULOS FISICOS DEL CONDUCTOR DESNUDO ---
    p_daN = peso_kg_m * 0.98                       # peso del conductor [daN/m]
    c_viento = _coeficiente_viento(diametro_mm)
    p_v_max = c_viento * (viento_kmh / 120.0) ** 2   # presion del viento [daN/m2]
    f_v_max = p_v_max * (diametro_mm * 0.001)        # fuerza del viento max [daN/m]
    # Fuerza del viento con la MITAD de la presion (punto de la catenaria con viento mitad)
    f_v_mitad = (p_v_max * (120.0 / viento_kmh) ** 2 / 2.0) * (diametro_mm * 0.001)
    f_v_120 = c_viento * (diametro_mm * 0.001)       # fuerza del viento a 120 km/h

    # --- CALCULOS DEL MANGUITO DE HIELO ---
    # dmh en metros
    dmh = math.sqrt(
        (diametro_mm / 1000.0) ** 2
        + (4.0 * k_hielo * math.sqrt(diametro_mm)) / (math.pi * 750.0)
    )
    p_hielo = k_hielo * math.sqrt(diametro_mm)      # sobrecarga de hielo [daN/m]
    f_v_hielo = p_v_max * k_hielo

    # Coeficiente del viento segun el diametro FINAL con hielo (en mm)
    c_viento_hielo = _coeficiente_viento(dmh * 1000.0)
    # Presion del viento especifica para la hipotesis de viento+hielo (60 km/h)
    v_vh = c_viento_hielo * (60.0 / 120.0) ** 2     # [daN/m2]

    # --- SOBRECARGAS FINALES [daN/m] ---
    sv = math.sqrt(p_daN ** 2 + f_v_max ** 2)
    sv120 = math.sqrt(p_daN ** 2 + f_v_120 ** 2)
    sh = p_daN + p_hielo
    s_vmitad = math.sqrt(p_daN ** 2 + f_v_mitad ** 2)
    s_vh = math.sqrt(sh ** 2 + (v_vh * dmh) ** 2)

    return {
        # Sobrecargas finales
        "Sv": sv, "Sv120": sv120, "Sh": sh,
        "S_vm": s_vmitad, "S_vh": s_vh,
        "dmh_m": dmh, "dmh_mm": dmh * 1000.0,
        # Valores intermedios
        "P_daN": p_daN, "P_kg": peso_kg_m,
        "Dcond_mm": diametro_mm, "zona": zona, "K_hielo": k_hielo,
        "C_viento": c_viento, "C_viento_hielo": c_viento_hielo,
        "P_v_max": p_v_max, "F_v_max": f_v_max, "F_v_mitad": f_v_mitad,
        "F_v_120": f_v_120, "P_hielo": p_hielo, "F_v_hielo": f_v_hielo,
        "V_vh": v_vh, "viento_kmh": viento_kmh,
    }


if __name__ == "__main__":
    import json
    print("== SOBRECARGAS - port de la HP Prime ==")
    # Ejemplos del Tema 10 para validar
    casos_prueba = [
        # (diametro_mm, peso_kg_m, zona, viento_kmh, descripcion)
        (14.0, 0.433, "C", 120.0, "LA-110 zona C (pag. 9-10)"),
        (14.0, 0.433, "B", 120.0, "LA-110 zona B (pag. 24)"),
        (14.0, 0.433, "C", 140.0, "LA-110 zona C a 140 km/h (pag. 49)"),
        (9.45, 0.188, "B", 120.0, "LA-56 zona B (pag. 40)"),
    ]
    for d, p, z, v, desc in casos_prueba:
        r = calcular_sobrecargas(d, p, z, viento_kmh=v)
        print("\n- %s" % desc)
        print("  Sv=%.4f  Sv120=%.4f  Sh=%.4f  S_vm=%.4f  S_vh=%.4f  dmh=%.4f m"
              % (r["Sv"], r["Sv120"], r["Sh"], r["S_vm"], r["S_vh"], r["dmh_m"]))
        print("  P_v_max=%.2f daN/m2  V_vh=%.2f daN/m2  C_viento_hielo=%s"
              % (r["P_v_max"], r["V_vh"], r["C_viento_hielo"]))
