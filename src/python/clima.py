# -*- coding: utf-8 -*-
"""
clima.py — Obtención de meteorología real (DLR operativo)
==========================================================
Parte del DLR operativo: consulta las APIs de AEMET o SiAR (misma lógica que
EnerFlux del TFG de Manuel) para la estación meteorológica más cercana a la
línea del Excel/.doc activo, y guarda los datos actuales en
unity/Assets/meteorologia_actual.json para que Unity los consuma.

GENERAL: funciona para CUALQUIER línea. Toma las coordenadas UTM del .doc
de apoyos activo (igual que principal.py), convierte a lat/lon, busca la
estación más cercana en el catálogo de EnerFlux y consulta su API.
RESILIENCIA: si la API falla, clima.py reintenta automáticamente la petición
(por defecto 3 intentos con backoff exponencial) y, si sigue sin responder,
usa como respaldo la ÚLTIMA OBSERVACIÓN REAL VÁLIDA guardada en
unity/Assets/meteorologia_ultima_valida.json en lugar de inventar
valores. Solo si tampoco hay caché, se usan valores manuales de respaldo.

Uso:
    uv run --no-project --offline python clima.py
        (una vez: obtiene los datos actuales)
    uv run --no-project --offline python clima.py --bucle 30
        (cada 30 minutos: obtiene y actualiza automáticamente)

    Alternativa tras instalar las dependencias (requirements.txt) en el
    Python del sistema:
        py -3 clima.py [--bucle 30]
"""

import sys
import os
import json
import math
import time
import glob
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
import pandas as pd

from twinelec_paths import assets_dir, data_dir, REPOSITORY_ROOT

# ============================================================================
# CREDENCIALES DE API
# ============================================================================
# Nunca se guardan claves reales en el repositorio. Se buscan, por este orden:
#   1) variables de entorno TWINELEC_*
#   2) secrets.local.json (ignorado por Git)
#
# AEMET permite usar una misma API key para observación y predicción. La
# clave de predicción separada es opcional por si se quieren aislar cuotas.

# Directorio del propio script (raiz del TFG en el editor). Se usa para
# resolver rutas de ENTRADA y el secrets.local.json independientemente del CWD
# (al ejecutarse desde Unity, el CWD es la carpeta de trabajo de AppData).
_BASE = os.path.dirname(os.path.abspath(__file__))


def _ruta_secretos():
    configurada = os.environ.get("TWINELEC_SECRETS_FILE", "").strip()
    if configurada:
        return os.path.abspath(os.path.expanduser(configurada))
    return str(data_dir() / "secrets.local.json")


RUTA_SECRETOS_LOCAL = _ruta_secretos()
METEO_MAX_ANTIGUEDAD_MIN = float(
    os.environ.get("TWINELEC_METEO_MAX_AGE_MIN", "180")
)
# Reintentos de peticiones HTTP: nº de intentos y espera base del backoff
# exponencial (2 s, 4 s, ...) ante fallos de red o respuestas transitorias.
METEO_INTENTOS_API = int(os.environ.get("TWINELEC_METEO_INTENTOS_API", "3"))
METEO_ESPERA_REINTENTO_S = float(
    os.environ.get("TWINELEC_METEO_ESPERA_REINTENTO_S", "2.0")
)
# Códigos HTTP transitorios que merecen reintento (429 = límite AEMET temporal).
CODIGOS_HTTP_REINTENTABLES = {429, 500, 502, 503, 504}


def _publicar_json_atomico(ruta, documento):
    """Publica un contrato JSON completo para que Unity nunca lea media escritura."""
    directorio = os.path.dirname(os.path.abspath(ruta))
    if directorio:
        os.makedirs(directorio, exist_ok=True)
    ruta_temporal = f"{ruta}.{os.getpid()}.tmp"
    try:
        with open(ruta_temporal, "w", encoding="utf-8") as f:
            json.dump(documento, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(ruta_temporal, ruta)
    finally:
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)


def _cargar_secretos_locales():
    if not os.path.exists(RUTA_SECRETOS_LOCAL):
        return {}
    try:
        with open(RUTA_SECRETOS_LOCAL, encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            raise ValueError("el contenido debe ser un objeto JSON")
        return datos
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"No se pudo leer {RUTA_SECRETOS_LOCAL}: {exc}"
        ) from None


_SECRETOS_LOCALES = _cargar_secretos_locales()


def _credencial(nombre_entorno, nombre_json):
    return os.environ.get(nombre_entorno) or _SECRETOS_LOCALES.get(nombre_json)


API_KEY_AEMET = _credencial("TWINELEC_AEMET_API_KEY", "aemet_api_key")
API_KEY_PREDICCION = (
    _credencial(
        "TWINELEC_AEMET_PREDICCION_API_KEY",
        "aemet_prediccion_api_key",
    )
    or API_KEY_AEMET
)
API_KEY_SIAR = _credencial("TWINELEC_SIAR_API_KEY", "siar_api_key")


def _exigir_credencial(valor, nombre):
    if not valor:
        raise RuntimeError(
            f"Falta la credencial {nombre}. Configúrala mediante una variable "
            f"de entorno TWINELEC_* o en {RUTA_SECRETOS_LOCAL}."
        )
    return valor


def _get_api_seguro(url, *, contexto, params=None, timeout=30):
    """Realiza una petición con reintentos automáticos (backoff exponencial)
    sin filtrar credenciales en mensajes de error.

    Reintenta los fallos de red (ConnectTimeout, ConnectionError, ReadTimeout,
    etc.) y las respuestas HTTP transitorias (429, 5xx) hasta METEO_INTENTOS_API
    intentos con espera creciente (2 s, 4 s, 8 s...). Si todos fallan, lanza
    RuntimeError con el mismo formato de mensaje que antes.
    """
    ultima_excepcion = None
    ultimo_codigo = None
    for intento in range(1, METEO_INTENTOS_API + 1):
        try:
            respuesta = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            ultima_excepcion = exc
        else:
            if respuesta.status_code not in CODIGOS_HTTP_REINTENTABLES:
                return respuesta
            ultimo_codigo = respuesta.status_code
        if intento < METEO_INTENTOS_API:
            espera = METEO_ESPERA_REINTENTO_S * (2 ** (intento - 1))
            detalle = (
                f"HTTP {ultimo_codigo}"
                if ultimo_codigo is not None
                else type(ultima_excepcion).__name__
            )
            print(
                f"  ⚠️ {contexto}: {detalle} (intento {intento}/"
                f"{METEO_INTENTOS_API}); reintentando en {espera:.0f} s..."
            )
            time.sleep(espera)
    if ultimo_codigo is not None:
        raise RuntimeError(
            f"{contexto}: respuesta HTTP {ultimo_codigo} tras "
            f"{METEO_INTENTOS_API} intentos."
        ) from None
    raise RuntimeError(
        f"{contexto}: fallo de red ({type(ultima_excepcion).__name__})."
    ) from None


