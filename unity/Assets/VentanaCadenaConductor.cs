using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

/// <summary>
/// VentanaCadenaConductor — Cambia la CADENA DE AISLADORES y el CONDUCTOR de la
/// linea del gemelo digital.
/// ============================================================================
/// Al pulsar "APLICAR":
///   1. Escribe una peticion JSON en la raiz del proyecto.
///   2. Llama a Python:  py cambiar_cadena_conductor.py --peticion ... --resultado ...
///   3. Lee el resultado: si OK, el Excel de trabajo queda actualizado
///      (V/T/L de las hipotesis, desviacion de cadena, flecha maxima y conteos
///      de Mediciones) y se regenera la escena 3D con la nueva cadena (la
///      longitud se refleja en el modelo, no solo en los calculos).
///   El CONDUCTOR es comun a toda la linea; la CADENA puede aplicarse a toda
///   la linea o solo a un apoyo.
///
/// GENERAL: funciona para cualquier linea/excel de la plantilla.
/// </summary>
public class VentanaCadenaConductor : MonoBehaviour
{
    private string rutaPython = "";
    private string rutaExcel = "";
    private string rutaSalidaExcel = "";
    private string rutaApoyosConfig = "";
    private string rutaConductorConfig = "";
    private string rutaUtm = "";

    private Canvas canvas;
    private GameObject ventana;
    private Text titulo;
    private Text detalleCadena;
    private Text mensaje;
    private Dropdown cadenaDropdown;   // desplegable de cadenas (nombre Andelec)
    private Dropdown apoyoDropdown;    // desplegable de apoyos (1, 2, 3...)
    private Dropdown conductorDropdown; // desplegable de conductores (nomenclatura)
    private int seleccionCadena = 0;
    private int seleccionado = 1;
    private int totalApoyos = 1;
    private string ambito = "todos";
    private bool sincronizandoDropdown = false;

