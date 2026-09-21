using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

/// <summary>
/// Frontera única entre los archivos generados por clima.py y Unity.
/// Lee, valida y publica meteorología; no calcula DLR ni dibuja interfaz.
/// </summary>
[DisallowMultipleComponent]
public class ServicioMeteorologiaDLR : MonoBehaviour
{
    [Serializable]
    public class InstantaneaMeteorologica
    {
        public int versionEsquema;
        public string fuente = "—";
        public string tipoEstacion = "—";
        public string idEstacion = "—";
        public float latLineaDeg;
        public float lonLineaDeg;
        public float altitudM;
        public float azimutLineaDeg;
        public float temperaturaLimiteC;
        public float horaSolar;
        public float temperaturaAmbienteC;
        public float velocidadVientoMs;
        public float direccionVientoDeg = -1f;
        public string fecha = "";
        public string horaLocal = "";
        public string estado = "SIN_DATOS";
        public string estadoApi = "—";
        public bool datosValidos;
        public bool esFallback;
        public string fechaObservacion = "";
        public float antiguedadMin = -1f;
        public float maxAntiguedadMin = 180f;
        public string mensaje = "";
    }

    [Serializable] private class DocumentoMeteorologia
    {
        public int version_esquema;
        public string fuente;
        public string tipo_estacion;
        public string id_estacion;
        public float lat_linea_deg;
        public float lon_linea_deg;
        public float he_m;
        public float zl_deg;
        public float ts_limite_C;
        public float hora_solar;
        public CalidadMeteorologia calidad;
        public DatosClima meteorologia;
    }

    [Serializable] private class CalidadMeteorologia
    {
        public string estado;
        public string estado_api;
        public bool datos_validos;
        public bool es_fallback;
        public string fecha_observacion;
        public float antiguedad_min;
        public float max_antiguedad_min;
        public string mensaje;
    }

    [Serializable] private class DatosClima
    {
        public float ta_C;
        public float vw_m_s;
        public float direccion_viento_deg;
        public string fecha;
        public string hora_local;
    }

    [Header("Adquisición meteorológica")]
    [Tooltip("Archivo producido por clima.py dentro de Assets.")]
    public string archivoMeteorologia = "meteorologia_actual.json";
    [Tooltip("Cache de la ultima observacion VALIDA (respaldo si falla la red).")]
    public string archivoCache = "meteorologia_ultima_valida.json";
    [Tooltip("Lee una primera instantánea al iniciar el programa.")]
    public bool leerAlIniciar = true;
    [Tooltip("Comprueba periódicamente si clima.py ha publicado nuevos datos.")]
    public bool actualizarPeriodicamente = true;
    [Min(1f)] public float intervaloActualizacionSeg = 60f;

    [Header("Última instantánea (solo lectura)")]
    [SerializeField] private InstantaneaMeteorologica datosActuales =
        new InstantaneaMeteorologica();

    public bool TieneLectura { get; private set; }
    public InstantaneaMeteorologica DatosActuales => datosActuales;
    public event Action<InstantaneaMeteorologica> Actualizada;

    private float temporizador;
    private string ultimoMensajeLog = "";

    void Awake()
    {
        if (leerAlIniciar) ActualizarAhora();
    }

    void Update()
    {
        if (!actualizarPeriodicamente) return;
        temporizador += Time.deltaTime;
        if (temporizador < Mathf.Max(1f, intervaloActualizacionSeg)) return;
        temporizador = 0f;
        ActualizarAhora();
    }