def _temperatura_aire_aemet(registro, valor_defecto=20.0):
    """Extrae la temperatura instantánea del aire de una observación AEMET.

    ``ta`` es la temperatura del aire del instante observado. ``tamax`` es
    una máxima acumulada y solo se admite como respaldo cuando ``ta`` falta.
    """
    valor = registro.get("ta")
    if valor is None or valor == "":
        valor = registro.get("tamax", valor_defecto)
    try:
        return float(valor)
    except (TypeError, ValueError):
        return float(valor_defecto)


def _km_h_a_m_s(velocidad_km_h):
    """Convierte la velocidad de predicción AEMET de km/h a m/s."""
    return float(velocidad_km_h) / 3.6


def hora_solar_aparente(fecha, hora_local, lon_deg, zona="Europe/Madrid"):
    """Convierte una fecha/hora civil local en hora solar aparente.

    Incluye la longitud de la línea, el desfase UTC de la fecha (con cambio
    verano/invierno) y la ecuación del tiempo. Devuelve horas decimales en
    el intervalo [0, 24).
    """
    fecha_iso = str(fecha).replace("/", "-")
    instante = datetime.strptime(
        f"{fecha_iso} {hora_local}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=ZoneInfo(zona))
    desfase_utc_h = instante.utcoffset().total_seconds() / 3600.0
    meridiano_huso_deg = 15.0 * desfase_utc_h
    n = instante.timetuple().tm_yday
    b = math.radians(360.0 * (n - 81) / 364.0)
    ecuacion_tiempo_min = (
        9.87 * math.sin(2.0 * b)
        - 7.53 * math.cos(b)
        - 1.5 * math.sin(b)
    )
    correccion_min = 4.0 * (float(lon_deg) - meridiano_huso_deg)
    hora_civil = instante.hour + instante.minute / 60.0
    return (hora_civil + (correccion_min + ecuacion_tiempo_min) / 60.0) % 24.0


def _fecha_observacion_iso(fecha, hora_local, zona="Europe/Madrid"):
    """Normaliza la fecha/hora meteorológica a ISO 8601 con zona horaria."""
    fecha_iso = str(fecha).replace("/", "-")
    instante = datetime.strptime(
        f"{fecha_iso} {hora_local}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=ZoneInfo(zona))
    return instante.isoformat(timespec="minutes")


def evaluar_calidad_meteorologica(
    datos,
    *,
    estado_api="OK",
    mensaje_api="",
    ahora=None,
    max_antiguedad_min=METEO_MAX_ANTIGUEDAD_MIN,
):
    """Clasifica una observación como OK, OBSOLETO, FALLBACK o ERROR."""
    ahora = ahora or datetime.now(ZoneInfo("Europe/Madrid"))
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=ZoneInfo("Europe/Madrid"))
    fecha_iso = datos.get("fecha_observacion")
    if not fecha_iso and datos.get("fecha") and datos.get("hora_local"):
        fecha_iso = _fecha_observacion_iso(datos["fecha"], datos["hora_local"])
    try:
        observacion = datetime.fromisoformat(fecha_iso) if fecha_iso else None
        if observacion is not None and observacion.tzinfo is None:
            observacion = observacion.replace(tzinfo=ZoneInfo("Europe/Madrid"))
    except (TypeError, ValueError):
        observacion = None

    antiguedad_min = None
    if observacion is not None:
        antiguedad_min = max(0.0, (ahora - observacion).total_seconds() / 60.0)

    estado_api = str(estado_api or "ERROR").upper()
    if estado_api == "FALLBACK":
        estado = "FALLBACK"
        valido = False
    elif estado_api == "CACHE":
        # Datos REALES de la última observación válida (la API falló, pero
        # usamos lo que ya teníamos). Se aplican mientras la observación siga
        # dentro de la antigüedad máxima operativa; si no, quedan como OBSOLETO
        # y Unity no los aplicará al cálculo.
        if antiguedad_min is not None and antiguedad_min <= float(max_antiguedad_min):
            estado = "OK"
            valido = True
        else:
            estado = "OBSOLETO"
            valido = False
    elif estado_api != "OK" or observacion is None:
        estado = "ERROR"
        valido = False
    elif antiguedad_min > float(max_antiguedad_min):
        estado = "OBSOLETO"
        valido = False
    else:
        estado = "OK"
        valido = True
    return {
        "estado": estado,
        "estado_api": estado_api,
        "datos_validos": valido,
        "es_fallback": estado_api in ("FALLBACK", "CACHE"),
        "fecha_observacion": fecha_iso,
        "antiguedad_min": round(antiguedad_min, 1) if antiguedad_min is not None else None,
        "max_antiguedad_min": float(max_antiguedad_min),
        "mensaje": mensaje_api or (
            "API sin respuesta; se usa la última observación válida."
            if estado_api == "CACHE"
            else ("Datos meteorológicos vigentes." if valido else "")
        ),
    }


def _cargar_conductor_configurado():
    ruta = str(assets_dir() / "conductor_configurado.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def configuracion_dlr_linea(apoyos_utm, conductor=None):
    """Deriva la configuración DLR común para Python y Unity."""
    if not apoyos_utm:
        raise ValueError("No hay apoyos para derivar la configuración DLR.")
    huso = detectar_huso()
    coordenadas = [
        utm_a_latlon(float(a["x"]), float(a["y"]), huso)
        for a in apoyos_utm
    ]
    conductor = conductor or _cargar_conductor_configurado() or {}
    ts_limite = conductor.get("t_limite_C")
    if ts_limite is None:
        ruta_caso = str(assets_dir() / "caso_referencia_nivel1b.json")
        if os.path.exists(ruta_caso):
            with open(ruta_caso, encoding="utf-8") as f:
                caso = json.load(f)
            ts_limite = caso.get("entradas", {}).get("limite", {}).get("ts_C")
    if ts_limite is None:
        raise ValueError(
            "No se conoce la temperatura límite del conductor. "
            "Ejecuta principal.py para detectarla del Excel."
        )
    return {
        "huso_utm": huso,
        "lat_deg": sum(p[0] for p in coordenadas) / len(coordenadas),
        "lon_deg": sum(p[1] for p in coordenadas) / len(coordenadas),
        "he_m": sum(float(a["cota"]) for a in apoyos_utm) / len(apoyos_utm),
        "zl_deg": dlr.orientacion_primer_vano(apoyos_utm),
        "ts_limite_C": float(ts_limite),
    }

# Reutilizamos la conversión UTM->lat/lon ya validada del motor DLR
# (las pruebas de los Niveles 1A/1B/2 confirmaron que es correcta).
import dlr
utm_a_latlon = dlr.utm_a_latlon

# ------------------------------------------------------------------
# PREDICCIÓN POR MUNICIPIO (main2 de EnerFlux): geolocalización + API
# ------------------------------------------------------------------
import shapefile  # pyshp instalado para leer el shapefile de municipios

# ---------------------------------------------------------------------------
# Rutas de ENTRADA: se resuelven primero relativas al propio script (la raiz
# del TFG en el editor). El CWD al ejecutarse desde Unity es la CARPETA DE
# TRABAJO (AppData), que NO contiene "TFG Manuel"; por eso las rutas de entrada
# no pueden depender del CWD. Como respaldo se prueba relativa al CWD (build).

def _ruta_entrada(relativa):
    # Datos meteorologicos externos opcionales. No se versionan porque pueden
    # ser voluminosos o estar sujetos a condiciones de redistribucion.
    for base in (
        os.environ.get("TWINELEC_REFERENCE_DATA_DIR", ""),
        str(data_dir() / "reference"),
        str(REPOSITORY_ROOT / "data" / "reference"),
    ):
        if base:
            ruta = os.path.join(base, relativa)
            if os.path.exists(ruta):
                return ruta
    return relativa


RUTA_SHAPEFILE_MUNICIPIOS = _ruta_entrada(os.path.join(
    "municipalities",
    "recintos_municipales_inspire_peninbal_etrs89.shp",
))
_sf_municipios = None  # caché global del shapefile


def _punto_en_poligono(x, y, puntos):
    """Ray-casting: True si (x, y) está dentro del anillo de puntos."""
    dentro = False
    j = len(puntos) - 1
    for i in range(len(puntos)):
        xi, yi = puntos[i]
        xj, yj = puntos[j]
        interseccion = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-30) + xi
        )
        if interseccion:
            dentro = not dentro
        j = i
    return dentro


