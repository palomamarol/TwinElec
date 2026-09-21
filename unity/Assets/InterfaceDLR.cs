using UnityEngine;
using System;
using System.Collections.Generic;

/// <summary>
/// InterfaceDLR — HUD (visión general) del gemelo digital.
/// ========================================================
/// Muestra en pantalla la información DLR generada por clima.py:
///   1. corriente admisible actual (IEEE 738) — del motor C# + meteorología real
///   2. meteorología real de la estación (Ta, viento, dirección, fuente)
///   3. capacidad por municipios (o estación) y límite de línea (mínimo)
///   4. intensidad por Reglamento RLAT (límite estático)
///   5. previsión de capacidad futura (72 h) — próximas horas
///   6. alerta si la corriente DLR está por debajo del RLAT (aviso operativo)
///
/// GENERAL: lee los JSON que genera clima.py para CUALQUIER línea. No hay
/// ningún valor fijo de una ubicación. Se conecta al escenario mediante
/// la referencia opcional 'generador' para leer la corriente calculada en
/// tiempo real por el MotorDLR C#.
///
/// USO: añadir como componente a un GameObject vacío (o al GeneradorDeLinea).
/// </summary>
public class InterfaceDLR : MonoBehaviour
{
    [Header("Referencias (opcional)")]
    [Tooltip("Opcional: GeneradorDeLinea que calcula el I_max por IEEE 738 en C#.")]
    public GeneradorDeLinea generador;
    [Tooltip("Servicio único que adquiere y valida la meteorología.")]
    public ServicioMeteorologiaDLR servicioMeteorologia;
    [Tooltip("Servicio que carga los resultados auxiliares producidos por Python.")]
    public ServicioResultadosDLR servicioResultados;

    [Header("Modo de visualización")]
    [Tooltip("Mostrar u ocultar el HUD en pantalla.")]
    public bool mostrarHUD = true;
    [Tooltip("Fondo semitransparente del panel (más legible).")]
    public bool fondoOscuro = true;
    [Tooltip("Escala del texto del HUD.")]
    public float escalaTexto = 1f;

    // --- Datos leídos de los JSON (clima.py) ---
    [Header("Datos actuales (lectura)")]
    public string fuente = "—";
    public string tipoEstacion = "—";
    public string fechaHora = "—";
    public float taC = 0f;
    public float vwMs = 0f;
    public float dirViento = 0f;
    public float latLinea = 0f;
    public float lonLinea = 0f;
    public float heM = 0f;
    public string estadoMeteorologia = "SIN_DATOS";
    public string estadoApi = "—";
    public bool datosMeteorologicosValidos = false;
    public float antiguedadMin = -1f;
    public float maxAntiguedadMin = 180f;
    public string mensajeMeteorologia = "";

    [Header("Datos por municipios / RLAT")]
    public int numMunicipios = 0;
    public string municipioCritico = "—";
    public float limiteLineaA = -1f;
    public float iRlatA = -1f;
    [TextArea(3, 10)]
    public string listaMunicipios = "";

    [Header("Previsión futura")]
    [TextArea(5, 20)]
    public string prevision = "";

    void Awake()
    {
        // La referencia queda serializada en la escena. Este respaldo evita que
        // el HUD pierda el motor si alguien vacia el campo en el Inspector.
        if (generador == null)
            generador = GetComponent<GeneradorDeLinea>();
        if (servicioMeteorologia == null)
            servicioMeteorologia = GetComponent<ServicioMeteorologiaDLR>();
        if (servicioMeteorologia == null && generador != null)
            servicioMeteorologia = generador.servicioMeteorologia;
        if (servicioMeteorologia != null)
            servicioMeteorologia.Actualizada += SincronizarMeteorologia;
        if (servicioResultados == null)
            servicioResultados = GetComponent<ServicioResultadosDLR>();
        if (servicioResultados != null)
            servicioResultados.Actualizada += SincronizarResultados;
    }

    void OnDestroy()
    {
        if (servicioMeteorologia != null)
            servicioMeteorologia.Actualizada -= SincronizarMeteorologia;
        if (servicioResultados != null)
            servicioResultados.Actualizada -= SincronizarResultados;
    }

    void Start()
    {
        SincronizarMeteorologia(
            servicioMeteorologia != null ? servicioMeteorologia.DatosActuales : null);
        SincronizarResultados(
            servicioResultados != null ? servicioResultados.DatosActuales : null);
    }

    void SincronizarMeteorologia(ServicioMeteorologiaDLR.InstantaneaMeteorologica m)
    {
        if (m == null) return;
        fuente = m.fuente;
        tipoEstacion = m.tipoEstacion;
        taC = m.temperaturaAmbienteC;
        vwMs = m.velocidadVientoMs;
        dirViento = m.direccionVientoDeg;
        fechaHora = (string.IsNullOrEmpty(m.fecha) ? "—" : m.fecha)
            + " " + (string.IsNullOrEmpty(m.horaLocal) ? "—" : m.horaLocal);
        latLinea = m.latLineaDeg;
        lonLinea = m.lonLineaDeg;
        heM = m.altitudM;
        estadoMeteorologia = m.estado;
        estadoApi = m.estadoApi;
        datosMeteorologicosValidos = m.datosValidos;
        antiguedadMin = m.antiguedadMin;
        maxAntiguedadMin = m.maxAntiguedadMin;
        mensajeMeteorologia = m.mensaje;
    }

