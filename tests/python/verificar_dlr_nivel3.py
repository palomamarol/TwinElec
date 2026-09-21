# -*- coding: utf-8 -*-
"""
verificar_dlr_nivel3.py — Pruebas de coherencia física y robustez del motor DLR
===============================================================================
Nivel 3 del plan de aplicación del DLR al gemelo digital (Unity).

Dos baterías de pruebas:
    A) COHERENCIA FÍSICA: el motor debe reaccionar lógicamente ante cambios
       en las condiciones (más viento -> más I, noche -> qs=0, etc.).
    B) ROBUSTEZ: el motor debe sobrevivir a entradas inválidas o ausentes
       (diámetro 0, R negativa, Ta>Ts, dirección fuera de rango, datos
       ausentes) sin romperse ni devolver NaN.

Escenario base anonimizado: LA-56 (Ts=50 °C), caso del Nivel 1B.
"""

import sys
import json
import os
import copy

import dlr
from twinelec_paths import assets_dir

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ============================================================================
# ESCENARIO BASE ANONIMIZADO (LA-56, Ts=50 °C — Nivel 1B)
# ============================================================================
def escenario_base():
    return {
        "conductor": {
            "designacion": "47-AL1/8-ST1A (LA-56)",
            "diametro_mm": 9.45,
            "seccion_mm2": 54.6,
            "composicion": "6+1",
            "r_low_ohm_km": 0.6101,
            "r_high_ohm_km": 0.6106,
            "t_low_C": 25.0,
            "t_high_C": 70.0,
            "emisividad": 0.8,
            "absortividad": 0.8,
        },
        "meteorologia": {
            "ta_C": 30.0,
            "vw_m_s": 2.0,
            "direccion_viento_deg": 90.0,
        },
        "geometria": {
            "he_m": 555.025,
            "lat_deg": 37.9362,
            "zl_deg": 185.256,
        },
        "fecha": "2025-06-21",
        "hora_solar": 12.0,
        "limite": {"ts_C": 50.0},
    }


def corriente(entradas, modo="ieee738"):
    """Devuelve I_max y los intermedios, o captura excepciones controladas."""
    try:
        resultado = dlr.calcular_dlr(entradas, modo=modo)
        return resultado["resultado"]["i_max_A"], resultado["intermedios"]
    except ValueError as e:
        return f"ERROR_VALOR: {e}", None
    except ZeroDivisionError:
        return "ERROR_DIV0", None
    except Exception as e:
        return f"ERROR: {type(e).__name__}", None