def _punto_en_multipoligono(x, y, partes):
    """True si el punto está en el multipolígono (todas las partes)."""
    for parte in partes:
        if _punto_en_poligono(x, y, parte):
            return True
    return False


def codigo_ine_municipio(lat, lon):
    """Devuelve el código INE de 5 dígitos del municipio que contiene el punto.

    Localiza el municipio en el shapefile INSPIRE de España mediante
    punto-en-polígono y extrae los últimos 5 dígitos del NATCODE
    (2 provincia + 3 municipio), que es el código que usa la API de AEMET.
    """
    global _sf_municipios
    if not os.path.exists(RUTA_SHAPEFILE_MUNICIPIOS):
        return None
    if _sf_municipios is None:
        _sf_municipios = shapefile.Reader(RUTA_SHAPEFILE_MUNICIPIOS)

    sf = _sf_municipios
    # El shapefile INSPIRE es 4thOrder (Municipio). Filtramos solo municipios.
    for idx in range(len(sf)):
        shape = sf.shape(idx)
        if shape.shapeType != 5:  # Polygon
            continue
        # Partes del polígono: shape.parts da índices de separación de rings.
        puntos = shape.points
        partes = []
        indices_parte = list(shape.parts) + [len(puntos)]
        for k in range(len(shape.parts)):
            ini = indices_parte[k]
            fin = indices_parte[k + 1]
            partes.append(puntos[ini:fin])
        if _punto_en_multipoligono(lon, lat, partes):
            rec = sf.record(idx)
            # IMPORTANTE: en pyshp el operador `in` sobre un registro NO comprueba
            # claves (recorre los valores), por lo que `if "X" in rec` siempre es
            # falso aunque la clave exista. Se accede via as_dict() (dict real).
            registro = rec.as_dict()
            natcode = str(registro.get("NATCODE") or "")
            if not natcode and len(rec) > 4:
                natcode = str(rec[4])
            nombre = str(registro.get("NAMEUNIT") or "").strip()
            # Últimos 5 dígitos del NATCODE = código municipal INE
            codigo_ine = natcode[-5:] if len(natcode) >= 5 else natcode
            return {"codigo_ine": codigo_ine, "nombre": nombre, "natcode": natcode}
    return None


def consultar_prediccion_horaria(codigo_municipio):
    """Consulta la predicción específica municipal horaria de AEMET."""
    clave = _exigir_credencial(
        API_KEY_PREDICCION,
        "TWINELEC_AEMET_PREDICCION_API_KEY o TWINELEC_AEMET_API_KEY",
    )
    url_request = (
        f"https://opendata.aemet.es/opendata/api/prediccion/especifica/"
        f"municipio/horaria/{codigo_municipio}"
    )
    r1 = _get_api_seguro(
        url_request,
        contexto="Predicción AEMET",
        params={"api_key": clave},
    )
    if r1.status_code != 200:
        print(f"  ⚠️ Predicción: respuesta {r1.status_code}")
        return None
    url_datos = r1.json().get("datos")
    if not url_datos:
        return None
    r2 = _get_api_seguro(url_datos, contexto="Descarga de predicción AEMET")
    if r2.status_code != 200:
        return None
    return r2.json()

# ============================================================================
# CONFIGURACIÓN DE FUENTES METEOROLÓGICAS
# ============================================================================
SIAR_BASE_URL = "https://servicio.mapama.gob.es/apisiar/API/v1"

RUTA_CATALOGO_ESTACIONES = _ruta_entrada(os.path.join(
    "stations.xlsx"
))
RUTA_SALIDA = str(assets_dir() / "meteorologia_actual.json")
# Caché de la última observación REAL válida (por estación). Se usa como
# respaldo si la API falla, en vez de inventar valores.
RUTA_CACHE_VALIDA = str(assets_dir() / "meteorologia_ultima_valida.json")


# ============================================================================
# UTILIDADES
# ============================================================================
def leer_apoyos_utm():
    """Lee el .doc/.docx de coordenadas UTM activo (como principal.py)."""
    archivos = glob.glob("*UTM*.doc*")
    if not archivos:
        raise FileNotFoundError("No se encontró ningún archivo *UTM*.doc*.")
    from docx import Document
    doc = Document(archivos[0])
    apoyos = []
    for i, fila in enumerate(doc.tables[0].rows):
        if i == 0:
            continue
        celdas = [c.text.replace(",", ".") for c in fila.cells]
        apoyos.append({
            "id": celdas[0],
            "x": float(celdas[1]),
            "y": float(celdas[2]),
            "cota": float(celdas[3]),
        })
    return apoyos


def detectar_huso():
    """Detecta el huso UTM de los ficheros PNOA."""
    for archivo in glob.glob("PNOA*HU*.tif"):
        import re
        m = re.search(r"HU(\d{2})", archivo)
        if m:
            return int(m.group(1))
    return 30


def estacion_mas_cercana(lat_linea, lon_linea):
    """Devuelve la estación (AEMET o SiAR) más cercana a las coordenadas."""
    df = pd.read_excel(RUTA_CATALOGO_ESTACIONES, header=0)
    # Nombres de columnas del catálogo de EnerFlux
    col_nombre = "NOMBRE,C,254"
    col_lat = "Latitud"
    col_lon = "Longitud"
    col_id = "INDICATIVO,C,254"
    col_alt = "ALTITUD,N,19,8"

    mejor = None
    mejor_dist = float("inf")
    for _, fila in df.iterrows():
        if col_nombre not in df.columns or col_lat not in df.columns or col_lon not in df.columns:
            break
        nombre = str(fila[col_nombre])
        try:
            lat = float(fila[col_lat])
            lon = float(fila[col_lon])
        except (KeyError, ValueError, TypeError):
            continue
        d = math.sqrt((lat - lat_linea) ** 2 + (lon - lon_linea) ** 2)
        if d < mejor_dist:
            mejor_dist = d
            mejor = {
                "nombre": nombre,
                "lat": lat,
                "lon": lon,
                "tipo": "AEMET" if str(nombre).startswith("AEMET_") else "SiAR",
                "id": str(fila[col_id]) if col_id in df.columns else "",
                "altitud": fila[col_alt] if col_alt in df.columns else 0.0,
            }
    return mejor, mejor_dist * 111.0  # km aprox


