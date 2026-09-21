# -*- coding: utf-8 -*-
"""
tensiones_vanos.py
==================
Motor de tensiones por vano y flechas del conductor. Implementa los dos
subprogramas Pascal de la calculadora (Subprograma 5 y Subprograma 6):

  SUBPROGRAMA 5 - TensionVanos
  ----------------------------
  Dada la tension en el apoyo (TA), el peso/sobrecarga (p), el vano (a) y el
  desnivel (h), obtiene la tension en el punto mas bajo:

      b = sqrt(h^2 + a^2)
      T0 = ((TA - p*|h|/2) + sqrt((TA - p*|h|/2)^2 - b^2*p^2/2)) / (2*b/a)

  SUBPROGRAMA 6 - TyFReglamentarias
  ---------------------------------
  Ecuacion de cambio de estado (cubica) para pasar de un estado inicial
  (t0, T0, p0) con vano de regulacion (ar) a una condicion objetivo (t, p):

      A = alfa*E*S*(t - t0) - T0 + (ar^2*p0^2*E*S)/(24*T0^2)
      B = (ar^2*p^2*E*S)/24
      T^3 + A*T^2 - B = 0        -> se toma la raiz real positiva Tf

  Y la flecha por vano:

      b = sqrt(a^2 + h^2)
      f = (a*b*p)/(8*Tf) * (1 + a^2*p^2/(48*Tf^2))

  Vano de regulacion (criterio clasico):
      ar = sqrt(suma(a^3) / suma(a))

  CRITERIO DE RECALCULO (opcion A):
  --------------------------------
  Al mover un apoyo se mantiene constante la TENSION DE REFERENCIA DEL TENDIDO
  (EDS: tension a la temperatura t0 con el solo peso del cable, leida de la
  pestaña 'T. tend. cond. fase' de la linea original). Con esa EDS fija y el
  nuevo vano de regulacion, se recalculan las tensiones y flechas de TODA la
  linea mediante la ecuacion de cambio de estado.
"""
import math

# ---------------------------------------------------------------------------
# Propiedades mecanicas de los conductores (catalogo_conductores.json)
# ---------------------------------------------------------------------------
# comp: E (daN/mm2), alfa (1/C)  -- tabla 'propiedades_mecanicas_por_composicion'
PROPIEDADES_COMPOSICION = {
    "6+1":   {"E_daN_mm2": 7900, "alfa_1_C": 1.91e-05},
    "6+7":   {"E_daN_mm2": 7500, "alfa_1_C": 1.98e-05},
    "26+7":  {"E_daN_mm2": 7500, "alfa_1_C": 1.89e-05},
    "30+7":  {"E_daN_mm2": 8000, "alfa_1_C": 1.78e-05},
    "30+19": {"E_daN_mm2": 7800, "alfa_1_C": 1.80e-05},
    "54+7":  {"E_daN_mm2": 6900, "alfa_1_C": 1.93e-05},
    "54+19": {"E_daN_mm2": 6700, "alfa_1_C": 1.94e-05},
}


def propiedades_conductor(conductor):
    """Devuelve {E_daN_mm2, alfa_1_C, seccion_mm2, peso_daN_m} de un dict de
    conductor (del catalogo) o de un dict con esos campos ya resueltos."""
    comp = (conductor.get("composicion") or "").strip()
    props = PROPIEDADES_COMPOSICION.get(comp, PROPIEDADES_COMPOSICION["6+1"])
    return {
        "E_daN_mm2": props["E_daN_mm2"],
        "alfa_1_C": props["alfa_1_C"],
        "seccion_mm2": conductor.get("seccion_mm2"),
        "peso_daN_m": (conductor.get("peso_kg_m") or 0.0) * 0.98,
    }


# ---------------------------------------------------------------------------
# Ecuacion de cambio de estado
# ---------------------------------------------------------------------------
def _a_y_b_cambio_estado(t0, T0, p0, ar, t, p, alfa, E, S):
    """Coeficientes A y B de la cubica T^3 + A*T^2 - B = 0."""
    A = (alfa * E * S * (t - t0) - T0
         + (ar * ar * p0 * p0 * E * S) / (24.0 * T0 * T0))
    B = (ar * ar * p * p * E * S) / 24.0
    return A, B