    void SincronizarResultados(ServicioResultadosDLR.InstantaneaResultados datos)
    {
        if (datos == null) return;
        numMunicipios = datos.numMunicipios;
        municipioCritico = datos.municipioCritico;
        limiteLineaA = datos.limiteLineaA;
        iRlatA = datos.iRlatA;
        listaMunicipios = datos.listaMunicipios;
        prevision = datos.prevision;
    }

    // ========================================================================
    // HUD EN PANTALLA (OnGUI) — visión general DLR
    // ========================================================================
    void OnGUI()
    {
        if (!mostrarHUD) return;

        float iActual = (generador != null) ? generador.dlrCorrienteMaximaA : limiteLineaA;

        float ancho = 360f * escalaTexto;
        float alto = 470f * escalaTexto;
        float x = 12f;
        float y = 12f;

        // Panel
        if (fondoOscuro)
        {
            GUI.color = new Color(0.05f, 0.05f, 0.1f, 0.78f);
            GUI.DrawTexture(new Rect(x, y, ancho, alto), Texture2D.whiteTexture, ScaleMode.StretchToFill);
            GUI.color = Color.white;
        }

        GUIStyle titulo = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(16 * escalaTexto), fontStyle = FontStyle.Bold };
        GUIStyle normal = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(13 * escalaTexto) };
        GUIStyle alerta = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(14 * escalaTexto), fontStyle = FontStyle.Bold };
        alerta.normal.textColor = new Color(1f, 0.7f, 0.2f);

        float lx = x + 14f * escalaTexto;
        float ly = y + 10f * escalaTexto;
        float paso = 22f * escalaTexto;

        GUI.Label(new Rect(lx, ly, ancho - 28f, 24f * escalaTexto), "⚡ DLR — GEMELO DIGITAL", titulo);
        ly += paso * 1.4f;

        // Corriente actual. Un dato meteorológico bloqueado significa que no
        // hay resultado operativo, no que la capacidad física sea cero amperios.
        string corrienteTexto = datosMeteorologicosValidos
            ? $"I máxima admisible (IEEE 738): {iActual,7:F1} A"
            : "I máxima admisible (IEEE 738): no disponible";
        GUI.Label(new Rect(lx, ly, ancho - 28f, paso), corrienteTexto,
            datosMeteorologicosValidos ? normal : alerta);
        ly += paso;
        // Estado crítico
        if (!datosMeteorologicosValidos)
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso),
                $"Estado: cálculo bloqueado ({estadoMeteorologia})", alerta);
        else if (iRlatA > 0f && iActual > 0f && iActual < iRlatA)
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"⚠ Estado: límite DLR < RLAT ({iActual:0} < {iRlatA:0} A)", alerta);
        else if (iRlatA > 0f && iActual > 0f)
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"Estado: margen disponible (DLR ≥ RLAT)", normal);
        else
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso), "Estado: calculando...", normal);
        ly += paso;

        // Separador
        GUI.Label(new Rect(lx, ly, ancho - 28f, paso), "— Meteorología actual —", titulo);
        ly += paso;
        GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"Temp: {taC:F1} °C   Viento: {vwMs:F1} m/s @ {dirViento:F0}°", normal);
        ly += paso;
        GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"Estación: {fuente}  ({tipoEstacion})", normal);
        ly += paso;
        GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"Fecha/Hora: {fechaHora}", normal);
        ly += paso;
        GUIStyle estadoClimaStyle = datosMeteorologicosValidos ? normal : alerta;
        string edadTexto = antiguedadMin >= 0f ? $" ({antiguedadMin:0} min)" : "";
        GUI.Label(new Rect(lx, ly, ancho - 28f, paso),
            $"Datos: {estadoMeteorologia} / API: {estadoApi}{edadTexto}", estadoClimaStyle);
        ly += paso;
        if (!datosMeteorologicosValidos && !string.IsNullOrEmpty(mensajeMeteorologia))
        {
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso * 2f), mensajeMeteorologia, alerta);
            ly += paso * 2f;
        }

        // RLAT
        if (iRlatA > 0f)
        {
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"Límite Reglamento (RLAT): {iRlatA:F1} A", normal);
            ly += paso;
        }

        // Municipalidad
        if (numMunicipios > 0)
        {
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"Municipios en la línea: {numMunicipios}", normal);
            ly += paso;
            if (municipioCritico != "—" && municipioCritico != "00000")
            {
                GUI.Label(new Rect(lx, ly, ancho - 28f, paso), $"Municipio crítico: {municipioCritico}", normal);
                ly += paso;
            }
            if (!string.IsNullOrEmpty(listaMunicipios))
            {
                GUI.Label(new Rect(lx, ly, ancho - 28f, 120f * escalaTexto), listaMunicipios, normal);
                ly += 130f * escalaTexto;
            }
        }

        // Previsión futura
        if (!string.IsNullOrEmpty(prevision))
        {
            GUI.Label(new Rect(lx, ly, ancho - 28f, paso), "— Previsión capacidad futura (72h) —", titulo);
            ly += paso;
            GUI.Label(new Rect(lx, ly, ancho - 28f, 180f * escalaTexto), prevision, normal);
        }
    }
}