def consultar_aemet(id_estacion):
    """Consulta la API de AEMET (observación de la estación)."""
    clave = _exigir_credencial(API_KEY_AEMET, "TWINELEC_AEMET_API_KEY")
    url = (
        f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/"
        f"estacion/{id_estacion}"
    )
    r1 = _get_api_seguro(
        url,
        contexto="Observación AEMET",
        params={"api_key": clave},
    )
    if r1.status_code != 200:
        return None
    url_datos = r1.json().get("datos")
    if not url_datos:
        return None
    r2 = _get_api_seguro(url_datos, contexto="Descarga de observación AEMET")
    if r2.status_code != 200:
        return None
    datos = r2.json()
    if not datos:
        return None
    # Última medición disponible
    ultimo = datos[-1]
    fecha_hora = ultimo["fint"]
    # IMPORTANTE: AEMET publica fint en UTC (p. ej. "2026-08-14T11:00:00+0000").
    # Antes se usaba esa hora como si ya fuera local de Madrid, lo que inflaba
    # la antigüedad de la observación 2 h en verano (1 h en invierno) y podía
    # marcar datos frescos como OBSOLETOS (el límite operativo es 180 min).
    # Ahora se convierte a la zona horaria real (Europe/Madrid) antes de guardar.
    try:
        observacion_utc = datetime.fromisoformat(fecha_hora)
        observacion_local = observacion_utc.astimezone(ZoneInfo("Europe/Madrid"))
        fecha = observacion_local.strftime("%Y/%m/%d")
        hora = observacion_local.strftime("%H:%M")
    except (ValueError, TypeError):
        # Respaldo ante un formato inesperado: parseo antiguo (UTC a secas).
        fecha = fecha_hora.split("T")[0].replace("-", "/")
        hora = fecha_hora.split("T")[1].split("+")[0][:5]
    return {
        "ta_C": _temperatura_aire_aemet(ultimo),
        "vw_m_s": float(ultimo.get("vv", 0.0)),
        "direccion_viento_deg": float(ultimo.get("dv", 0.0)) if ultimo.get("dv") else None,
        "fecha": fecha,
        "hora_local": hora,
        "fecha_observacion": _fecha_observacion_iso(fecha, hora),
    }


def consultar_siar(id_estacion):
    """Consulta la API de SiAR (datos horarios de la estación)."""
    clave = _exigir_credencial(API_KEY_SIAR, "TWINELEC_SIAR_API_KEY")
    fecha_ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    fecha_actual = time.strftime("%Y-%m-%d")
    now = datetime.now()
    if now.time() <= datetime.strptime("01:40", "%H:%M").time():
        fecha_consulta = fecha_ayer
    else:
        fecha_consulta = fecha_actual
    url = f"{SIAR_BASE_URL}/Datos/Horarios/Estacion"
    r = _get_api_seguro(
        url,
        contexto="Observación SiAR",
        params={
            "Id": id_estacion,
            "FechaInicial": fecha_consulta,
            "FechaFinal": fecha_consulta,
            "ClaveAPI": clave,
        },
    )
    if r.status_code != 200:
        return None
    data = r.json()
    if not data.get("Datos"):
        return None
    ultimo = data["Datos"][-1]
    hora_min = int(ultimo["HoraMin"])
    hora = f"{hora_min // 100:02d}:{hora_min % 100:02d}"
    return {
        "ta_C": float(ultimo.get("TempMedia", 20.0)),
        "vw_m_s": float(ultimo.get("VelViento", 0.0)),
        "direccion_viento_deg": float(ultimo.get("DirViento", 0.0))
        if ultimo.get("DirViento") else None,
        "fecha": fecha_consulta.replace("-", "/"),
        "hora_local": hora,
        "fecha_observacion": _fecha_observacion_iso(
            fecha_consulta.replace("-", "/"), hora
        ),
    }


def _guardar_cache_ultima_valida(datos, estacion):
    """Persiste la última observación REAL válida por estación.

    Se usa como respaldo cuando la API falla, en vez de inventar valores.
    El archivo vive en Assets para que Unity pueda inspeccionarlo (TextAsset).
    """
    clave = str(estacion.get("id") or estacion.get("nombre") or "global")
    documento = {}
    if os.path.exists(RUTA_CACHE_VALIDA):
        try:
            with open(RUTA_CACHE_VALIDA, encoding="utf-8") as f:
                documento = json.load(f)
        except (OSError, ValueError, json.JSONDecodeError):
            documento = {}
    documento.setdefault(
        "guardadas_en", datetime.now().isoformat(timespec="seconds")
    )
    estaciones = documento.setdefault("estaciones", {})
    estaciones[clave] = {
        "guardada_en": datetime.now().isoformat(timespec="seconds"),
        "estacion": estacion["nombre"],
        "tipo_estacion": estacion["tipo"],
        "id_estacion": estacion["id"],
        "altitud_estacion_m": estacion["altitud"],
        "meteorologia": {
            "ta_C": datos.get("ta_C"),
            "vw_m_s": datos.get("vw_m_s", 0.0),
            "direccion_viento_deg": datos.get("direccion_viento_deg"),
            "fecha": datos.get("fecha"),
            "hora_local": datos.get("hora_local"),
            "fecha_observacion": datos.get("fecha_observacion"),
        },
    }
    _publicar_json_atomico(RUTA_CACHE_VALIDA, documento)


