# -*- coding: utf-8 -*-
"""
generar_png_graficos.py
=======================
Genera los graficos de utilizacion de cada apoyo (Tema 10) con el formato
del codigo MATLAB de referencia:

  - fondo de figura oscuro [0.1 0.1 0.1] y fondo del plot [0.15 0.15 0.15]
  - rejilla [0.5 0.5 0.5]
  - colores de rectas identicos al MATLAB (viento, hielo, V+H, desequilibrio,
    oscilacion; vano maximo en rojo discontinuo; punto del apoyo en magenta)
  - DOS VISTAS por apoyo (como el MATLAB):
        vista 'U' (cerca): L en [0, ~800],  N en [-1, 1]
        vista 'V' (lejos): L en [0, 1200],  N que cubre todas las rectas
  - zona utilizable rellena en verde con transparencia
  - leyenda blanca en el noreste de cada panel

Salida:
  unity/Assets/Resources/graficos_utilizacion/apoyo_N.png
  unity/Assets/Resources/graficos_utilizacion/apoyo_N.pdf

GENERAL: funciona para cualquier apoyo de cualquier Excel (todo sale del JSON).
USO:  py generar_png_graficos.py
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont
from twinelec_paths import assets_dir

RUTA_JSON = str(assets_dir() / "graficos_utilizacion.json")
RUTA_SALIDA = str(assets_dir() / "Resources" / "graficos_utilizacion")

# ---------------------------------------------------------------------------
# Colores estilo MATLAB
# ---------------------------------------------------------------------------
COLOR_FIG = (26, 26, 26)            # [0.1  0.1  0.1 ] fondo de la figura
COLOR_AX = (38, 38, 38)             # [0.15 0.15 0.15] fondo del plot
COLOR_GRID = (128, 128, 128)        # [0.5  0.5  0.5 ] rejilla
COLOR_TEXTO = (235, 235, 235)
COLOR_TEXTO_SUAVE = (165, 165, 165)
COLOR_EJE = (200, 200, 200)

COLOR_RECTA = {
    "1a": (0, 114, 189),            # azul     [0     0.447 0.741]
    "2a": (217, 83, 25),            # naranja  [0.85  0.325 0.098]
    "2a_VH": (237, 177, 32),        # amarillo [0.929 0.694 0.125]
    "3a": (126, 47, 142),           # morado   [0.494 0.184 0.556]
    "desviacion_cadena": (119, 172, 48),  # verde [0.466 0.674 0.188]
    "vano_maximo": (255, 0, 0),     # rojo (xline --r)
    "cruceta": (120, 120, 120),
}
COLOR_ZONA = (0, 255, 0, 51)        # verde con FaceAlpha 0.2
COLOR_PUNTO = (255, 0, 255)         # magenta (m.)
COLOR_VANO_MAX = (255, 0, 0)

L_CERCA = 800.0                     # limite L de la vista 'cerca' (U)
L_LEJOS = 1200.0                    # limite L de la vista 'lejos' (V)
N_LEJOS_DEF = (-20.0, 80.0)         # rango N por defecto de la vista 'lejos'


def _fuente(tamano):
    try:
        return ImageFont.truetype("arial.ttf", tamano)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", tamano)
        except Exception:
            return ImageFont.load_default()


def _fmt(valor, dec=2):
    if valor is None:
        return "-"
    try:
        return ("%." + str(dec) + "f") % float(valor)
    except Exception:
        return str(valor)


def _fmt_numero(v):
    """Formato corto para las marcas de los ejes (0, 200, 400... / -1, -0.5...)."""
    if v is None:
        return "-"
    if abs(v) >= 100:
        return "%d" % round(v)
    texto = ("%.1f" % v).rstrip("0").rstrip(".")
    return texto


def _texto_envolviendo(d, texto, x, y, ancho_max, fuente, fill):
    """Dibuja 'texto' partido en lineas para que no supere 'ancho_max' px.
    Devuelve la coordenada y de la siguiente linea."""
    palabras = str(texto).split(" ")
    linea = ""
    for palabra in palabras:
        prueba = (linea + " " + palabra).strip()
        if d.textlength(prueba, font=fuente) <= ancho_max:
            linea = prueba
        else:
            if linea:
                d.text((x, y), linea, font=fuente, fill=fill)
                y += fuente.size + 6
            linea = palabra
    if linea:
        d.text((x, y), linea, font=fuente, fill=fill)
        y += fuente.size + 6
    return y


# ---------------------------------------------------------------------------
# Etiquetas de la leyenda (nombres del codigo MATLAB de referencia)
# ---------------------------------------------------------------------------
def _label_matlab(clave, r, viento_kmh=120.0):
    if clave == "1a":
        return "Viento %d" % (140 if float(viento_kmh or 120.0) >= 140 else 120)
    if clave == "2a":
        return "Hielo Solo"
    if clave == "2a_VH":
        return "V+H 60"
    if clave == "3a":
        return "Desequilibrio"
    if clave == "desviacion_cadena":
        return "Hip. Oscilación"
    if clave == "vano_maximo":
        return "Vano Máximo"
    return r.get("label", clave)


def _color_recta(clave):
    return COLOR_RECTA.get(clave, (255, 255, 255))


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------
def _mapa(l, n, ax, ay, aw, ah, lmin, lmax, nmin, nmax):
    x = ax + (l - lmin) / (lmax - lmin) * aw
    y = ay + (nmax - n) / (nmax - nmin) * ah
    return x, y


def _segmento_recta(a, b, c, lmin, lmax, nmin, nmax, eps=1e-9):
    """Puntos (L, N) de la interseccion de a*L + b*N + c = 0 con el rectangulo
    [lmin, lmax] x [nmin, nmax]. Devuelve [p1, p2] (o [p] en tangencias), o None
    si la recta no toca el rectangulo."""
    pts = []

    def anadir(l, n):
        if (lmin - 1e-6 <= l <= lmax + 1e-6
                and nmin - 1e-6 <= n <= nmax + 1e-6):
            for (pl, pn) in pts:
                if abs(pl - l) < 1e-3 and abs(pn - n) < 1e-3:
                    return
            pts.append((l, n))

    if abs(b) > eps:
        for l in (lmin, lmax):
            anadir(l, (-a * l - c) / b)
    if abs(a) > eps:
        for n in (nmin, nmax):
            anadir((-b * n - c) / a, n)
    if len(pts) >= 2:
        pts.sort()
        return [pts[0], pts[-1]]
    if len(pts) == 1:
        return [pts[0]]
    return None


def _linea_discontinua(d, p1, p2, fill, width=2, tramo=9, hueco=7):
    """Dibuja una linea discontinua entre dos puntos (coordenadas de pixel)."""
    import math
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    longitud = math.hypot(dx, dy)
    if longitud < 1e-6:
        return
    ux, uy = dx / longitud, dy / longitud
    paso = tramo + hueco
    t = 0.0
    while t < longitud:
        fin = min(t + tramo, longitud)
        d.line([p1[0] + ux * t, p1[1] + uy * t,
                p1[0] + ux * fin, p1[1] + uy * fin],
               fill=fill, width=width)
        t += paso


def _punto_en_zona(l, n, zona):
    if not zona or len(zona) < 3:
        return False
    dentro = False
    j = len(zona) - 1
    for i in range(len(zona)):
        xi, yi = zona[i][0], zona[i][1]
        xj, yj = zona[j][0], zona[j][1]
        if (yi > n) != (yj > n) and l < (xj - xi) * (n - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


# ---------------------------------------------------------------------------
# Limites de las dos vistas
# ---------------------------------------------------------------------------
def _lmax_cerca(apoyo, base=L_CERCA):
    """Limite L de la vista 'cerca': al menos 'base' m, ampliado si la zona
    utilizable, el vano maximo o el punto real lo necesitan (hasta L_LEJOS)."""
    lmax = base
    for p in (apoyo.get("zona_utilizable") or []):
        if p[0] > lmax:
            lmax = p[0] * 1.15
    lr = apoyo.get("punto_real_L")
    if lr is not None and lr * 1.3 > lmax:
        lmax = lr * 1.3
    for clave, r in (apoyo.get("rectas") or {}).items():
        if r.get("tipo") == "vertical" and r.get("L", 0) * 1.05 > lmax:
            lmax = r["L"] * 1.05
    return min(lmax, L_LEJOS)


def _n_limites_cerca(apoyo):
    """Rango N de la vista 'cerca': [-1, 1] ampliado si el punto o la zona
    utilizable quedan fuera."""
    nmin, nmax = -1.0, 1.0
    for p in (apoyo.get("zona_utilizable") or []):
        nmin = min(nmin, p[1] - 0.05)
        nmax = max(nmax, p[1] + 0.05)
    nr = apoyo.get("punto_real_N")
    if nr is not None:
        nmin = min(nmin, nr - 0.05)
        nmax = max(nmax, nr + 0.05)
    return nmin, nmax


def _n_limites_lejos(apoyo, lmax=L_LEJOS):
    """Rango N de la vista 'lejos': cubre las rectas, el punto real y la zona
    utilizable con un ENCUADRE ACEPTABLE. Las rectas casi perpendiculares a
    los ejes (p. ej. N(L=0) = +450) NO deben aplanar el resto: se recorta el
    12 % de los valores mas extremos de las rectas antes de fijar el rango
    (el punto y la zona SIEMPRE se incluyen). El resultado se amplia al
    rango por defecto [-20, 80] (estilo MATLAB) y se limita a [-200, 400]."""
    fijos = []
    nr = apoyo.get("punto_real_N")
    if nr is not None:
        fijos.append(float(nr))
    for p in (apoyo.get("zona_utilizable") or []):
        fijos.append(float(p[1]))

    recta_valores = []
    for clave, r in (apoyo.get("rectas") or {}).items():
        if r.get("tipo") == "vertical":
            continue
        a, b, c = r.get("a", 0), r.get("b", 0), r.get("c", 0)
        if abs(b) < 1e-9:
            continue
        for l in (0.0, lmax):
            n = (-a * l - c) / b
            if abs(n) < 1e6:
                recta_valores.append(n)

    nucleo = []
    if recta_valores:
        orden = sorted(recta_valores)
        corte = max(0, int(round(len(orden) * 0.12)))
        nucleo = orden[corte:len(orden) - corte] or orden

    todos = nucleo + fijos
    if not todos:
        return N_LEJOS_DEF
    nmin = min(todos)
    nmax = max(todos)
    margen = max(0.10 * (nmax - nmin), 3.0)
    nmin -= margen
    nmax += margen
    # Siempre incluye el rango por defecto (estilo MATLAB)
    nmin = min(nmin, N_LEJOS_DEF[0])
    nmax = max(nmax, N_LEJOS_DEF[1])
    # Limites de seguridad para no aplanar la zona utilizable
    nmin = max(nmin, -200.0)
    nmax = min(nmax, 400.0)
    return nmin, nmax


# ---------------------------------------------------------------------------
# Panel (una vista del grafico)
# ---------------------------------------------------------------------------
def _dibujar_leyenda(d, apoyo, viento_kmh, ax, ay, aw, ah, f_ley):
    """Leyenda blanca en el noreste del panel (como MATLAB)."""
    items = []
    for clave, r in (apoyo.get("rectas") or {}).items():
        items.append((_color_recta(clave), _label_matlab(clave, r, viento_kmh)))
    items.append((COLOR_PUNTO, "Apoyo"))

    ancho_max = aw * 0.55
    filas = []
    for color, label in items:
        if d.textlength(label, font=f_ley) > ancho_max:
            label = label[:max(8, int(ancho_max // (f_ley.size * 0.55)))] + "…"
        filas.append((color, label))

    alto_linea = f_ley.size + 10
    total = alto_linea * len(filas) + 10
    lx = ax + aw - ancho_max - 10
    ly = ay + 8
    # fondo semitransparente para legibilidad
    d.rectangle([lx - 6, ly - 4, ax + aw - 4, ly + total],
                fill=(10, 10, 10, 170))
    for color, label in filas:
        d.line([lx, ly + f_ley.size // 2, lx + 22, ly + f_ley.size // 2],
               fill=color, width=3)
        d.text((lx + 30, ly), label, font=f_ley, fill=COLOR_TEXTO)
        ly += alto_linea


def _dibujar_panel(d, apoyo, viento_kmh, titulo, ax, ay, aw, ah,
                   lmax, nmin, nmax, f_eje, f_ley):
    lmin = 0.0
    rectas = apoyo.get("rectas") or {}

    # Fondo del plot
    d.rectangle([ax, ay, ax + aw, ay + ah], fill=COLOR_AX,
                outline=COLOR_EJE, width=2)

    # Rejilla (vertical x6, horizontal x5)
    for i in range(6):
        l = lmin + (lmax - lmin) * i / 5
        x = ax + (l - lmin) / (lmax - lmin) * aw
        d.line([x, ay, x, ay + ah], fill=COLOR_GRID, width=1)
    for i in range(5):
        n = nmin + (nmax - nmin) * i / 4
        y = ay + (nmax - n) / (nmax - nmin) * ah
        d.line([ax, y, ax + aw, y], fill=COLOR_GRID, width=1)

    # Zona utilizable (relleno verde semitransparente)
    zona = apoyo.get("zona_utilizable") or []
    if len(zona) >= 3:
        pts = [_mapa(p[0], p[1], ax, ay, aw, ah, lmin, lmax, nmin, nmax)
               for p in zona]
        d.polygon(pts, fill=COLOR_ZONA)

    # Rectas
    for clave, r in rectas.items():
        color = _color_recta(clave)
        if r.get("tipo") == "vertical":
            lv = r.get("L", 0.0)
            if lmin <= lv <= lmax:
                p1 = _mapa(lv, nmin, ax, ay, aw, ah, lmin, lmax, nmin, nmax)
                p2 = _mapa(lv, nmax, ax, ay, aw, ah, lmin, lmax, nmin, nmax)
                _linea_discontinua(d, p1, p2, COLOR_VANO_MAX, width=3)
            continue
        seg = _segmento_recta(r.get("a", 0), r.get("b", 0), r.get("c", 0),
                              lmin, lmax, nmin, nmax)
        if not seg:
            continue
        if len(seg) == 1:
            px, py = _mapa(seg[0][0], seg[0][1], ax, ay, aw, ah,
                           lmin, lmax, nmin, nmax)
            d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=color)
            continue
        p1 = _mapa(seg[0][0], seg[0][1], ax, ay, aw, ah, lmin, lmax, nmin, nmax)
        p2 = _mapa(seg[1][0], seg[1][1], ax, ay, aw, ah, lmin, lmax, nmin, nmax)
        if clave == "vano_maximo":
            _linea_discontinua(d, p1, p2, COLOR_VANO_MAX, width=3)
        else:
            d.line([p1, p2], fill=color, width=4)

    # Punto real del apoyo (magenta, estilo MATLAB 'm.')
    lr = apoyo.get("punto_real_L")
    nr = apoyo.get("punto_real_N")
    if lr is not None and nr is not None:
        px, py = _mapa(lr, nr, ax, ay, aw, ah, lmin, lmax, nmin, nmax)
        d.ellipse([px - 8, py - 8, px + 8, py + 8], fill=COLOR_PUNTO,
                  outline=(255, 255, 255), width=2)
        f_punto = _fuente(f_ley.size + 4)
        d.text((px + 14, py - 12), " a", font=f_punto, fill=COLOR_PUNTO)

    # Titulo del panel
    d.text((ax + 6, ay - f_eje.size - 8), titulo,
           font=_fuente(f_eje.size + 4), fill=COLOR_TEXTO)

    # Ejes, marcas y etiquetas
    d.line([ax, ay + ah, ax + aw, ay + ah], fill=COLOR_EJE, width=2)
    d.line([ax, ay, ax, ay + ah], fill=COLOR_EJE, width=2)
    d.text((ax + aw // 2 - 40, ay + ah + 6), "L (Vano)",
           font=f_eje, fill=COLOR_TEXTO)
    # La N se separa de las marcas numericas del eje. Antes coincidia con la
    # marca central (p. ej. "-60N") y en el primer panel podia quedar fuera.
    d.text((ax - 64, ay + ah // 2 - f_eje.size // 2), "N",
           font=f_eje, fill=COLOR_TEXTO)
    for i in range(6):
        l = lmin + (lmax - lmin) * i / 5
        x = ax + (l - lmin) / (lmax - lmin) * aw
        d.text((x - 14, ay + ah + f_eje.size + 8), _fmt_numero(l),
               font=f_eje, fill=COLOR_TEXTO_SUAVE)
    for i in range(5):
        n = nmin + (nmax - nmin) * i / 4
        y = ay + (nmax - n) / (nmax - nmin) * ah
        etiqueta = _fmt_numero(n)
        ancho_etiqueta = d.textlength(etiqueta, font=f_eje)
        d.text((ax - 10 - ancho_etiqueta, y - f_eje.size // 2), etiqueta,
               font=f_eje, fill=COLOR_TEXTO_SUAVE)

    # Leyenda (noreste)
    _dibujar_leyenda(d, apoyo, viento_kmh, ax, ay, aw, ah, f_ley)


# ======================================================================
# Grafico completo (cabecera + dos vistas)
# ======================================================================
def dibujar_grafico(apoyo, ancho, alto, viento_kmh=120.0):
    """Dibuja el grafico de utilizacion de un apoyo con formato MATLAB:
    fondo oscuro, dos paneles (cerca 'U' y lejos 'V') lado a lado."""
    img = Image.new("RGB", (ancho, alto), COLOR_FIG)
    d = ImageDraw.Draw(img, "RGBA")

    f_tit = _fuente(max(20, ancho // 48))
    f_sub = _fuente(max(14, ancho // 80))
    f_eje = _fuente(max(11, ancho // 95))
    f_ley = _fuente(max(11, ancho // 100))

    margen = max(12, ancho // 40)

    # --- Cabecera (titulo + datos del apoyo) ---
    y = margen
    d.text((margen, y),
           "GRÁFICO DE UTILIZACIÓN — APOYO Nº %s" % apoyo.get("numero"),
           font=f_tit, fill=COLOR_TEXTO)
    y += f_tit.size + 8

    valido = _punto_en_zona(apoyo.get("punto_real_L"), apoyo.get("punto_real_N"),
                            apoyo.get("zona_utilizable") or [])
    texto_veredicto = ("APOYO VÁLIDO" if valido else "APOYO NO VÁLIDO")

    y = _texto_envolviendo(
        d,
        "Tipo: %s (%s)   |   Zona: %s (%s)   |   Montaje: %s   |   "
        "L real = %s m   N real = %s   |   %s"
        % (apoyo.get("tipo"), apoyo.get("tipo_texto"), apoyo.get("zona"),
           apoyo.get("zona_clave"), apoyo.get("montaje"),
           _fmt(apoyo.get("punto_real_L")),
           _fmt(apoyo.get("punto_real_N"), 3), texto_veredicto),
        margen, y, ancho - 2 * margen, f_sub, COLOR_TEXTO_SUAVE)
    y = _texto_envolviendo(
        d,
        "Fu = %s daN   |   h = h' = %s m   |   d1 = %s m   |   K = %s   "
        "K' = %s   DPP = %s m   |   gamma_cadena = %s°"
        % (_fmt(apoyo.get("Fu_daN")), _fmt(apoyo.get("h_m")),
           _fmt(apoyo.get("d1_m")), _fmt(apoyo.get("K_vano_maximo")),
           _fmt(apoyo.get("K_prima")), _fmt(apoyo.get("DPP_m")),
           _fmt(apoyo.get("gammamax_grados"), 1)),
        margen, y, ancho - 2 * margen, f_sub, COLOR_TEXTO_SUAVE)
    y = _texto_envolviendo(
        d,
        "HREF = %s m   |   Sep. conductores = %s m   |   LCAD = %s m   |   "
        "solera = 0.2 m"
        % (_fmt(apoyo.get("href_m")), _fmt(apoyo.get("sep_conductores_m")),
           _fmt(apoyo.get("lcad_m"))),
        margen, y, ancho - 2 * margen, f_sub, COLOR_TEXTO_SUAVE)
    # Reserva una banda propia para "Apoyo N - U/V". Con solo 10 px el titulo
    # de cada panel invadia la ultima linea de caracteristicas del apoyo.
    y += f_eje.size + 18

    # --- Dos paneles lado a lado ---
    margen_izquierdo = max(100, ancho // 12)
    margen_derecho = max(24, ancho // 40)
    # El hueco alberga las marcas y la N del segundo eje vertical.
    hueco = max(68, ancho // 18)
    ax = margen_izquierdo
    aw = (ancho - margen_izquierdo - margen_derecho - hueco) // 2
    ay = y
    ah = alto - y - margen - int(f_eje.size * 2.6)

    # Vista 'cerca' (U)
    lmax_c = _lmax_cerca(apoyo)
    nmin_c, nmax_c = _n_limites_cerca(apoyo)
    _dibujar_panel(d, apoyo, viento_kmh, "Apoyo %s - U" % apoyo.get("numero"),
                   ax, ay, aw, ah, lmax_c, nmin_c, nmax_c, f_eje, f_ley)

    # Vista 'lejos' (V)
    ax2 = ax + aw + hueco
    nmin_l, nmax_l = _n_limites_lejos(apoyo, L_LEJOS)
    _dibujar_panel(d, apoyo, viento_kmh, "Apoyo %s - V" % apoyo.get("numero"),
                   ax2, ay, aw, ah, L_LEJOS, nmin_l, nmax_l, f_eje, f_ley)

    return img


# ======================================================================
# Generadores
# ======================================================================
# Tamano PDF A4 apaisado a 200 dpi (297x210 mm)
A4_LANDSCAPE = (2339, 1654)
# Tamano PNG (misma proporcion que la figura MATLAB 1200x500)
PNG_SIZE = (1200, 520)


def _leer_documento(ruta_json):
    with open(ruta_json, encoding="utf-8") as f:
        return json.load(f)


def generar_pngs(ruta_json=RUTA_JSON, salida_dir=RUTA_SALIDA):
    documento = _leer_documento(ruta_json)
    viento_kmh = (documento.get("linea") or {}).get("viento_kmh", 120.0)
    os.makedirs(salida_dir, exist_ok=True)
    # Orden por numero SIEMPRE: cada PNG 'apoyo_N.png' debe contener el grafico
    # del apoyo cuyo numero es N, sea cual sea el orden del array en el JSON.
    for apoyo in sorted(documento.get("apoyos", []),
                        key=lambda a: a.get("numero") or 0):
        n = apoyo.get("numero")
        img = dibujar_grafico(apoyo, PNG_SIZE[0], PNG_SIZE[1], viento_kmh)
        salida = os.path.join(salida_dir, "apoyo_%d.png" % n)
        img.save(salida)
        print("OK PNG", salida)


def generar_pdfs(ruta_json=RUTA_JSON, salida_dir=RUTA_SALIDA,
                 tamano=A4_LANDSCAPE):
    """PDF A4 apaisado a pagina completa por apoyo (estilo MATLAB oscuro)."""
    documento = _leer_documento(ruta_json)
    viento_kmh = (documento.get("linea") or {}).get("viento_kmh", 120.0)
    os.makedirs(salida_dir, exist_ok=True)
    for apoyo in sorted(documento.get("apoyos", []),
                        key=lambda a: a.get("numero") or 0):
        n = apoyo.get("numero")
        img = dibujar_grafico(apoyo, tamano[0], tamano[1], viento_kmh)
        salida = os.path.join(salida_dir, "apoyo_%d.pdf" % n)
        try:
            img.save(salida, "PDF", resolution=200)
            print("OK PDF", salida)
        except PermissionError:
            print("!! PDF BLOQUEADO (cierra el visor y regenera):", salida)


if __name__ == "__main__":
    generar_pngs()
    generar_pdfs()