def _raiz_positiva_cubica(A, B, tol=1e-6, max_iter=200):
    """Raiz real positiva de T^3 + A*T^2 - B = 0 (B > 0 => una unica raiz
    positiva, por la regla de Descartes). Bisecton sobre f(T)=T^3+A*T^2-B."""
    if B <= 0:
        return None

    def f(T):
        return T * T * T + A * T * T - B

    # Acotar: la raiz esta entre 0 y un valor donde f > 0
    lo = 0.0
    hi = 1.0
    while f(hi) < 0:
        hi *= 2.0
        if hi > 1e9:
            return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if f(mid) == 0:
            return mid
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
        if (hi - lo) < tol:
            return (lo + hi) / 2.0
    return (lo + hi) / 2.0


def tension_cambio_estado(t0, T0, p0, ar, t, p, alfa, E, S):
    """Tension Tf [daN] de la condicion objetivo (t, p) partiendo del estado
    inicial (t0, T0, p0) con vano de regulacion ar [m]. Subprograma 6."""
    if T0 is None or T0 <= 0 or ar is None or ar <= 0:
        return None
    A, B = _a_y_b_cambio_estado(t0, T0, p0, ar, t, p, alfa, E, S)
    return _raiz_positiva_cubica(A, B)


def t0_desde_tension_condicion(t0, T_nueva, p_cond, t_cond, ar, p0, alfa, E, S):
    """Tension del estado EDS T0 [daN] que produce 'T_nueva' [daN] en la
    condicion reglamentaria (t_cond, p_cond). Inversa del Subprograma 6:

        B = (ar^2*p_cond^2*E*S)/24
        C = (B - T_nueva^3)/T_nueva^2 - alfa*E*S*(t_cond - t0)
        K = (ar^2*p0^2*E*S)/24
        T0^3 + C*T0^2 - K = 0   -> raiz real positiva

    Devuelve None si los datos no son validos."""
    if T_nueva is None or T_nueva <= 0 or ar is None or ar <= 0:
        return None
    if p_cond is None or p_cond <= 0 or S is None or S <= 0:
        return None
    B = (ar * ar * p_cond * p_cond * E * S) / 24.0
    C = (B - T_nueva ** 3) / (T_nueva * T_nueva) - alfa * E * S * (t_cond - t0)
    K = (ar * ar * p0 * p0 * E * S) / 24.0
    return _raiz_positiva_cubica(C, K)



# ---------------------------------------------------------------------------
# Flecha por vano
# ---------------------------------------------------------------------------
def flecha_vano(a, h, p, Tf):
    """Flecha [m] del vano de longitud 'a' [m] y desnivel 'h' [m] con
    sobrecarga 'p' [daN/m] y tension 'Tf' [daN]. Subprograma 6."""
    if a is None or Tf is None or Tf <= 0 or p is None:
        return None
    b = math.hypot(a, h or 0.0)
    f = (a * b * p) / (8.0 * Tf) * (1.0 + (a * a * p * p) / (48.0 * Tf * Tf))
    return f


# ---------------------------------------------------------------------------
# Tension en el punto bajo desde la tension en el apoyo (Subprograma 5)
# ---------------------------------------------------------------------------
def tension_punto_bajo_desde_apoyo(TA, p, a, h):
    """Tension T0 en el punto mas bajo del vano dada la tension TA en el apoyo.
    Subprograma 5:
        b = sqrt(h^2 + a^2)
        T0 = ((TA - p*|h|/2) + sqrt((TA - p*|h|/2)^2 - b^2*p^2/2)) / (2*b/a)
    """
    b = math.hypot(a, h or 0.0)
    interior = (TA - p * abs(h) / 2.0) ** 2 - (b * b * p * p) / 2.0
    if interior < 0:
        return None
    T0 = ((TA - p * abs(h) / 2.0) + math.sqrt(interior)) / (2.0 * b / a)
    return T0


def tension_en_apoyo(T0, p, a, h):
    """Tension TA en el apoyo mas alto desde la tension en el punto bajo.
    (inversa del Subprograma 5; util para comprobar resultados)."""
    b = math.hypot(a, h or 0.0)
    return T0 * (b / a) + p * abs(h) / 2.0


# ---------------------------------------------------------------------------
# Vano de regulacion
# ---------------------------------------------------------------------------
def vano_regulacion(vanos):
    """ar = sqrt(suma(a^3) / suma(a)). None si no hay vanos validos."""
    a3 = [a * a * a for a in vanos if a and a > 0]
    s = [a for a in vanos if a and a > 0]
    if not a3 or sum(s) == 0:
        return None
    return math.sqrt(sum(a3) / sum(s))