def _cargar_cache_ultima_valida(id_estacion=None):
    """Devuelve (datos, estacion) de la última observación REAL válida conocida.

    Si id_estacion se indica, busca la caché de esa estación concreta; si no la
    encuentra, usa la observación más reciente de todas (sigue siendo un dato
    real y cercano, mejor que inventar valores). (None, None) si no hay caché.
    """
    if not os.path.exists(RUTA_CACHE_VALIDA):
        return None, None
    try:
        with open(RUTA_CACHE_VALIDA, encoding="utf-8") as f:
            documento = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return None, None
    estaciones = documento.get("estaciones")
    if not isinstance(estaciones, dict) or not estaciones:
        return None, None

    entrada = None
    if id_estacion is not None:
        entrada = estaciones.get(str(id_estacion))
    if not isinstance(entrada, dict):
        entrada = max(
            estaciones.values(),
            key=lambda e: e.get("guardada_en", ""),
            default=None,
        )
    if not isinstance(entrada, dict):
        return None, None
    meteo = entrada.get("meteorologia")
    if not isinstance(meteo, dict) or meteo.get("ta_C") is None:
        return None, None

    datos = {
        "ta_C": float(meteo["ta_C"]),
        "vw_m_s": float(meteo.get("vw_m_s", 0.0)),
        "direccion_viento_deg": meteo.get("direccion_viento_deg"),
        "fecha": meteo.get("fecha") or datetime.now().strftime("%Y/%m/%d"),
        "hora_local": meteo.get("hora_local") or datetime.now().strftime("%H:%M"),
        "fecha_observacion": meteo.get("fecha_observacion"),
    }
    estacion = {
        "nombre": entrada.get("estacion") or "Última observación válida",
        "tipo": entrada.get("tipo_estacion") or "AEMET",
        "id": entrada.get("id_estacion") or "-",
        "altitud": float(entrada.get("altitud_estacion_m") or 0.0),
    }
    return datos, estacion


def guardar_meteorologia(
    datos,
    estacion,
    configuracion,
    *,
    estado_api="OK",
    mensaje_api="",
):
    """Guarda los datos en meteorologia_actual.json para Unity."""
    calidad = evaluar_calidad_meteorologica(
        datos, estado_api=estado_api, mensaje_api=mensaje_api
    )
    documento = {
        "version_esquema": 3,
        "fecha_generacion": datetime.now().isoformat(timespec="seconds"),
        "calidad": calidad,
        "fuente": estacion["nombre"],
        "tipo_estacion": estacion["tipo"],
        "id_estacion": estacion["id"],
        "altitud_estacion_m": estacion["altitud"],
        "distancia_aprox_km": None,
        "lat_linea_deg": configuracion["lat_deg"],
        "lon_linea_deg": configuracion["lon_deg"],
        "he_m": configuracion["he_m"],
        "zl_deg": configuracion["zl_deg"],
        "ts_limite_C": configuracion["ts_limite_C"],
        "hora_solar": hora_solar_aparente(
            datos["fecha"], datos["hora_local"], configuracion["lon_deg"]
        ),
        "meteorologia": datos,
    }
    _publicar_json_atomico(RUTA_SALIDA, documento)
    if calidad["datos_validos"]:
        _guardar_cache_ultima_valida(datos, estacion)
    print(f"✅ Meteorología guardada en {RUTA_SALIDA}")