    [ContextMenu("Actualizar meteorología ahora")]
    public void ActualizarAhora()
    {
        string ruta = Path.Combine(RutasGemelo.RutaAssetsGemelo(), archivoMeteorologia);
        if (File.Exists(ruta))
        {
            LeerDesdeArchivo(ruta, false);
            return;
        }

        // Respaldo: si clima.py no ha publicado aun (o fallo la red), se usa la
        // ultima observacion VALIDA almacenada, sin sobrescribirla.
        string rutaCache = Path.Combine(RutasGemelo.RutaAssetsGemelo(), archivoCache);
        if (File.Exists(rutaCache) && LeerDesdeCache(rutaCache))
            return;

        // Fallback adicional: buscar tambien en la raiz de datos (algunos
        // despliegues colocan los JSON de clima.py junto al Excel de trabajo).
        string rutaRaiz = Path.Combine(RutasGemelo.RutaDatos(), archivoMeteorologia);
        if (!string.Equals(Path.GetFullPath(rutaRaiz), Path.GetFullPath(ruta),
                StringComparison.OrdinalIgnoreCase) && File.Exists(rutaRaiz))
        {
            LeerDesdeArchivo(rutaRaiz, false);
            return;
        }
        string rutaCacheRaiz = Path.Combine(RutasGemelo.RutaDatos(), archivoCache);
        if (!string.Equals(Path.GetFullPath(rutaCacheRaiz), Path.GetFullPath(rutaCache),
                StringComparison.OrdinalIgnoreCase)
            && File.Exists(rutaCacheRaiz) && LeerDesdeCache(rutaCacheRaiz))
            return;

        PublicarError("SIN_DATOS", "No existe " + archivoMeteorologia
            + " (buscado en " + RutasGemelo.RutaAssetsGemelo() + ").");
    }

    void LeerDesdeArchivo(string ruta, bool esCache)
    {
        try
        {
            DocumentoMeteorologia documento =
                JsonUtility.FromJson<DocumentoMeteorologia>(File.ReadAllText(ruta));
            if (documento == null || documento.meteorologia == null)
            {
                PublicarError("ERROR", "El JSON no contiene el bloque meteorologia.");
                return;
            }
            datosActuales = Convertir(documento);
            if (esCache) MarcarComoCache(datosActuales);
            TieneLectura = true;
            Actualizada?.Invoke(datosActuales);
        }
        catch (Exception ex)
        {
            PublicarError("ERROR", "No se pudo leer la meteorologia: " + ex.Message);
        }
    }

    bool LeerDesdeCache(string rutaCache)
    {
        try
        {
            string texto = File.ReadAllText(rutaCache, System.Text.Encoding.UTF8);
            var doc = Json.Deserialize(texto) as Dictionary<string, object>;
            if (doc == null || !doc.ContainsKey("estaciones")
                || !(doc["estaciones"] is Dictionary<string, object> estaciones))
                return false;
            foreach (var kv in estaciones)
            {
                if (!(kv.Value is Dictionary<string, object> entrada)) continue;
                datosActuales = ConvertirDesdeDict(entrada);
                if (datosActuales == null) continue;
                MarcarComoCache(datosActuales);
                TieneLectura = true;
                Actualizada?.Invoke(datosActuales);
                return true;
            }
        }
        catch (Exception)
        {
            // Si la cache no se puede leer, se reporta SIN_DATOS en el siguiente paso.
        }
        return false;
    }

    void MarcarComoCache(InstantaneaMeteorologica resultado)
    {
        resultado.estado = "CACHE";
        resultado.esFallback = true;
        resultado.datosValidos = true; // la cache solo guarda observaciones validas
        resultado.mensaje = "Sin conexion. Se muestra la ultima observacion disponible.";
    }