# ---------------------------------------------------------------------------
# Condiciones reglamentarias por defecto (Subprograma 6 de Paloma)
# ---------------------------------------------------------------------------
def condiciones_reglamentarias(categoria="no_especial"):
    """Lista de condiciones estandar: (nombre, temperatura_C, clave_sobrecarga).
    'categoria' especial -> 85 C en la condicion de temperatura maxima."""
    t_max = 85.0 if str(categoria).lower() in ("especial", "s") else 50.0
    return [
        ("15 C + Viento", 15.0, "Sv120"),
        ("Temp. Max (%.0f C)" % t_max, t_max, "Peso cable"),
        ("0 C + Hielo", 0.0, "Sh"),
    ]


# ---------------------------------------------------------------------------
# Recalculo de tensiones y flechas de una linea
# ---------------------------------------------------------------------------
def recalcular_tensiones_flechas(vanos, desniveles, estado_inicial,
                                 sobrecargas, alfa, E, S,
                                 condiciones=None):
    """Recalcula tensiones y flechas de todos los tramos de la linea.

    Parametros:
      vanos:        lista de longitudes de vano [m] (un valor por tramo).
      desniveles:   lista de desniveles [m] (un valor por tramo).
      estado_inicial: dict {'t0_C':.., 'T0_daN':.., 'p0_daN_m':..} (EDS).
      sobrecargas:  dict con {'Sv120':.., 'Sh':.., 'Peso cable':..} (comun)
                    o una lista de dicts, uno por tramo.
      alfa, E, S:   propiedades del conductor (alfa 1/C, E daN/mm2, S mm2).
      condiciones:  lista de (nombre, t_C, clave_sobrecarga).

    Devuelve {i_tramo: {nombre_cond: {'T_daN':.., 'F_m':..}}}.
    """
    if condiciones is None:
        condiciones = condiciones_reglamentarias()

    n = len(vanos)
    ar = vano_regulacion(vanos)
    if ar is None or n == 0:
        return {}

    t0 = estado_inicial.get("t0_C", 10.0)
    T0 = estado_inicial.get("T0_daN")
    p0 = estado_inicial.get("p0_daN_m")

    resultado = {}
    for i in range(n):
        a = vanos[i]
        h = desniveles[i] if i < len(desniveles) else 0.0
        if isinstance(sobrecargas, dict) and "Sh" in sobrecargas:
            sob = sobrecargas
        else:
            sob = sobrecargas[i] if i < len(sobrecargas) else {}
        p_cable = sob.get("Peso cable")
        resultado[i] = {}
        for nombre, t, clave_p in condiciones:
            p = sob.get(clave_p)
            if p is None or p_cable is None:
                continue
            # La tension reglamentaria se calcula con el vano de regulacion ar
            Tf = tension_cambio_estado(t0, T0, p0, ar, t, p, alfa, E, S)
            if Tf is None:
                continue
            f = flecha_vano(a, h, p, Tf)
            resultado[i][nombre] = {"T_daN": Tf, "F_m": f}
    return resultado


if __name__ == "__main__":
    # ---- Validación contra el Excel de demostración (tramo 2-3) ----
    # Estado inicial: t0=10 C, T0=196 daN (EDS a 10 C), p0=peso cable
    alfa = 1.91e-05
    E = 7900.0
    S = 54.6
    p0 = 0.1853
    T0 = 196.0
    t0 = 10.0
    ar = 89.0
    a = 89.0
    h = 0.72
    Sv120 = 0.5965
    Sh = 0.7387

    print("== VALIDACIÓN: tramo 2-3 del ejemplo ==")
    casos = [
        ("15 C + Viento", 15.0, Sv120, 380.0),
        ("0 C + Hielo", 0.0, Sh, 484.0),
        ("50 C", 50.0, p0, 114.0),
    ]
    for nombre, t, p, esperado in casos:
        Tf = tension_cambio_estado(t0, T0, p0, ar, t, p, alfa, E, S)
        f = flecha_vano(a, h, p, Tf)
        print("  %-15s T=%.2f daN (Excel: %s)  f=%.3f m"
              % (nombre, Tf, esperado, f))
    print("  vano_regulacion([10,89,140]) =", vano_regulacion([10, 89, 140]))