# ============================================================================
# PREDICCIÓN DE CAPACIDAD FUTURA (main2 de EnerFlux)
# ============================================================================
def procesar_prediccion(datos_pred, geometria, conductor=None):
    """Procesa la respuesta de la predicción horaria de AEMET y calcula la
    corriente máxima admisible (I_max) para cada franja futura usando el motor
    DLR (dlr.py). Devuelve una lista de registros {fecha_hora, ta, vw, dir,
    i_max_A}.

    Parámetros
    ----------
    datos_pred : list
        Respuesta JSON de la API de predicción específica municipal horaria.
    geometria : dict
        {"lat_deg", "lon_deg", "he_m", "zl_deg"} de la línea.
    conductor : dict | None
        Si se proporciona, debe traer r_low_ohm_km, r_high_ohm_km, etc.
        Si es None, se intenta leer de conductor_configurado.json (Unity).
    """
    if not datos_pred or not datos_pred[0].get("prediccion"):
        return []

    # --- Cargar el conductor enriquecido (con resistencias eléctricas) ---
    if conductor is None:
        ruta_cond = str(assets_dir() / "conductor_configurado.json")
        if os.path.exists(ruta_cond):
            with open(ruta_cond, encoding="utf-8") as f:
                conductor = json.load(f)
    if conductor is None or not conductor.get("r_low_ohm_km"):
        print("  ⚠️ Sin resistencias eléctricas del conductor: no se puede predecir I_max.")
        return []
    ts_limite = conductor.get("t_limite_C")
    if ts_limite is None:
        ruta_caso = str(assets_dir() / "caso_referencia_nivel1b.json")
        if os.path.exists(ruta_caso):
            with open(ruta_caso, encoding="utf-8") as f:
                caso = json.load(f)
            ts_limite = caso.get("entradas", {}).get("limite", {}).get("ts_C")
    if ts_limite is None:
        raise ValueError(
            "No se conoce la temperatura límite del conductor para la predicción. "
            "Ejecuta principal.py para detectarla del Excel."
        )

    # Geometría de referencia para la posición solar y la línea
    lat = geometria["lat_deg"]
    he = geometria.get("he_m", 0.0)
    zl = geometria.get("zl_deg", 0.0)

    def _normalizar_hora(periodo):
        """Convierte el periodo de AEMET (int 0-23 o cadena "0-1") a hora int."""
        if isinstance(periodo, (int, float)):
            return int(periodo)
        if isinstance(periodo, str):
            # Formato típico horario de AEMET: "0-1", "8-9", ...
            primera = periodo.split("-")[0].split("/")[0].strip()
            try:
                return int(primera)
            except ValueError:
                return None
        return None

    def _valor_viento(campo):
        """AEMET devuelve velocidades/direcciones como listas (p.ej. [5]).
        Extrae el primer elemento o devuelve None."""
        if campo is None:
            return None
        if isinstance(campo, (list, tuple)):
            return campo[0] if len(campo) > 0 else None
        return campo

    def _direccion_a_grados(dir_v):
        """Convierte la dirección del viento (grados o rosa) a grados."""
        if dir_v is None:
            return None
        if isinstance(dir_v, (int, float)):
            return float(dir_v)
        rosa = {"N":0,"NE":45,"E":90,"SE":135,"S":180,"SO":225,"O":270,"NO":315,
                "NNE":22.5,"ENE":67.5,"ESE":112.5,"SSE":157.5,"SSO":202.5,
                "OSO":247.5,"NNO":292.5,"ONO":337.5}
        return rosa.get(str(dir_v).upper())

    franjas = []
    for dia in datos_pred[0]["prediccion"]["dia"]:
        fecha_str = dia.get("fecha", "")
        # AEMET horaria: fecha viene como '2025-08-05T00:00:00' o '2025-08-05'
        if "T" in fecha_str:
            fecha = fecha_str.split("T")[0]
        else:
            fecha = fecha_str

        temperaturas = dia.get("temperatura", [])
        vientos = dia.get("vientoAndRachaMax", [])

        # Construir mapa hora -> temp y hora -> (vel, dir). La predicción
        # municipal AEMET expresa la velocidad en km/h; el motor IEEE 738
        # trabaja exclusivamente en m/s.
        temp_por_hora = {}
        for t in temperaturas:
            hora = _normalizar_hora(t.get("periodo"))
            value = t.get("value")
            if hora is not None and value is not None:
                try:
                    temp_por_hora[hora] = float(value)
                except (ValueError, TypeError):
                    continue

        viento_por_hora = {}
        for v in vientos:
            hora = _normalizar_hora(v.get("periodo"))
            vel = _valor_viento(v.get("velocidad"))
            dir_v = _valor_viento(v.get("direccion"))
            dir_grados = _direccion_a_grados(dir_v)
            if hora is not None and vel is not None:
                try:
                    viento_por_hora[hora] = (_km_h_a_m_s(vel), dir_grados)
                except (ValueError, TypeError):
                    continue

        # Combinar por periodo
        periodos = sorted(set(temp_por_hora) | set(viento_por_hora))
        for periodo in periodos:
            if periodo not in temp_por_hora:
                continue
            ta = temp_por_hora[periodo]
            vel, dir_v = viento_por_hora.get(periodo, (0.0, None))
            hora_aprox = f"{periodo:02d}:00"
            franjas.append({
                "fecha": fecha,
                "hora": hora_aprox,
                "ta_C": ta,
                "vw_m_s": vel,
                "direccion_viento_deg": dir_v,
            })

    if not franjas:
        return []

    # --- Calcular I_max para cada franja con el motor DLR ---
    for f in franjas:
        fecha_iso = f["fecha"].replace("/", "-")
        hora_float = hora_solar_aparente(f["fecha"], f["hora"], geometria["lon_deg"])
        entradas = {
            "conductor": {
                "designacion": conductor.get("designacion", ""),
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
            "meteorologia": {
                "ta_C": f["ta_C"],
                "vw_m_s": f["vw_m_s"],
                "direccion_viento_deg": f["direccion_viento_deg"],
            },
            "geometria": {
                "he_m": he,
                "lat_deg": lat,
                "zl_deg": zl,
            },
            "fecha": fecha_iso,
            "hora_solar": hora_float,
            "limite": {"ts_C": float(ts_limite)},
        }
        try:
            res = dlr.calcular_dlr(entradas, modo="ieee738")
            f["i_max_A"] = round(res["resultado"]["i_max_A"], 2)
        except Exception as e:
            f["i_max_A"] = None
            f["error"] = str(e)

    return franjas


def guardar_prediccion_futura(franjas, municipio):
    """Guarda la previsión de capacidad futura en
    unity/Assets/prediccion_futura.json para Unity."""
    ruta = str(assets_dir() / "prediccion_futura.json")
    documento = {
        "fecha_generacion": datetime.now().isoformat(timespec="seconds"),
        "municipio": municipio,
        "franjas": franjas,
    }
    _publicar_json_atomico(ruta, documento)
    print(f"✅ Predicción futura guardada en {ruta} ({len(franjas)} franjas)")


# ============================================================================
# AGRUPACIÓN POR MUNICIPIOS (example2 de EnerFlux)
# ============================================================================
def agrupar_por_municipios(apoyos_utm):
    """Agrupa los apoyos de la línea por municipio (código INE) y devuelve
    una lista de grupos con sus apoyos, lat/lon media y altitud media.

    Estructura de retorno:
    [
        {
            "codigo_ine": "00000",
            "nombre": "Municipio de ejemplo",
            "natcode": "demo",
            "apoyos": [ {id, x, y, cota}, ... ],
            "lat_media": float,
            "lon_media": float,
            "he_m": float
        }, ...
    ]
    """
    grupos = {}
    for apoyo in apoyos_utm:
        lat, lon = utm_a_latlon(float(apoyo["x"]), float(apoyo["y"]), detectar_huso())
        municipio = codigo_ine_municipio(lat, lon)
        if municipio is None:
            clave = "DESCONOCIDO"
            codigo = "00000"
            nombre = "Desconocido"
        else:
            clave = municipio["codigo_ine"]
            codigo = municipio["codigo_ine"]
            nombre = municipio.get("nombre") or municipio.get("natcode")
        if clave not in grupos:
            grupos[clave] = {
                "codigo_ine": codigo,
                "nombre": nombre,
                "natcode": municipio.get("natcode") if municipio else None,
                "apoyos": [],
            }
        grupos[clave]["apoyos"].append(apoyo)

    resultado = []
    for clave, grupo in grupos.items():
        lats = [utm_a_latlon(float(a["x"]), float(a["y"]), detectar_huso())[0] for a in grupo["apoyos"]]
        lons = [utm_a_latlon(float(a["x"]), float(a["y"]), detectar_huso())[1] for a in grupo["apoyos"]]
        cotas = [float(a["cota"]) for a in grupo["apoyos"]]
        grupo["lat_media"] = sum(lats) / len(lats)
        grupo["lon_media"] = sum(lons) / len(lons)
        grupo["he_m"] = sum(cotas) / len(cotas)
        resultado.append(grupo)
    return resultado


def calcular_capacidad_municipios(apoyos_utm, configuracion=None):
    """Calcula la corriente admisible de la línea agrupada por municipios.

    Para cada grupo de apoyos del mismo municipio:
        1) localiza la estación meteorológica más cercana (AEMET/SiAR)
        2) consulta su meteorología actual
        3) calcula la I_max del grupo con el motor DLR
    La línea entera queda limitada por el VALOR MÍNIMO (más desfavorable).

    Devuelve (grupos_resultado, limite_linea_A, limite_linea_detalle).
    grupos_resultado: lista con {codigo_ine, nombre, estacion, ta, vw, dir,
                                 i_max_A}.
    """
    grupos = agrupar_por_municipios(apoyos_utm)
    grupos_resultado = []

    # Cargar conductor enriquecido una sola vez
    conductor = _cargar_conductor_configurado()
    configuracion = configuracion or configuracion_dlr_linea(apoyos_utm, conductor)

    for grupo in grupos:
        estacion, dist = estacion_mas_cercana(grupo["lat_media"], grupo["lon_media"])
        datos = None
        estado_api_grupo = "OK"
        mensaje_api_grupo = ""
        if estacion:
            if estacion["tipo"] == "AEMET":
                try:
                    datos = consultar_aemet(estacion["id"])
                except Exception as exc:
                    estado_api_grupo = "ERROR"
                    mensaje_api_grupo = str(exc)
                    datos = None
            else:
                try:
                    datos = consultar_siar(estacion["id"])
                except Exception as exc:
                    estado_api_grupo = "ERROR"
                    mensaje_api_grupo = str(exc)
                    datos = None
        # Fallback: si no hay estación o la API falla, usamos la última
        # observación REAL válida de esa estación; si no existe caché, manual.
        if datos is None:
            datos_cache, estacion_cache = _cargar_cache_ultima_valida(
                estacion["id"] if estacion else None
            )
            if datos_cache is not None:
                datos = datos_cache
                estacion = estacion_cache
                estado_api_grupo = "CACHE"
                if mensaje_api_grupo:
                    mensaje_api_grupo = (
                        f"{mensaje_api_grupo.rstrip('.')}. "
                        "Se usa la última observación válida."
                    )
                else:
                    mensaje_api_grupo = (
                        "Se usa la última observación válida (API sin respuesta)."
                    )
            else:
                datos = {
                    "ta_C": 20.0,
                    "vw_m_s": 2.0,
                    "direccion_viento_deg": 90.0,
                    "fecha": datetime.now().strftime("%Y/%m/%d"),
                    "hora_local": datetime.now().strftime("%H:%M"),
                }
                estacion = {"nombre": "manual", "tipo": "MANUAL", "id": "-", "altitud": 0.0}
                estado_api_grupo = "FALLBACK"
                mensaje_api_grupo = (
                    mensaje_api_grupo or "La API no devolvió una observación utilizable."
                )

        calidad_grupo = evaluar_calidad_meteorologica(
            datos,
            estado_api=estado_api_grupo,
            mensaje_api=mensaje_api_grupo,
        )
        if calidad_grupo["datos_validos"]:
            _guardar_cache_ultima_valida(datos, estacion)

        # Calcular I_max con el motor DLR
        i_max = None
        if conductor and conductor.get("r_low_ohm_km"):
            entradas = {
                "conductor": {
                    "designacion": conductor.get("designacion", ""),
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
                "meteorologia": {
                    "ta_C": float(datos.get("ta_C", 20.0)),
                    "vw_m_s": float(datos.get("vw_m_s", 0.0)),
                    "direccion_viento_deg": datos.get("direccion_viento_deg"),
                },
                "geometria": {
                    "he_m": grupo["he_m"],
                    "lat_deg": grupo["lat_media"],
                    "zl_deg": configuracion["zl_deg"],
                },
                "fecha": datos["fecha"].replace("/", "-"),
                "hora_solar": hora_solar_aparente(
                    datos["fecha"], datos["hora_local"], grupo["lon_media"]
                ),
                "limite": {"ts_C": configuracion["ts_limite_C"]},
            }
            try:
                res = dlr.calcular_dlr(entradas, modo="ieee738")
                i_max = round(res["resultado"]["i_max_A"], 2)
            except Exception as e:
                i_max = None

        grupos_resultado.append({
            "codigo_ine": grupo["codigo_ine"],
            "nombre": grupo["nombre"],
            "natcode": grupo["natcode"],
            "num_apoyos": len(grupo["apoyos"]),
            "lat_media": grupo["lat_media"],
            "lon_media": grupo["lon_media"],
            "he_m": grupo["he_m"],
            "estacion": estacion["nombre"],
            "tipo_estacion": estacion["tipo"],
            "id_estacion": estacion["id"],
            "distancia_estacion_km": round(dist, 2) if dist is not None else None,
            "meteorologia": {
                "ta_C": datos.get("ta_C"),
                "vw_m_s": datos.get("vw_m_s"),
                "direccion_viento_deg": datos.get("direccion_viento_deg"),
                "fecha": datos.get("fecha"),
                "hora_local": datos.get("hora_local"),
            },
            "calidad": calidad_grupo,
            "i_max_A": i_max,
        })

    # Límite de la línea: mínimo (más desfavorable) de las I_max disponibles.
    # Se incluyen tambien las de respaldo/manuales para que el panel muestre
    # siempre una referencia (el estado FALLBACK avisa de que no son reales).
    validos = [
        g["i_max_A"] for g in grupos_resultado
        if g["i_max_A"] is not None and g["calidad"]["datos_validos"]
    ]
    limite_linea_A = min(validos) if validos else None
    limite_detalle = {
        "municipio_critico": (
            next((g["codigo_ine"] for g in grupos_resultado
                  if g["i_max_A"] == limite_linea_A), None)
            if limite_linea_A is not None else None
        ),
        "num_municipios": len(grupos_resultado),
        "num_apoyos": len(apoyos_utm),
    }
    return grupos_resultado, limite_linea_A, limite_detalle


def guardar_capacidad_municipios(grupos, limite_A, limite_detalle):
    """Guarda la capacidad agrupada por municipios en
    unity/Assets/meteorologia_por_municipio.json para Unity."""
    ruta = str(assets_dir() / "meteorologia_por_municipio.json")
    documento = {
        "fecha_generacion": datetime.now().isoformat(timespec="seconds"),
        "limite_linea_A": limite_A,
        "limite_detalle": limite_detalle,
        "municipios": grupos,
    }
    _publicar_json_atomico(ruta, documento)
    print(f"✅ Capacidad por municipios guardada en {ruta}")


def main():
    """Obtiene la meteorología de la estación más cercana y la guarda."""
    print("=" * 70)
    print("DLR OPERATIVO — Obtención de meteorología real (AEMET/SiAR)")
    print("=" * 70)

    try:
        apoyos = leer_apoyos_utm()
        huso = detectar_huso()
        configuracion = configuracion_dlr_linea(apoyos)
        lat_media = configuracion["lat_deg"]
        lon_media = configuracion["lon_deg"]
        he_m = configuracion["he_m"]
        print(f"Línea: {len(apoyos)} apoyos, lat={lat_media:.4f}, lon={lon_media:.4f}, He={he_m:.0f} m")
        print(
            f"DLR: Zl={configuracion['zl_deg']:.2f}°, "
            f"Ts={configuracion['ts_limite_C']:.1f} °C"
        )
    except Exception as e:
        print(f"⚠️ No se pudo leer la geometría: {e}")
        return

    # 1) Localizar estación más cercana
    estacion, dist = estacion_mas_cercana(lat_media, lon_media)
    if estacion is None:
        print("⚠️ No se encontró ninguna estación en el catálogo.")
        return
    print(f"Estación más cercana: {estacion['nombre']} a ~{dist:.1f} km")

    # 2) Consultar API
    datos = None
    estado_api = "OK"
    mensaje_api = ""
    if estacion["tipo"] == "AEMET":
        try:
            datos = consultar_aemet(estacion["id"])
        except Exception as e:
            estado_api = "ERROR"
            mensaje_api = str(e)
            print(f"⚠️ Error API AEMET: {e}")
    else:
        try:
            datos = consultar_siar(estacion["id"])
        except Exception as e:
            estado_api = "ERROR"
            mensaje_api = str(e)
            print(f"⚠️ Error API SiAR: {e}")

    # 3) Si la API falla, usar la última observación REAL válida como respaldo;
    #    solo si no existe caché, valores por defecto (modo manual/documentado).
    if datos is None:
        datos_cache, estacion_cache = _cargar_cache_ultima_valida(estacion["id"])
        if datos_cache is not None:
            print("⚠️ La API no respondió. Se usará la última observación válida real.")
            datos = datos_cache
            estacion = estacion_cache
            estado_api = "CACHE"
            if mensaje_api:
                mensaje_api = (
                    f"{mensaje_api.rstrip('.')}. Se usa la última observación válida."
                )
            else:
                mensaje_api = "Se usa la última observación válida (API sin respuesta)."
        else:
            print("⚠️ La API no respondió y no hay caché válida. "
                  "Se usarán valores por defecto (modo manual).")
            datos = {
                "ta_C": 20.0,
                "vw_m_s": 2.0,
                "direccion_viento_deg": 90.0,
                "fecha": datetime.now().strftime("%Y/%m/%d"),
                "hora_local": datetime.now().strftime("%H:%M"),
                "fecha_observacion": datetime.now(
                    ZoneInfo("Europe/Madrid")
                ).isoformat(timespec="minutes"),
            }
            estado_api = "FALLBACK"
            mensaje_api = mensaje_api or "La API no devolvió una observación utilizable."
            estacion = {
                "nombre": "Valores manuales de respaldo",
                "tipo": "MANUAL",
                "id": "-",
                "altitud": 0.0,
            }

    # 4) Guardar
    guardar_meteorologia(
        datos,
        estacion,
        configuracion,
        estado_api=estado_api,
        mensaje_api=mensaje_api,
    )
    print(f"   Ta={datos['ta_C']:.1f} °C, Vw={datos['vw_m_s']:.1f} m/s, "
          f"dir={datos['direccion_viento_deg']}° — {datos['fecha']} {datos['hora_local']}")

    # ------------------------------------------------------------------
    # 5) CAPACIDAD POR MUNICIPIOS (example2 de EnerFlux)
    #    Agrupar apoyos por municipio -> estación más cercana de cada uno
    #    -> I_max por municipio -> límite de línea = mínimo (desfavorable).
    # ------------------------------------------------------------------
    print("\n--- Capacidad por municipios (example2) ---")
    try:
        grupos_mun, limite_A, limite_det = calcular_capacidad_municipios(
            apoyos, configuracion
        )
        guardar_capacidad_municipios(grupos_mun, limite_A, limite_det)
        print(f"  Municipios detectados: {limite_det['num_municipios']}")
        for g in grupos_mun:
            print(f"    - {g['nombre']} ({g['codigo_ine']}): "
                  f"{g['num_apoyos']} apoyos, estación {g['estacion']}, "
                  f"I_max = {g['i_max_A']} A")
        if limite_A is not None:
            print(f"  ⚠️ LÍMITE DE LÍNEA (mínimo): {limite_A:.2f} A "
                  f"(municipio crítico {limite_det['municipio_critico']})")
    except Exception as e:
        print(f"  ⚠️ Error en la capacidad por municipios: {e}")

    # ------------------------------------------------------------------
    # 6) INTENSIDAD MÁXIMA POR EL RLAT (reglamento, main1 8.1.3)
    #    Límite normativo: densidad de corriente de la tabla 5 del RLAT
    #    corregida por el factor de composición. Sirve de comparación
    #    con el valor dinámico IEEE 738.
    # ------------------------------------------------------------------
    print("\n--- Intensidad por Reglamento RLAT (main1 8.1.3) ---")
    try:
        ruta_cond = str(assets_dir() / "conductor_configurado.json")
        conductor_rlat = None
        if os.path.exists(ruta_cond):
            with open(ruta_cond, encoding="utf-8") as f:
                conductor_rlat = json.load(f)
        if conductor_rlat and conductor_rlat.get("seccion_mm2"):
            res_rlat = dlr.intensidad_reglamento(
                conductor_rlat["seccion_mm2"],
                conductor_rlat.get("nomenclatura_excel") or conductor_rlat.get("designacion", ""),
                conductor_rlat.get("composicion"),
            )
            if "error" not in res_rlat:
                ruta_rlat = str(assets_dir() / "intensidadreglamento.json")
                _publicar_json_atomico(
                    ruta_rlat,
                    {
                        "fecha_generacion": datetime.now().isoformat(timespec="seconds"),
                        "conductor": conductor_rlat.get("designacion", ""),
                        "resultado": res_rlat,
                    },
                )
                print(f"  ✅ Intensidad RLAT guardada en {ruta_rlat}")
                print(f"  Densidad tabla: {res_rlat['densidad_tabla_A_mm2']} A/mm², "
                      f"factor {res_rlat['factor_reduccion']}, "
                      f"I_reglamento = {res_rlat['intensidad_reglamento_A']:.2f} A")
                # Comparar con el límite dinámico por municipios si existe
                if limite_A is not None:
                    print(f"  ⚠️ Comparativa: DLR actual = {limite_A:.2f} A "
                          f"vs RLAT = {res_rlat['intensidad_reglamento_A']:.2f} A")
            else:
                print(f"  ⚠️ {res_rlat['error']}")
        else:
            print("  ⚠️ Sin conductor configurado para la comparativa RLAT.")
    except Exception as e:
        print(f"  ⚠️ Error en la comparativa RLAT: {e}")

    # ------------------------------------------------------------------
    # 7) PREDICCIÓN DE CAPACIDAD FUTURA (main2 de EnerFlux)
    #    Geolocalizar municipio -> código INE -> predicción horaria AEMET
    #    -> procesar franjas -> calcular I_max futura con el motor DLR.
    # ------------------------------------------------------------------
    print("\n--- Predicción de capacidad futura (main2) ---")
    try:
        # Geolocalizar el municipio (usa el punto medio de la línea)
        municipio = codigo_ine_municipio(lat_media, lon_media)
        if municipio is None:
            print("  ⚠️ No se pudo geolocalizar el municipio de la línea.")
        else:
            print(f"  Municipio: {municipio.get('nombre') or municipio.get('natcode')} "
                  f"(código INE {municipio['codigo_ine']})")
            datos_pred = consultar_prediccion_horaria(municipio["codigo_ine"])
            if datos_pred:
                franjas = procesar_prediccion(
                    datos_pred,
                    {"lat_deg": lat_media, "lon_deg": lon_media,
                     "he_m": he_m, "zl_deg": configuracion["zl_deg"]},
                    conductor=None,  # se carga solo desde conductor_configurado.json
                )
                guardar_prediccion_futura(franjas, municipio)
                if franjas:
                    minimo = min(f["i_max_A"] for f in franjas if f.get("i_max_A") is not None)
                    maximo = max(f["i_max_A"] for f in franjas if f.get("i_max_A") is not None)
                    print(f"  Capacidad futura: I_max entre {minimo:.1f} A y {maximo:.1f} A "
                          f"en {len(franjas)} franjas horarias.")
                else:
                    print("  ⚠️ No se pudieron procesar franjas de predicción.")
            else:
                print("  ⚠️ La API de predicción no respondió (posible límite 429 temporal).")
    except Exception as e:
        print(f"  ⚠️ Error en la predicción: {e}")


if __name__ == "__main__":
    # UTF-8 forzado en stdout (si Python hereda CP-1252, los prints con simbolos
    # ✅/❌/⚠️ lanzan UnicodeEncodeError y el script aborta).
    import sys
    import io
    try:
        if sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
    except Exception:
        pass
    # Soporte para bucle: py -3 clima.py --bucle 30
    if len(sys.argv) >= 3 and sys.argv[1] == "--bucle":
        intervalo_min = float(sys.argv[2])
        print(f"Modo bucle: se actualizará cada {intervalo_min:.0f} minutos.")
        while True:
            try:
                main()
            except Exception as e:
                print(f"⚠️ Error en el bucle: {e}")
            time.sleep(intervalo_min * 60.0)
    else:
        main()
