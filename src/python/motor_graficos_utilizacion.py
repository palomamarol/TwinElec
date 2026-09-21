# -*- coding: utf-8 -*-
"""
motor_graficos_utilizacion.py
=============================
Resuelve numericamente las rectas de los graficos de utilizacion del Tema 10.

Partiendo de los datos ensamblados por datos_apoyos_excel.datos_completos_para_graficos
y de las ecuaciones de graficos_utilizacion_ecuaciones, aplica la ecuacion
resistente:

    Fu*h'/(2*d1) = F*h/(2*d1) + P/4

y devuelve, para cada apoyo, los coeficientes (a, b, c) de cada recta en la
forma  a*L + b*N + c = 0  (o una recta vertical L = cte para el vano maximo).

USO:
    from motor_graficos_utilizacion import calcular_rectas_apoyo
    rectas = calcular_rectas_apoyo(apoyo, sobrecarga, conductor, viento_kmh,
                                   tension_linea_kv)
"""
import math

from graficos_utilizacion_ecuaciones import PORCENTAJES_DESEQUILIBRIO


def _grados_a_rad(grados):
    return math.radians(grados)


def _constante_catenaria(tension_daN, sobrecarga_daN_m):
    """c = T/S (constante de catenaria) si ambos valores estan disponibles."""
    if tension_daN is None or sobrecarga_daN_m in (None, 0):
        return None
    return tension_daN / sobrecarga_daN_m


def _es_viento_140(viento_kmh):
    return float(viento_kmh or 120.0) >= 140.0