    static float _f(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] != null)
        {
            float v;
            if (float.TryParse(d[clave].ToString().Replace(',', '.'),
                System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out v)) return v;
        }
        return 0f;
    }

    static bool _b(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] != null)
        {
            string s = d[clave].ToString().Trim().ToLowerInvariant();
            return s == "true" || s == "1";
        }
        return false;
    }

    static string _s(Dictionary<string, object> d, string clave)
    {
        return d != null && d.ContainsKey(clave) && d[clave] != null
            ? d[clave].ToString() : "";
    }

    InstantaneaMeteorologica ConvertirDesdeDict(Dictionary<string, object> d)
    {
        if (d == null || !(d.ContainsKey("meteorologia")
            && d["meteorologia"] is Dictionary<string, object> m))
            return null;
        var calidad = d.ContainsKey("calidad")
            ? d["calidad"] as Dictionary<string, object> : null;

        InstantaneaMeteorologica r = new InstantaneaMeteorologica
        {
            versionEsquema = (int)_f(d, "version_esquema"),
            fuente = _s(d, "fuente"),
            tipoEstacion = _s(d, "tipo_estacion"),
            idEstacion = _s(d, "id_estacion"),
            latLineaDeg = _f(d, "lat_linea_deg"),
            lonLineaDeg = _f(d, "lon_linea_deg"),
            altitudM = _f(d, "he_m"),
            azimutLineaDeg = _f(d, "zl_deg"),
            temperaturaLimiteC = _f(d, "ts_limite_C"),
            horaSolar = _f(d, "hora_solar"),
            temperaturaAmbienteC = _f(m, "ta_C"),
            velocidadVientoMs = _f(m, "vw_m_s"),
            direccionVientoDeg = _f(m, "direccion_viento_deg"),
            fecha = _s(m, "fecha").Replace("/", "-"),
            horaLocal = _s(m, "hora_local"),
            estado = _s(calidad, "estado"),
            estadoApi = _s(calidad, "estado_api"),
            datosValidos = _b(calidad, "datos_validos"),
            esFallback = _b(calidad, "es_fallback"),
            fechaObservacion = _s(calidad, "fecha_observacion"),
            antiguedadMin = _f(calidad, "antiguedad_min"),
            maxAntiguedadMin = _f(calidad, "max_antiguedad_min"),
            mensaje = _s(calidad, "mensaje"),
        };
        return r;
    }

    private static InstantaneaMeteorologica Convertir(DocumentoMeteorologia d)
    {
        DatosClima m = d.meteorologia;
        InstantaneaMeteorologica resultado = new InstantaneaMeteorologica
        {
            versionEsquema = d.version_esquema,
            fuente = d.fuente ?? "—",
            tipoEstacion = d.tipo_estacion ?? "—",
            idEstacion = d.id_estacion ?? "—",
            latLineaDeg = d.lat_linea_deg,
            lonLineaDeg = d.lon_linea_deg,
            altitudM = d.he_m,
            azimutLineaDeg = d.zl_deg,
            temperaturaLimiteC = d.ts_limite_C,
            horaSolar = d.hora_solar,
            temperaturaAmbienteC = m.ta_C,
            velocidadVientoMs = m.vw_m_s,
            direccionVientoDeg = m.direccion_viento_deg,
            fecha = (m.fecha ?? "").Replace("/", "-"),
            horaLocal = m.hora_local ?? ""
        };

        if (d.version_esquema < 3 || d.calidad == null)
        {
            resultado.estado = "OBSOLETO";
            resultado.mensaje = "JSON antiguo sin control de calidad.";
            return resultado;
        }

        CalidadMeteorologia c = d.calidad;
        resultado.estado = c.estado ?? "ERROR";
        resultado.estadoApi = c.estado_api ?? "—";
        resultado.datosValidos = c.datos_validos;
        resultado.esFallback = c.es_fallback;
        resultado.fechaObservacion = c.fecha_observacion ?? "";
        resultado.antiguedadMin = c.antiguedad_min;
        resultado.maxAntiguedadMin = c.max_antiguedad_min;
        resultado.mensaje = c.mensaje ?? "";

        if (DateTimeOffset.TryParse(resultado.fechaObservacion, out DateTimeOffset observacion))
        {
            resultado.antiguedadMin = (float)Math.Max(
                0.0, (DateTimeOffset.Now - observacion).TotalMinutes);
            if (resultado.estado == "OK"
                && resultado.antiguedadMin > resultado.maxAntiguedadMin)
            {
                resultado.estado = "OBSOLETO";
                resultado.datosValidos = false;
                resultado.mensaje = "La observación superó la antigüedad máxima.";
            }
        }

        return resultado;
    }

    private void PublicarError(string estado, string mensaje)
    {
        datosActuales = new InstantaneaMeteorologica
        {
            estado = estado,
            estadoApi = "NO_DISPONIBLE",
            datosValidos = false,
            mensaje = mensaje
        };
        TieneLectura = true;
        Actualizada?.Invoke(datosActuales);
        // Solo se registra en consola la PRIMERA vez (o si el mensaje cambia):
        // mientras clima.py tarda en generar el archivo, este aviso se repetiria
        // cada 60 s sin aportar nada nuevo.
        if (mensaje != ultimoMensajeLog)
        {
            ultimoMensajeLog = mensaje;
            Debug.LogWarning("ServicioMeteorologiaDLR: " + mensaje);
        }
    }
}