# ============================================================================
# BATERÍA A — COHERENCIA FÍSICA
# ============================================================================
def bateria_coherencia():
    """Comprueba que el motor reacciona en la dirección físicamente correcta."""
    pruebas = []
    base = escenario_base()
    i_base, inter_base = corriente(base)
    if isinstance(i_base, str):
        return [("BASE inválido", i_base, "FAIL", "El escenario base no calcula")]

    # A1: más viento -> más I
    e = copy.deepcopy(base)
    e["meteorologia"]["vw_m_s"] = 4.0
    i_viento, _ = corriente(e)
    pruebas.append(
        ("A1 más viento -> más I", (i_base, i_viento),
         i_viento > i_base, f"I(2m/s)={i_base:.1f} -> I(4m/s)={i_viento:.1f}")
    )

    # A2: viento perpendicular vs paralelo -> perpendicular refrigeró más
    e = copy.deepcopy(base)
    e["meteorologia"]["direccion_viento_deg"] = 185.256  # phi=0 (paralelo)
    i_paralelo, _ = corriente(e)
    pruebas.append(
        ("A2 perpendicular -> más I que paralelo", (i_paralelo, i_base),
         i_base > i_paralelo, f"I(paralelo)={i_paralelo:.1f} < I(perp)={i_base:.1f}")
    )

    # A3: más temperatura ambiente -> menos I
    e = copy.deepcopy(base)
    e["meteorologia"]["ta_C"] = 40.0
    i_tacaliente, _ = corriente(e)
    pruebas.append(
        ("A3 más Ta -> menos I", (i_base, i_tacaliente),
         i_tacaliente < i_base, f"I(Ta=30)={i_base:.1f} > I(Ta=40)={i_tacaliente:.1f}")
    )

    # A4: más radiación solar -> menos I (mediodía vs noche)
    e = copy.deepcopy(base)
    e["hora_solar"] = 0.0  # noche
    i_noche, inter_noche = corriente(e)
    pruebas.append(
        ("A4 noche -> qs=0 y más I", (inter_noche["qs_W_m"], i_noche),
         inter_noche["qs_W_m"] == 0.0 and i_noche > i_base,
         f"qs(noche)={inter_noche['qs_W_m']:.2f} (base={inter_base['qs_W_m']:.2f}), I={i_noche:.1f}")
    )

    # A5: mayor Ts -> normalmente más I
    e = copy.deepcopy(base)
    e["limite"]["ts_C"] = 70.0
    i_ts70, _ = corriente(e)
    pruebas.append(
        ("A5 mayor Ts -> más I", (i_base, i_ts70),
         i_ts70 > i_base, f"I(Ts=50)={i_base:.1f} < I(Ts=70)={i_ts70:.1f}")
    )

    # A6: sin viento -> usa convección natural (qc = qcn)
    e = copy.deepcopy(base)
    e["meteorologia"]["vw_m_s"] = 0.0
    e["meteorologia"]["direccion_viento_deg"] = None
    i_sin_viento, inter_sv = corriente(e)
    usa_qcn = abs(inter_sv["qc_W_m"] - inter_sv["qcn_W_m"]) < 1e-9
    pruebas.append(
        ("A6 sin viento -> qc=qcn", (inter_sv["qc_W_m"], inter_sv["qcn_W_m"]),
         usa_qcn, f"qc={inter_sv['qc_W_m']:.2f} = qcn={inter_sv['qcn_W_m']:.2f}")
    )

    # A7: I=0 no produce Joule (con corriente nula no hay calentamiento)
    # El balance implica: si I=0 -> qs = qc + qr (el motor da I_max=0 si no
    # hay margen). Verificamos que con un escenario imposible (Ts=Ta sin sol
    # ni viento) la I_max sea 0 (no negativa).
    e = copy.deepcopy(base)
    e["limite"]["ts_C"] = 30.0
    e["meteorologia"]["ta_C"] = 30.0
    e["hora_solar"] = 0.0
    e["meteorologia"]["vw_m_s"] = 0.0
    i_cero, inter_cero = corriente(e)
    radicando = inter_cero["radicando_A2"]
    pruebas.append(
        ("A7 sin margen -> I=0 y radicando no negativo", (i_cero, radicando),
         i_cero == 0.0 and radicando >= 0.0,
         f"I={i_cero}, radicando={radicando:.1f}")
    )

    return pruebas