def calcular_rectas_apoyo(apoyo, sob, conductor, viento_kmh=120.0,
                          tension_linea_kv=None):
    """Devuelve {clave_recta: {"a","b","c","label", ...}} para un apoyo.

    Si algun dato esencial falta (Fu, h o d1), devuelve {}.
    """
    tipo = apoyo["tipo_clave"]
    zona = apoyo["zona_clave"]
    ten = apoyo.get("tensiones_daN") or {}
    cad = apoyo.get("cadena_caracteristicas") or {}

    # --- Datos esenciales del apoyo: Fu por hipotesis (catalogo Unesa) ---
    fu_por_hip = apoyo.get("Fu_por_hipotesis_daN") or {}
    fu_viento = fu_por_hip.get("viento 120")
    fu_hielo = fu_por_hip.get("hielo")
    fu_vh = fu_por_hip.get("hielo+viento 60km/h")
    fu_deseq = fu_por_hip.get("desequilibrio")
    h = apoyo.get("h_m")          # h = h-prima (altura al cdg del armado)
    hp = apoyo.get("h_prima_m")
    d1 = apoyo.get("d1_m")
    if fu_viento is None or h is None or hp is None or d1 is None:
        return {}
    ncad = apoyo.get("n_cadenas") or 0
    pcadf = cad.get("peso_daN") or 0.0
    clave_viento = ("esfuerzo_viento_140_daN" if _es_viento_140(viento_kmh)
                    else "esfuerzo_viento_120_daN")
    evcadf = cad.get(clave_viento) or 0.0
    evcadf60 = cad.get("esfuerzo_viento_60_daN") or 0.0
    lcad = cad.get("longitud_m") or 0.0

    # --- Datos del conductor y sobrecargas ---
    pF = sob.get("P_daN") or 0.0          # peso conductor [daN/m]
    dF = conductor["diametro_m"]          # diametro [m]
    vF = sob.get("P_v_max") or 0.0        # presion del viento [daN/m2]
    sv = sob.get("Sv")
    sh = sob.get("Sh")
    svm = sob.get("S_vm")
    svh = sob.get("S_vh")
    dmh = sob.get("dmh_m") or 0.0
    v60 = sob.get("V_vh") or 0.0

    # --- Tensiones por hipotesis ---
    tvf = ten.get("TVF")
    thf = ten.get("THF")
    tvhf = ten.get("TVHF")
    tvm = ten.get("TVM")
    t0h = ten.get("T0H")
    ttemp = ten.get("TTemp")
    t15v = ten.get("T15V")

    # --- Porcentaje de desequilibrio de tracciones (3a hipotesis) ---
    pct = 0.0
    tabla_pct = PORCENTAJES_DESEQUILIBRIO.get(tipo, {})
    if tabla_pct:
        pct = (tabla_pct["<=66 kV"] if (tension_linea_kv or 0.0) <= 66.0
               else tabla_pct[">66 kV"])

    # --- Constantes de catenaria ---
    cvf = _constante_catenaria(tvf, sv)
    cvhf = _constante_catenaria(tvhf, svh)

    # --- Geometria de angulo (beta=180 grad, alfa = angulo del apoyo) ---
    alfa = apoyo.get("angulo_sexagesimal")
    es_angulo = tipo.startswith("angulo")
    if es_angulo and alfa is not None:
        rad_a = _grados_a_rad(alfa)
        rad_b = _grados_a_rad(180.0)
        cb = math.cos((rad_b - rad_a) / 2.0)   # cos((beta-alfa)/2)
        s2 = 2.0 * math.cos(rad_a / 2.0)       # 2*cos(alfa/2) = parametro S
    else:
        cb = 0.0
        s2 = 0.0

    rectas = {}

    def guardar(clave, a, b, c, label, **extra):
        if a == 0.0 and b == 0.0:
            return
        item = {"a": a, "b": b, "c": c, "label": label}
        item.update(extra)
        rectas[clave] = item

    # ------------------------------------------------------------------
    # VANO MAXIMO por separacion de conductores (recta vertical L = cte)
    # ------------------------------------------------------------------
    D = apoyo.get("D_m")
    K = apoyo.get("K_vano_maximo")
    kp = apoyo.get("K_prima")
    dpp = apoyo.get("DPP_m")
    if D and K and kp is not None and dpp is not None and lcad is not None:
        fmx = ((D - kp * dpp) / K) ** 2 - lcad
        if fmx > 0 and ttemp and pF > 0:
            l_vano = math.sqrt(fmx * 8.0 * ttemp / pF)
            if zona in ("BC_no_especial", "BC_especial") and t0h and sh:
                l_hielo = math.sqrt(fmx * 8.0 * t0h / sh)
                l_vano = min(l_vano, l_hielo)
            rectas["vano_maximo"] = {
                "tipo": "vertical", "L": l_vano, "label": "Vano máximo",
            }

    # ------------------------------------------------------------------
    # RECTAS DE HIPOTESIS por tipo de apoyo
    # ------------------------------------------------------------------
    # ---------- ALINEACION (suspension, amarre, anclaje) ----------
    if tipo in ("alineacion_suspension", "alineacion_amarre", "alineacion_anclaje"):
        # 1a hipotesis: viento
        # Fu*h'/(2d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2d1) + [pF*(L+CVF*N)+PCADF*NCAD]/4
        if tvf is not None and cvf is not None and fu_viento is not None:
            a = 4.0 * dF * vF * h + 2.0 * d1 * pF
            b = 2.0 * d1 * pF * cvf
            c = (4.0 * evcadf * ncad * h + 2.0 * d1 * pcadf * ncad
                 - 4.0 * fu_viento * hp)
            guardar("1a", a, b, c, "1ª hipótesis (viento)")

        # 2a hipotesis: hielo (solo zonas B/C)
        # Fu*h'/(2d1) = [SH*L + THF*N + PCADF*NCAD]/4
        if zona in ("BC_no_especial", "BC_especial") and thf is not None and fu_hielo is not None:
            a = 2.0 * d1 * sh
            b = 2.0 * d1 * thf
            c = 2.0 * d1 * pcadf * ncad - 4.0 * fu_hielo * hp
            guardar("2a", a, b, c, "2ª hipótesis (hielo)")

        # 2a hipotesis viento+hielo
        # Fu*h'/(2d1) = [dmh*v60*L*h + EVCADF60*NCAD*h]/(2d1) + [SH*(L+CVHF*N)+PCADF*NCAD]/4
        if zona in ("BC_no_especial", "BC_especial") and tvhf is not None and cvhf is not None and fu_vh is not None:
            a = 4.0 * dmh * v60 * h + 2.0 * d1 * sh
            b = 2.0 * d1 * sh * cvhf
            c = (4.0 * evcadf60 * ncad * h + 2.0 * d1 * pcadf * ncad
                 - 4.0 * fu_vh * hp)
            guardar("2a_VH", a, b, c, "2ª hipótesis (viento+hielo)")

        # 3a hipotesis: desequilibrio de tracciones
        if zona == "A":
            # Fu*h'/(2d1) = %P*TVF*h/(2d1) + [pF*(L + CVF*N) + PCADF*NCAD]/4
            if tvf is not None and cvf is not None and fu_deseq is not None:
                a = 2.0 * d1 * pF
                b = 2.0 * d1 * pF * cvf
                c = (4.0 * pct * tvf * h + 2.0 * d1 * pcadf * ncad
                     - 4.0 * fu_deseq * hp)
                guardar("3a", a, b, c, "3ª hipótesis (deseq. tracciones)")
        elif zona == "BC_no_especial" and thf is not None and fu_deseq is not None:
            a = 2.0 * d1 * sh
            b = 2.0 * d1 * thf
            c = 4.0 * pct * thf * h + 2.0 * d1 * pcadf * ncad - 4.0 * fu_deseq * hp
            guardar("3a", a, b, c, "3ª hipótesis (deseq. tracciones)")
        elif zona == "BC_especial" and tvhf is not None and cvhf is not None and fu_deseq is not None:
            a = 2.0 * d1 * sh
            b = 2.0 * d1 * sh * cvhf
            c = 4.0 * pct * tvhf * h + 2.0 * d1 * pcadf * ncad - 4.0 * fu_deseq * hp
            guardar("3a", a, b, c, "3ª hipótesis (deseq. tracciones)")

    # ---------- ANGULO (suspension, amarre, anclaje) ----------
    elif tipo in ("angulo_suspension", "angulo_amarre", "angulo_anclaje"):
        # 1a hipotesis: viento (con cosenos de angulo)
        # Fu*h'/(2d1) = [dF*vF*L*h*Cb + EVCADF*NCAD*h]/(2d1) + T*h/(2d1)*S2 + [pF*(L+CVF*N)+PCADF*NCAD]/4
        if tvf is not None and cvf is not None and fu_viento is not None:
            a = 4.0 * dF * vF * h * cb + 2.0 * d1 * pF
            b = 2.0 * d1 * pF * cvf
            c = (4.0 * evcadf * ncad * h + 4.0 * tvf * h * s2
                 + 2.0 * d1 * pcadf * ncad - 4.0 * fu_viento * hp)
            guardar("1a", a, b, c, "1ª hipótesis (viento)")

        # 2a hipotesis: hielo (zonas B/C)
        # Fu*h'/(2d1) = THF*h/(2d1)*S2 + [SH*L + THF*N + PCADF*NCAD]/4
        if zona in ("BC_no_especial", "BC_especial") and thf is not None and fu_hielo is not None:
            a = 2.0 * d1 * sh
            b = 2.0 * d1 * thf
            c = 4.0 * thf * h * s2 + 2.0 * d1 * pcadf * ncad - 4.0 * fu_hielo * hp
            guardar("2a", a, b, c, "2ª hipótesis (hielo)")

        # 2a hipotesis viento+hielo
        if zona in ("BC_no_especial", "BC_especial") and tvhf is not None and cvhf is not None and fu_vh is not None:
            a = 4.0 * dmh * v60 * h * cb + 2.0 * d1 * sh
            b = 2.0 * d1 * sh * cvhf
            c = (4.0 * evcadf60 * ncad * h + 4.0 * tvhf * h * s2
                 + 2.0 * d1 * pcadf * ncad - 4.0 * fu_vh * hp)
            guardar("2a_VH", a, b, c, "2ª hipótesis (viento+hielo)")

        # 3a hipotesis: desequilibrio de tracciones
        if zona == "A":
            # T*h/(2d1)*S2 + %P*TVF*h/(2d1) + [pF*(L + CVF*N) + PCADF*NCAD]/4
            if tvf is not None and cvf is not None and fu_deseq is not None:
                a = 2.0 * d1 * pF
                b = 2.0 * d1 * pF * cvf
                c = (4.0 * tvf * h * s2 + 4.0 * pct * tvf * h
                     + 2.0 * d1 * pcadf * ncad - 4.0 * fu_deseq * hp)
                guardar("3a", a, b, c, "3ª hipótesis (deseq. tracciones)")
        elif zona == "BC_no_especial" and thf is not None and fu_deseq is not None:
            a = 2.0 * d1 * sh
            b = 2.0 * d1 * thf
            c = (4.0 * thf * h * s2 + 4.0 * pct * thf * h
                 + 2.0 * d1 * pcadf * ncad - 4.0 * fu_deseq * hp)
            guardar("3a", a, b, c, "3ª hipótesis (deseq. tracciones)")
        elif zona == "BC_especial" and tvhf is not None and cvhf is not None and fu_deseq is not None:
            a = 2.0 * d1 * sh
            b = 2.0 * d1 * sh * cvhf
            c = (4.0 * tvhf * h * s2 + 4.0 * pct * tvhf * h
                 + 2.0 * d1 * pcadf * ncad - 4.0 * fu_deseq * hp)
            guardar("3a", a, b, c, "3ª hipótesis (deseq. tracciones)")

    # ---------- PRINCIPIO / FINAL DE LINEA ----------
    elif tipo == "principio_final_de_linea":
        # 1a: Fu*h'/(2d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2d1) + %P*TVF*h/(2d1) + [pF*(L+CVF*N)+PCADF*NCAD]/4
        if tvf is not None and cvf is not None and fu_viento is not None:
            a = 4.0 * dF * vF * h + 2.0 * d1 * pF
            b = 2.0 * d1 * pF * cvf
            c = (4.0 * evcadf * ncad * h + 4.0 * pct * tvf * h
                 + 2.0 * d1 * pcadf * ncad - 4.0 * fu_viento * hp)
            guardar("1a", a, b, c, "1ª hipótesis (viento)")

        if zona in ("BC_no_especial", "BC_especial"):
            # 2a: Fu*h'/(2d1) = %P*THF*h/(2d1) + [SH*L + THF*N + PCADF*NCAD]/4
            if thf is not None and fu_hielo is not None:
                a = 2.0 * d1 * sh
                b = 2.0 * d1 * thf
                c = 4.0 * pct * thf * h + 2.0 * d1 * pcadf * ncad - 4.0 * fu_hielo * hp
                guardar("2a", a, b, c, "2ª hipótesis (hielo)")
            # 2a V+H: Fu*h'/(2d1) = [dmh*v60*L*h + EVCADF60*NCAD*h]/(2d1) + %P*TVHF*h/(2d1) + [SH*(L+CVHF*N)+PCADF*NCAD]/4
            if tvhf is not None and cvhf is not None and fu_vh is not None:
                a = 4.0 * dmh * v60 * h + 2.0 * d1 * sh
                b = 2.0 * d1 * sh * cvhf
                c = (4.0 * evcadf60 * ncad * h + 4.0 * pct * tvhf * h
                     + 2.0 * d1 * pcadf * ncad - 4.0 * fu_vh * hp)
                guardar("2a_VH", a, b, c, "2ª hipótesis (viento+hielo)")

    # ------------------------------------------------------------------
    # DESVIACION DE CADENA (solo apoyos de suspension)
    # Alineacion: tan(g) = [v/2*d*L + EVCad/2] / [p*L + TVM*N + PCad/2]
    # Angulo:     tan(g) = [2*TVM*Cb + v/2*d*L*Cb + EVCad/2] / [p*L + TVM*N + PCad/2]
    # ------------------------------------------------------------------
    gamma = apoyo.get("gammamax_grados")
    if (tipo in ("alineacion_suspension", "angulo_suspension")
            and gamma is not None and tvm is not None):
        tg = math.tan(_grados_a_rad(gamma))
        # v = presion del viento a 120 km/h (60 daN/m2 si d<=16 mm, si no 50)
        v120 = 60.0 if dF <= 0.016 else 50.0
        evcad = cad.get("esfuerzo_viento_120_daN") or 0.0
        pcad = cad.get("peso_daN") or 0.0
        if tipo == "angulo_suspension":
            a = tg * pF - v120 * dF * cb / 2.0
            c = tg * pcad / 2.0 - 2.0 * tvm * cb - evcad / 2.0
        else:
            a = tg * pF - v120 * dF / 2.0
            c = tg * pcad / 2.0 - evcad / 2.0
        b = tg * tvm
        guardar("desviacion_cadena", a, b, c,
                "Desviación de la cadena (%.1f°)" % gamma)

    return rectas