    // Catalogo de cadenas (lo trae Python): {nombre, denominacion, tipo,
    // material, doble, longitud_m, peso_daN, carga_rotura_daN, compatible}
    private List<Dictionary<string, object>> catalogo =
        new List<Dictionary<string, object>>();
    private Dictionary<string, object> cadenaActual = null;
    // Catalogo de conductores (lo trae Python): {nomenclatura, designacion, ...}
    private List<Dictionary<string, object>> catalogoConductores =
        new List<Dictionary<string, object>>();

    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaCadenaConductor>() == null)
        {
            var go = new GameObject("VentanaCadenaConductor");
            go.AddComponent<VentanaCadenaConductor>();
        }
    }

    void Awake()
    {
        try
        {
            rutaPython = RutasGemelo.RutaDatos(); // raiz del TFG (editor) o Datos/ (build)
            string nombreExcel = BuscarExcelTrabajo();
            rutaExcel = Path.Combine(rutaPython, nombreExcel + ".xlsx");
            rutaSalidaExcel = Path.Combine(rutaPython, nombreExcel + "_editada.xlsx");
            // Preferir el Excel de trabajo si ya existe (acumula cambios)
            if (File.Exists(rutaSalidaExcel)) rutaExcel = rutaSalidaExcel;
            rutaApoyosConfig = Path.Combine(RutasGemelo.RutaAssetsGemelo(),
                                            "apoyos_configurados.json");
            rutaConductorConfig = Path.Combine(RutasGemelo.RutaAssetsGemelo(),
                                               "conductor_configurado.json");
            rutaUtm = BuscarRutaUtm(rutaPython, nombreExcel);

            // Primero el total de apoyos y despues la ventana: el desplegable
            // de "SOLO APOYO Nº" debe mostrar TODOS los apoyos de la linea.
            CargarApoyosConfig();
            CrearCanvasYEventSystem();
            CrearVentana();
            // Catalogo desde Python sin bloquear el arranque
            Invoke("CargarCatalogo", 0.5f);
            DontDestroyOnLoad(gameObject);
            UnityEngine.Debug.Log("[VentanaCadenaConductor] ventana creada");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaCadenaConductor: " + ex.Message);
        }
    }

    string BuscarExcelTrabajo()
    {
        string[] exceles = Directory.GetFiles(rutaPython, "*.xlsx");
        foreach (string e in exceles)
        {
            string nombre = Path.GetFileNameWithoutExtension(e);
            if (!nombre.EndsWith("_editada")) return nombre;
        }
        return "line_example";
    }

    // -----------------------------------------------------------------------
    // Catalogo de cadenas (Python) y datos del apoyo
    // -----------------------------------------------------------------------
    string ConductorLinea()
    {
        try
        {
            if (File.Exists(rutaConductorConfig))
            {
                var doc = Json.Deserialize(
                    File.ReadAllText(rutaConductorConfig, System.Text.Encoding.UTF8))
                    as Dictionary<string, object>;
                if (doc != null && doc.ContainsKey("nomenclatura_excel")
                    && doc["nomenclatura_excel"] != null)
                    return doc["nomenclatura_excel"].ToString();
            }
        }
        catch (Exception) { }
        return "";
    }

    /// <summary>Localiza el JSON UTM de la linea (mismo criterio que la ventana
    /// "Mover apoyo y altura"): primero en la carpeta de trabajo, despues en la
    /// base (raiz del TFG en editor, Datos/ en build). Prefiere
    /// 'utm_editado.json' porque acumula los cambios ya aplicados.</summary>
    string BuscarRutaUtm(string carpeta, string nombreExcel)
    {
        string[] nombres = new[]
        {
            "utm_editado.json",
            "utm_" + nombreExcel + "_extraido.json",
        };
        foreach (string c in new[] { carpeta, RutasGemelo.RutaDatosBase() })
        {
            foreach (string nombre in nombres)
            {
                string ruta = Path.Combine(c, nombre);
                if (File.Exists(ruta)) return ruta;
            }
            string[] glob = Directory.GetFiles(c, "utm_*.json");
            if (glob.Length > 0) return glob[0];
        }
        return "";
    }

    void CargarApoyosConfig()
    {
        try
        {
            // Total de apoyos: se cuenta desde el JSON UTM (TODOS los apoyos
            // de la linea, igual que "Mover apoyo y altura"). Si no hay UTM,
            // se cae a apoyos_configurados.json.
            if (!string.IsNullOrEmpty(rutaUtm) && File.Exists(rutaUtm))
            {
                var doc = Json.Deserialize(
                    File.ReadAllText(rutaUtm, System.Text.Encoding.UTF8));
                List<object> lista = null;
                if (doc is List<object> listaPlana) lista = listaPlana;
                else if (doc is Dictionary<string, object> d2
                    && d2.ContainsKey("apoyos")
                    && d2["apoyos"] is List<object> l2) lista = l2;
                if (lista != null && lista.Count > 0)
                {
                    totalApoyos = Mathf.Max(1, lista.Count);
                    return;
                }
            }
            if (File.Exists(rutaApoyosConfig))
            {
                var doc = Json.Deserialize(
                    File.ReadAllText(rutaApoyosConfig, System.Text.Encoding.UTF8))
                    as Dictionary<string, object>;
                if (doc != null && doc.ContainsKey("apoyos")
                    && doc["apoyos"] is List<object> l)
                    totalApoyos = Mathf.Max(1, l.Count);
            }
        }
        catch (Exception) { }
    }

    void CargarCatalogo()
    {
        try
        {
            string conductor = ConductorLinea();
            string argumentos = "cambiar_cadena_conductor.py --catalogo_cadenas";
            if (!string.IsNullOrEmpty(conductor))
                argumentos += " --conductor \"" + conductor + "\"";
            // El catalogo es de solo lectura: se cachea para que la segunda
            // vez que se abra la ventana sea instantanea.
            string salida = CacheCatalogos.Obtener(
                "catalogo_cadenas_" + conductor, () => EjecutarPython(argumentos));
            var doc = Json.Deserialize(salida) as Dictionary<string, object>;
            if (doc != null && doc.ContainsKey("cadenas") && doc["cadenas"] is List<object> lista)
            {
                // Solo las compatibles con el conductor de la linea (marcadas por
                // Python); si no hay ninguna, se muestran todas.
                foreach (var item in lista)
                {
                    if (item is Dictionary<string, object> d
                        && EsCompatible(d))
                        catalogo.Add(d);
                }
                if (catalogo.Count == 0)
                {
                    foreach (var item in lista)
                        if (item is Dictionary<string, object> d) catalogo.Add(d);
                }
            }
            if (catalogo.Count == 0)
            {
                mensaje.text = "No se pudo cargar el catalogo de cadenas.\n"
                    + "Revisa que 'py' este en el PATH y que exista el catalogo.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
            }
            RellenarCatalogoCadenas();
            MostrarCadena();
            CargarCatalogoConductores();
        }
        catch (Exception ex)
        {
            mensaje.text = "AVISO / PARON:\n" + ex.Message;
            mensaje.color = new Color(1f, 0.5f, 0.4f);
        }
    }

    string EjecutarPython(string argumentos)
    {
        return MotorHelper.EjecutarMotor("cambiar_cadena_conductor", argumentos);
    }

    string CadenaCampo(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] != null)
            return d[clave].ToString().Replace(',', '.');
        return "";
    }

    bool EsCompatible(Dictionary<string, object> d)
    {
        object v = null;
        if (d != null && d.TryGetValue("compatible", out v) && v != null)
        {
            string s = v.ToString().Trim();
            return s.Equals("true", StringComparison.OrdinalIgnoreCase) || s == "True";
        }
        return false;
    }

    float NumeroCampo(InputField campo)
    {
        string texto = campo.text.Replace(',', '.');
        float v;
        if (float.TryParse(texto, System.Globalization.NumberStyles.Float,
                           System.Globalization.CultureInfo.InvariantCulture, out v))
            return v;
        throw new FormatException("Introduce un numero valido.");
    }

    void MostrarCadena()
    {
        if (catalogo.Count == 0) return;
        seleccionCadena = Mathf.Clamp(seleccionCadena, 0, catalogo.Count - 1);
        cadenaActual = catalogo[seleccionCadena];
        // Sincroniza los desplegables sin disparar sus listeners
        sincronizandoDropdown = true;
        if (cadenaDropdown != null && cadenaDropdown.options.Count > 0)
            cadenaDropdown.value = seleccionCadena;
        if (apoyoDropdown != null && apoyoDropdown.options.Count > 0)
            apoyoDropdown.value = Mathf.Clamp(seleccionado - 1, 0, totalApoyos - 1);
        sincronizandoDropdown = false;
        string nombre = CadenaCampo(cadenaActual, "nombre");
        string tipo = CadenaCampo(cadenaActual, "tipo");
        string material = CadenaCampo(cadenaActual, "material");
        string longitud = CadenaCampo(cadenaActual, "longitud_m");
        string peso = CadenaCampo(cadenaActual, "peso_daN");
        string denominacion = CadenaCampo(cadenaActual, "denominacion");
        string conductorNom = ConductorSeleccionado();
        detalleCadena.text =
            "Cadena " + (seleccionCadena + 1) + " de " + catalogo.Count + "\n"
            + nombre + "\n"
            + "Tipo: " + tipo + (material == "POL" ? " (polimerica)" : " (vidrio)")
            + "   |   Longitud: " + Formatear(longitud, "F3") + " m"
            + "   |   Peso: " + Formatear(peso, "F2") + " daN\n"
            + denominacion
            + "\n\nConductor: " + conductorNom;
        titulo.text = "CADENA Y CONDUCTOR  (ambito: "
            + (ambito == "todos" ? "toda la linea" : "apoyo " + seleccionado) + ")";
        mensaje.text = "";
    }

    string Formatear(string valor, string formato)
    {
        float f;
        if (float.TryParse(valor, System.Globalization.NumberStyles.Float,
                           System.Globalization.CultureInfo.InvariantCulture, out f))
            return f.ToString(formato, System.Globalization.CultureInfo.InvariantCulture);
        return "--";
    }


    // -----------------------------------------------------------------------
    // Aplicar el cambio de cadena
    // -----------------------------------------------------------------------
    void Aplicar()
    {
        try
        {
            if (cadenaActual == null)
            {
                mensaje.text = "Elige primero una cadena.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }
            mensaje.text = "Procesando...";
            mensaje.color = Color.yellow;

            string nombreCadena = CadenaCampo(cadenaActual, "nombre");
            string ambitoJson = ambito == "todos" ? "todos" : "apoyo";
            string apoyoJson = ambito == "todos"
                ? "1"
                : Mathf.Clamp(seleccionado, 1, totalApoyos).ToString(
                    System.Globalization.CultureInfo.InvariantCulture);

            string json = "{\n"
                + "  \"excel\": \"" + Json.Esc(rutaExcel) + "\",\n"
                + "  \"salida_excel\": \"" + Json.Esc(rutaSalidaExcel) + "\",\n"
                + "  \"conductor\": \"" + Json.Esc(ConductorSeleccionado()) + "\",\n"
                + "  \"apoyos_config\": \"" + Json.Esc(rutaApoyosConfig) + "\",\n"
                + "  \"config_conductor\": \"" + Json.Esc(rutaConductorConfig) + "\",\n"
                + "  \"cadena\": {\n"
                + "    \"nombre\": \"" + Json.Esc(nombreCadena) + "\",\n"
                + "    \"ambito\": \"" + ambitoJson + "\",\n"
                + "    \"apoyo\": " + apoyoJson + "\n"
                + "  }\n"
                + "}";

            string rutaPeticion = Path.Combine(rutaPython, "peticion_cadena.json");
            string rutaResultado = Path.Combine(rutaPython, "resultado_cadena.json");
            File.WriteAllText(rutaPeticion, json, Json.Utf8SinBom);

            EjecutarPython("--peticion \"" + rutaPeticion + "\""
                + " --resultado \"" + rutaResultado + "\"");

            if (!File.Exists(rutaResultado))
                throw new Exception(
                    "Python no genero resultado. Revisa que 'py' este en el PATH.");

            string texto = File.ReadAllText(rutaResultado, System.Text.Encoding.UTF8);
            var doc = Json.Deserialize(texto) as Dictionary<string, object>;
            bool ok = doc != null && doc.ContainsKey("ok") && doc["ok"] is bool b && b;

            if (ok && doc != null)
            {
                string resumen = "CADENA Y CONDUCTOR APLICADOS\n"
                    + "Cadena: " + nombreCadena + "\n"
                    + "Conductor: " + ConductorSeleccionado() + "\n";
                if (doc.ContainsKey("cadena") && doc["cadena"] is Dictionary<string, object> cd
                    && cd.ContainsKey("apoyos_modificados"))
                    resumen += "Apoyos modificados: " + cd["apoyos_modificados"] + "\n";
                resumen += "Excel actualizado (V/T/L, desviacion, mediciones)\ny escena 3D regenerada.";
                mensaje.text = resumen;
                mensaje.color = new Color(0.4f, 1f, 0.5f);
                AvisarRecarga();
            }
            else
            {
                string error = (doc != null && doc.ContainsKey("error"))
                    ? doc["error"].ToString() : "Error desconocido";
                mensaje.text = "AVISO / PARON:\n" + error;
                mensaje.color = new Color(1f, 0.5f, 0.4f);
            }
        }
        catch (Exception ex)
        {
            mensaje.text = "AVISO / PARON:\n" + ex.Message;
            mensaje.color = new Color(1f, 0.5f, 0.4f);
        }
    }

    void CambiarAmbito(string nuevo)
    {
        ambito = nuevo;
        if (apoyoDropdown != null)
            apoyoDropdown.gameObject.SetActive(nuevo == "apoyo");
        MostrarCadena();
    }

    /// <summary>Rellena el desplegable de cadenas con SOLO el nombre Andelec
    /// (p. ej. "LA30-20kV-SUS-SIM-VID").</summary>
    void RellenarCatalogoCadenas()
    {
        if (cadenaDropdown == null) return;
        cadenaDropdown.options.Clear();
        foreach (var d in catalogo)
            cadenaDropdown.options.Add(new Dropdown.OptionData(CadenaCampo(d, "nombre")));
        if (cadenaDropdown.options.Count > 0)
        {
            seleccionCadena = Mathf.Clamp(seleccionCadena, 0,
                cadenaDropdown.options.Count - 1);
            cadenaDropdown.value = seleccionCadena;
        }
    }

    /// <summary>Carga el catalogo de conductores desde Python
    /// ('--catalogo_conductores') y rellena el desplegable.</summary>
    void CargarCatalogoConductores()
    {
        try
        {
            string salida = CacheCatalogos.Obtener(CacheCatalogos.ClaveConductores,
                () => EjecutarPython("cambiar_cadena_conductor.py --catalogo_conductores"));
            var doc = Json.Deserialize(salida) as Dictionary<string, object>;
            catalogoConductores.Clear();
            if (doc != null && doc.ContainsKey("conductores")
                && doc["conductores"] is List<object> lista)
            {
                foreach (var item in lista)
                    if (item is Dictionary<string, object> d)
                        catalogoConductores.Add(d);
            }
            RellenarCatalogoConductores();
            MostrarCadena();
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogWarning(
                "VentanaCadenaConductor (conductores): " + ex.Message);
        }
    }

    /// <summary>Rellena el desplegable de conductores con su nomenclatura
    /// (p. ej. "LA-56") y preselecciona el conductor actual de la linea.</summary>
    void RellenarCatalogoConductores()
    {
        if (conductorDropdown == null) return;
        conductorDropdown.options.Clear();
        foreach (var d in catalogoConductores)
        {
            string nom = CadenaCampo(d, "nomenclatura");
            if (!string.IsNullOrEmpty(nom))
                conductorDropdown.options.Add(new Dropdown.OptionData(nom));
        }
        if (conductorDropdown.options.Count == 0) return;
        string actual = ConductorLinea();
        int idx = 0;
        for (int i = 0; i < conductorDropdown.options.Count; i++)
        {
            if (ClaveConductor(conductorDropdown.options[i].text)
                == ClaveConductor(actual))
            {
                idx = i;
                break;
            }
        }
        sincronizandoDropdown = true;
        conductorDropdown.value = idx;
        sincronizandoDropdown = false;
    }

    /// <summary>Nomenclatura del conductor seleccionado en el desplegable
    /// (o el conductor actual de la linea si no hay catalogo cargado).</summary>
    string ConductorSeleccionado()
    {
        if (conductorDropdown != null && conductorDropdown.options.Count > 0)
        {
            int idx = Mathf.Clamp(conductorDropdown.value, 0,
                conductorDropdown.options.Count - 1);
            return conductorDropdown.options[idx].text;
        }
        return ConductorLinea();
    }

    static string ClaveConductor(string s)
    {
        return string.IsNullOrEmpty(s) ? "" : s.Trim().ToUpperInvariant();
    }

    void AvisarRecarga()
    {
        var generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador != null)
        {
            try { generador.ConstruirEscenaCompleta(); }
            catch (Exception ex)
            { UnityEngine.Debug.LogWarning("Recarga: " + ex.Message); }
        }
    }


    // -----------------------------------------------------------------------
    // Creacion de la UI
    // -----------------------------------------------------------------------
    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemCadena");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var go = new GameObject("CanvasCadena");
        canvas = go.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 2000;
        go.AddComponent<CanvasScaler>().uiScaleMode =
            CanvasScaler.ScaleMode.ScaleWithScreenSize;
        go.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
        go.AddComponent<GraphicRaycaster>();
    }

    void CrearVentana()
    {
        var raiz = new GameObject("VentanaCadena");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(500, 700),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));
        // X visible arriba a la derecha para volver al menu de Gemelo digital
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(228, 322), new Vector2(40, 40), CerrarYVolver);

        titulo = CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 315), 22, TextAnchor.MiddleCenter);

        detalleCadena = CrearTexto(raiz, "Detalle", new Vector2(0.5f, 0.5f),
            new Vector2(0, 225), 14, TextAnchor.MiddleCenter);
        detalleCadena.rectTransform.sizeDelta = new Vector2(460, 125);

        // Desplegable de CONDUCTORES: nomenclatura (p.ej. "LA-56")
        conductorDropdown = UIFactory.CrearDropdown(raiz, "ConductorDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, 125), new Vector2(420, 40));
        conductorDropdown.onValueChanged.AddListener(idx =>
        {
            if (!sincronizandoDropdown) MostrarCadena();
        });

        // Desplegable de CADENAS: solo el nombre Andelec (p.ej. "LA30-20kV-SUS-SIM-VID")
        cadenaDropdown = UIFactory.CrearDropdown(raiz, "CadenaDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, 68), new Vector2(420, 40));
        cadenaDropdown.onValueChanged.AddListener(idx =>
        {
            if (!sincronizandoDropdown)
            {
                seleccionCadena = idx;
                MostrarCadena();
            }
        });

        CrearBoton(raiz, "Todos", "TODA LA LÍNEA", new Vector2(0.5f, 0.5f),
            new Vector2(-110, 8), new Vector2(180, 42), () => CambiarAmbito("todos"));
        CrearBoton(raiz, "Apoyo", "SOLO APOYO Nº", new Vector2(0.5f, 0.5f),
            new Vector2(110, 8), new Vector2(180, 42), () => CambiarAmbito("apoyo"));

        // Desplegable de APOYOS (1, 2, 3...)
        apoyoDropdown = UIFactory.CrearDropdown(raiz, "ApoyoDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, -47), new Vector2(220, 40));
        for (int i = 1; i <= totalApoyos; i++)
            apoyoDropdown.options.Add(new Dropdown.OptionData("Apoyo " + i));
        apoyoDropdown.value = Mathf.Clamp(seleccionado - 1, 0, totalApoyos - 1);
        apoyoDropdown.gameObject.SetActive(ambito == "apoyo");
        apoyoDropdown.onValueChanged.AddListener(idx =>
        {
            if (!sincronizandoDropdown)
            {
                seleccionado = idx + 1;
                MostrarCadena();
            }
        });

        CrearBoton(raiz, "Aplicar", "APLICAR", new Vector2(0.5f, 0.5f),
            new Vector2(0, -107), new Vector2(200, 50), Aplicar);

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -228), 15, TextAnchor.UpperCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(460, 210);
        mensaje.raycastTarget = false;

        CrearBoton(raiz, "Cerrar", "CERRAR", new Vector2(0.5f, 0.5f),
            new Vector2(175, -315), new Vector2(120, 40), CerrarVentana);
    }

    public void AbrirVentana() { if (ventana != null) ventana.SetActive(true); }
    void CerrarVentana() { if (ventana != null) ventana.SetActive(false); }

    void CerrarYVolver()
    {
        CerrarVentana();
        var gestor = FindAnyObjectByType<GestorAplicacionGemelo>();
        if (gestor != null) gestor.ReabrirMenuGemelo();
    }



    // -----------------------------------------------------------------------
    // Utilidades UI
    // -----------------------------------------------------------------------
    Image CrearImagen(GameObject padre, string nombre, Vector2 ancla,
                      Vector2 pos, Vector2 tam, Color color)
    {
        var go = new GameObject(nombre);
        go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = ancla; rt.anchorMax = ancla; rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = pos;
        rt.sizeDelta = tam;
        var img = go.AddComponent<Image>();
        img.color = color;
        return img;
    }

    Text CrearTexto(GameObject padre, string nombre, Vector2 ancla,
                    Vector2 pos, int tamano, TextAnchor alineacion)
    {
        var go = new GameObject(nombre);
        go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = ancla; rt.anchorMax = ancla; rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = pos;
        rt.sizeDelta = new Vector2(400, 40);
        var txt = go.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = tamano;
        txt.alignment = alineacion;
        txt.color = Color.white;
        txt.horizontalOverflow = HorizontalWrapMode.Wrap;
        txt.verticalOverflow = VerticalWrapMode.Overflow;
        return txt;
    }

    InputField CrearCampo(GameObject padre, string nombre, Vector2 ancla,
                          Vector2 pos, Vector2 tam)
    {
        var go = new GameObject(nombre);
        go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = ancla; rt.anchorMax = ancla; rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = pos;
        rt.sizeDelta = tam;

        var img = go.AddComponent<Image>();
        img.color = new Color(0.2f, 0.25f, 0.35f, 1f);

        var campo = go.AddComponent<InputField>();
        campo.targetGraphic = img;

        // Unity solo permite UN Graphic por objeto: el texto va en un HIJO.
        var hijo = new GameObject("Texto");
        hijo.transform.SetParent(go.transform, false);
        var hrt = hijo.AddComponent<RectTransform>();
        hrt.anchorMin = Vector2.zero; hrt.anchorMax = Vector2.one;
        hrt.offsetMin = new Vector2(6, 0); hrt.offsetMax = new Vector2(-6, 0);
        var texto = hijo.AddComponent<Text>();
        texto.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        texto.fontSize = 20;
        texto.alignment = TextAnchor.MiddleCenter;
        texto.color = Color.white;
        texto.supportRichText = false;
        campo.textComponent = texto;
        return campo;
    }

    Button CrearBoton(GameObject padre, string nombre, string etiqueta,
                      Vector2 ancla, Vector2 pos, Vector2 tam, UnityEngine.Events.UnityAction onClic)
    {
        var go = new GameObject(nombre);
        go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = ancla; rt.anchorMax = ancla; rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = pos;
        rt.sizeDelta = tam;
        var img = go.AddComponent<Image>();
        img.color = new Color(0.2f, 0.35f, 0.55f, 1f);
        var btn = go.AddComponent<Button>();
        btn.targetGraphic = img;
        UiBoton.AplicarEstilo(btn);
        btn.onClick.AddListener(onClic);

        // Unity solo permite UN Graphic por objeto: el texto va en un HIJO.
        var hijo = new GameObject("Etiqueta");
        hijo.transform.SetParent(go.transform, false);
        var hrt = hijo.AddComponent<RectTransform>();
        hrt.anchorMin = Vector2.zero; hrt.anchorMax = Vector2.one;
        hrt.offsetMin = Vector2.zero; hrt.offsetMax = Vector2.zero;
        var txt = hijo.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = 15;
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.text = etiqueta;
        txt.raycastTarget = false;
        return btn;
    }
}