# ============================================================================
# BATERÍA B — ROBUSTEZ (entradas inválidas / ausentes)
# ============================================================================
def bateria_robustez():
    pruebas = []
    base = escenario_base()

    # B1: diámetro cero -> error controlado (no NaN/crash silencioso)
    e = copy.deepcopy(base)
    e["conductor"]["diametro_mm"] = 0.0
    i, _ = corriente(e)
    pruebas.append(
        ("B1 diámetro cero -> error controlado", i,
         isinstance(i, str) and "ERROR" in i, f"resultado={i}")
    )

    # B2: resistencia negativa -> resultado controlado (I=0, no crash)
    e = copy.deepcopy(base)
    e["conductor"]["r_low_ohm_km"] = -0.5
    e["conductor"]["r_high_ohm_km"] = -0.5
    i, _ = corriente(e)
    # r_tavg <= 0: el motor devuelve i_max=0 controlado
    pruebas.append(
        ("B2 R negativa -> I=0 controlado", i,
         (isinstance(i, (int, float)) and i == 0.0) or (isinstance(i, str) and "ERROR" in i),
         f"resultado={i}")
    )

    # B3: Ta > Ts -> no debe dar NaN (radicando protegido)
    e = copy.deepcopy(base)
    e["meteorologia"]["ta_C"] = 60.0
    e["limite"]["ts_C"] = 50.0
    i, inter = corriente(e)
    es_finito = isinstance(i, (int, float)) and i >= 0.0 and (
        inter is None or all(
            isinstance(v, (int, float)) and not isinstance(v, float) or v == v
            for v in inter.values()
        )
    )
    pruebas.append(
        ("B3 Ta>Ts -> sin NaN/crash", i,
         es_finito, f"I={i}")
    )

    # B4: dirección de viento fuera de rango (450°) -> normaliza a [0,180]
    e = copy.deepcopy(base)
    e["meteorologia"]["direccion_viento_deg"] = 450.0
    i_450, _ = corriente(e)
    # phi_deg se guarda en entradas_resumen (no en intermedios)
    try:
        res_450 = dlr.calcular_dlr(e, modo="ieee738")
        phi = res_450["entradas_resumen"]["phi_deg"]
    except Exception:
        phi = None
    normaliza = phi is not None and 0.0 <= phi <= 90.0
    pruebas.append(
        ("B4 dirección 450° -> phi normalizada", phi,
         normaliza, f"phi={phi}")
    )

    # B5: datos meteorológicos ausentes (sin clave direccion) -> usa calma
    e = copy.deepcopy(base)
    del e["meteorologia"]["direccion_viento_deg"]
    i_ausente, _ = corriente(e)
    pruebas.append(
        ("B5 viento ausente -> sin crash (calma)", i_ausente,
         isinstance(i_ausente, (int, float)) and i_ausente >= 0.0,
         f"I={i_ausente}")
    )

    return pruebas


# ============================================================================
# EJECUCIÓN Y VEREDICTO
# ============================================================================
def ejecutar_y_mostrar(nombre_bateria, pruebas):
    print(f"\n{'=' * 90}")
    print(f"BATERÍA {nombre_bateria}")
    print(f"{'=' * 90}")
    print(f"{'Prueba':<42}{'Resultado obtenido':<38}{'Condición':<12}{'Estado':<6}")
    print("-" * 90)
    fallos = 0
    for nombre, resultado, condicion_ok, detalle in pruebas:
        estado = "PASS" if condicion_ok else "FAIL"
        if not condicion_ok:
            fallos += 1
        print(f"{nombre:<42}{detalle:<38}{'debe cumplir':<12}{estado}")
        print(f"{'':<42}{'(obtenido: ' + str(resultado) + ')':<38}")
    return fallos


def main():
    print("=" * 90)
    print("NIVEL 3 — PRUEBAS DE COHERENCIA FÍSICA Y ROBUSTEZ DEL MOTOR DLR")
    print("=" * 90)

    coherencia = bateria_coherencia()
    robustez = bateria_robustez()

    fallos_a = ejecutar_y_mostrar("A — COHERENCIA FÍSICA", coherencia)
    fallos_b = ejecutar_y_mostrar("B — ROBUSTEZ (ENTRADAS INVÁLIDAS)", robustez)

    total_fallos = fallos_a + fallos_b
    total_pruebas = len(coherencia) + len(robustez)

    print("\n" + "=" * 90)
    print(f"RESULTADO GLOBAL: {total_pruebas - total_fallos}/{total_pruebas} pruebas PASS")
    if total_fallos == 0:
        print("✅ NIVEL 3 SUPERADO: el motor es coherente físicamente y robusto.")
    else:
        print(f"❌ HAY {total_fallos} PRUEBAS CON FALLO.")
    print("=" * 90)

    # Guardar informe
    ruta_salida = str(assets_dir() / "verificacion_nivel3.json")
    informe = {
        "nombre": "Verificación Nivel 3 - Coherencia física y robustez",
        "coherencia": [
            {"prueba": n, "detalle": d, "ok": ok}
            for n, _, ok, d in coherencia
        ],
        "robustez": [
            {"prueba": n, "detalle": d, "ok": ok}
            for n, _, ok, d in robustez
        ],
        "total_pass": total_pruebas - total_fallos,
        "total_pruebas": total_pruebas,
        "veredicto": "PASS" if total_fallos == 0 else "FALLOS",
    }
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    print(f"Informe guardado en {ruta_salida}")

    return 0 if total_fallos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