// ============================================================================
// Mini-deserializador JSON genérico (para los JSON de clima.py)
// No depende de Newtonsoft; suficiente para nuestros archivos.
// ============================================================================
public static class Json
{
    public static object Deserialize(string json)
    {
        var pos = new Node(json, 0);
        var (obj, _) = pos.ParseValue();
        return obj;
    }

    /// <summary>Escapa un texto para usarlo dentro de un string JSON.</summary>
    public static string Esc(string valor)
    {
        if (valor == null) return "";
        var sb = new System.Text.StringBuilder();
        foreach (char c in valor)
        {
            switch (c)
            {
                case '\\': sb.Append("\\\\"); break;
                case '"': sb.Append("\\\""); break;
                case '\n': sb.Append("\\n"); break;
                case '\r': sb.Append("\\r"); break;
                case '\t': sb.Append("\\t"); break;
                default: sb.Append(c); break;
            }
        }
        return sb.ToString();
    }

    /// <summary>UTF-8 SIN marca de orden de bytes (BOM). Los archivos de peticion
    /// que lee Python deben escribirse con esta codificacion: json.load falla con
    /// 'Unexpected UTF-8 BOM' si el archivo empieza por la marca (Encoding.UTF8
    /// de .NET SI escribe la marca al grabar con WriteAllText).</summary>
    public static readonly System.Text.Encoding Utf8SinBom =
        new System.Text.UTF8Encoding(false);

    class Node
    {
        string s; int i;
        public Node(string str, int start) { s = str; i = start; }
        void SkipWs() { while (i < s.Length && (s[i] == ' ' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t')) i++; }
        public (object, int) ParseValue()
        {
            SkipWs();
            if (i >= s.Length) return (null, i);
            char c = s[i];
            if (c == '{') return ParseObj();
            if (c == '[') return ParseArr();
            if (c == '"') return (ParseStr(), i);
            // número o bool/null
            int ini = i;
            if (s[i] == '-') i++;
            while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '.' || s[i] == 'e' || s[i] == 'E' || s[i] == '+' || s[i] == '-')) i++;
            if (i > ini)
            {
                // Si el token empieza por dígito -> número
                if (char.IsDigit(s[ini]) || s[ini] == '-')
                {
                    string num = s.Substring(ini, i - ini);
                    return (double.TryParse(num, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out double d) ? d : (object)num, i);
                }
                return (s.Substring(ini, i - ini), i);
            }
            // literales. IMPORTANTE: hay que adelantar 'i' aqui, porque los
            // llamadores (ParseObj/ParseArr) descartan la posicion devuelta en
            // la tupla y confian en este campo: si no avanzara, tras 'false' el
            // siguiente ParseStr se tragaria 'false, ...' como clave y el JSON
            // se desincronizaria (error "clave 'etiqueta' no presente").
            string resto = s.Substring(i);
            if (resto.StartsWith("true")) { i += 4; return (true, i); }
            if (resto.StartsWith("false")) { i += 5; return (false, i); }
            if (resto.StartsWith("null")) { i += 4; return (null, i); }
            return (null, i);
        }
        (object, int) ParseObj()
        {
            var d = new Dictionary<string, object>();
            i++; // '{'
            SkipWs();
            if (i < s.Length && s[i] == '}') return (d, i + 1);
            while (i < s.Length)
            {
                SkipWs();
                string key = ParseStr();
                SkipWs();
                if (i < s.Length && s[i] == ':') i++;
                SkipWs();
                var (val, _) = ParseValue();
                d[key] = val;
                SkipWs();
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == '}') { i++; break; }
            }
            return (d, i);
        }
        (object, int) ParseArr()
        {
            var list = new List<object>();
            i++; // '['
            SkipWs();
            if (i < s.Length && s[i] == ']') return (list, i + 1);
            while (i < s.Length)
            {
                SkipWs();
                var (val, _) = ParseValue();
                list.Add(val);
                SkipWs();
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == ']') { i++; break; }
            }
            return (list, i);
        }
        string ParseStr()
        {
            if (i < s.Length && s[i] == '"') i++;
            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            while (i < s.Length)
            {
                char c = s[i];
                if (c == '\\') { i++; if (i < s.Length) { sb.Append(s[i]); i++; } continue; }
                if (c == '"') { i++; break; }
                sb.Append(c); i++;
            }
            return sb.ToString();
        }
    }
}
