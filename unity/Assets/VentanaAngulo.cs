using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

/// <summary>
/// VentanaAngulo — Edita MANUALMENTE el angulo de un apoyo (apoyos de angulo).
/// ============================================================================
/// Al pulsar "APLICAR":
///   1. Escribe una peticion JSON en la raiz del proyecto.
///   2. Llama a Python:  py editar_angulo.py --peticion ... --resultado ...
///   3. Python actualiza el angulo en 'Cálculo de apoyos', recalcula
///      S = 2*cos(alfa/2), los ESFUERZOS V/T/L, los graficos de utilizacion y
///      la rotacion 3D del apoyo (coordenadas_linea.csv).
///   4. Unity reconstruye la escena 3D.
///
/// GENERAL: funciona para cualquier apoyo/linea/excel de la plantilla.
/// </summary>
public class VentanaAngulo : MonoBehaviour
{
    private string rutaPython = "";
    private string rutaExcel = "";
    private string rutaSalidaExcel = "";
    private string rutaUtm = "";

    private Canvas canvas;
    private GameObject ventana;
    private Text titulo;
    private Text detalle;
    private Text mensaje;
    private InputField campo;
    private Dropdown apoyoDropdown;
    private bool sincronizandoDropdown = false;

    private List<Dictionary<string, object>> apoyos =
        new List<Dictionary<string, object>>();
    private int selApoyo = 0;

    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaAngulo>() == null)
        {
            var go = new GameObject("VentanaAngulo");
            go.AddComponent<VentanaAngulo>();
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
            rutaUtm = BuscarRutaUtm(rutaPython, nombreExcel);

            CrearCanvasYEventSystem();
            CrearVentana();
            Invoke("CargarListado", 0.6f);
            DontDestroyOnLoad(gameObject);
            UnityEngine.Debug.Log("[VentanaAngulo] ventana creada");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaAngulo: " + ex.Message);
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

    /// <summary>Localiza el JSON UTM de la linea. La carpeta de trabajo activa
    /// no siempre contiene los utm_*.json; se busca tambien en la base (raiz
    /// del TFG en editor, Datos/ en build). Se prefiere 'utm_editado.json'
    /// porque acumula los movimientos ya aplicados.</summary>
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

    string EjecutarPython(string argumentos)
    {
        return MotorHelper.EjecutarMotor("editar_angulo", argumentos);
    }

    void CargarListado()
    {
        try
        {
            // Listado de solo lectura: se cachea para aperturas rapidas. Si se
            // aplica un cambio, CacheCatalogos se invalida al reconstruir.
            string texto = CacheCatalogos.Obtener(CacheCatalogos.ClaveAngulos, () =>
            {
                string rutaPeticion = Path.Combine(rutaPython, "peticion_angulos.json");
                string rutaResultado = Path.Combine(rutaPython, "resultado_angulos.json");
                File.WriteAllText(rutaPeticion,
                    "{\n  \"excel\": \"" + Json.Esc(rutaExcel) + "\"\n}",
                    System.Text.Encoding.UTF8);

                EjecutarPython("--listado \"" + rutaPeticion + "\""
                    + " --resultado \"" + rutaResultado + "\"");

                if (!File.Exists(rutaResultado))
                    throw new Exception(
                        "Python no genero resultado. Revisa que 'py' este en el PATH.");

                return File.ReadAllText(rutaResultado, System.Text.Encoding.UTF8);
            });
            var doc = Json.Deserialize(texto) as Dictionary<string, object>;
            if (doc == null || !(bool)doc["ok"] || !doc.ContainsKey("datos"))
            {
                string error = doc != null && doc.ContainsKey("error")
                    ? doc["error"].ToString() : "Error al leer los angulos.";
                mensaje.text = "AVISO / PARON:\n" + error;
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }
            var datos = doc["datos"];
            if (datos is List<object> lista)
            {
                apoyos.Clear();
                foreach (var item in lista)
                    if (item is Dictionary<string, object> d) apoyos.Add(d);
            }
            if (apoyos.Count == 0)
            {
                mensaje.text = "No se encontraron apoyos de ángulo\n"
                    + "(tipo 'Ang-*' = angulo anclaje/amarre) en la línea.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }
            RellenarApoyosDropdown();
            MostrarEstado();
        }
        catch (Exception ex)
        {
            mensaje.text = "AVISO / PARON:\n" + ex.Message;
            mensaje.color = new Color(1f, 0.5f, 0.4f);
        }
    }

    void MostrarEstado()
    {
        if (apoyos.Count == 0) return;
        sincronizandoDropdown = true;
        if (apoyoDropdown != null && apoyoDropdown.options.Count > 0)
            apoyoDropdown.value = selApoyo;
        sincronizandoDropdown = false;
        var ap = apoyos[Mathf.Clamp(selApoyo, 0, apoyos.Count - 1)];
        string tipo = ap.ContainsKey("tipo") && ap["tipo"] != null
            ? ap["tipo"].ToString() : "";
        string angulo = ap.ContainsKey("angulo") && ap["angulo"] != null
            ? ap["angulo"].ToString().Replace(',', '.') : "--";
        string s = ap.ContainsKey("S") && ap["S"] != null
            ? ap["S"].ToString().Replace(',', '.') : "--";
        string esAng = ap.ContainsKey("es_de_angulo") && (bool)ap["es_de_angulo"]
            ? "SI (apoyo de angulo)" : "no (recta)";

        titulo.text = "EDITAR ANGULO";
        detalle.text = "Apoyo: " + ap["numero"]
            + "  |  " + tipo
            + "\nAngulo actual: " + angulo + " deg"
            + "  |  S = " + s
            + "\n" + esAng;
        campo.text = angulo == "--" ? "" : angulo;
        mensaje.text = "";
    }

    /// <summary>Rellena el desplegable con "Apoyo N" (el numero real del Excel).</summary>
    void RellenarApoyosDropdown()
    {
        if (apoyoDropdown == null) return;
        apoyoDropdown.options.Clear();
        for (int i = 0; i < apoyos.Count; i++)
        {
            var ap = apoyos[i];
            string num = (ap != null && ap.ContainsKey("numero") && ap["numero"] != null)
                ? ap["numero"].ToString() : (i + 1).ToString();
            apoyoDropdown.options.Add(new Dropdown.OptionData("Apoyo " + num));
        }
        if (apoyoDropdown.options.Count > 0)
            apoyoDropdown.value = Mathf.Clamp(selApoyo, 0, apoyos.Count - 1);
    }

    void Aplicar()
    {
        try
        {
            if (apoyos.Count == 0)
            {
                mensaje.text = "Primero carga el listado de apoyos.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }
            var ap = apoyos[Mathf.Clamp(selApoyo, 0, apoyos.Count - 1)];

            string textoCampo = campo.text.Replace(',', '.');
            double anguloNuevo;
            if (!double.TryParse(textoCampo, System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out anguloNuevo)
                || anguloNuevo <= 0.0 || anguloNuevo > 180.0)
            {
                mensaje.text = "Introduce un angulo valido (0 < a <= 180 grados).";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }

            mensaje.text = "Procesando...";
            mensaje.color = Color.yellow;

            string json = "{\n"
                + "  \"excel\": \"" + Json.Esc(rutaExcel) + "\",\n"
                + "  \"utm\": \"" + Json.Esc(rutaUtm) + "\",\n"
                + "  \"salida_excel\": \"" + Json.Esc(rutaSalidaExcel) + "\",\n"
                + "  \"apoyo\": " + ap["numero"] + ",\n"
                + "  \"angulo\": "
                + anguloNuevo.ToString(System.Globalization.CultureInfo.InvariantCulture)
                + "\n}";

            string rutaPeticion = Path.Combine(rutaPython, "peticion_angulo.json");
            string rutaResultado = Path.Combine(rutaPython, "resultado_angulo.json");
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
                string resumen = "ANGULO APLICADO\n"
                    + "Apoyo " + ap["numero"] + "\n"
                    + "Angulo: " + (doc.ContainsKey("angulo_anterior") ? doc["angulo_anterior"] : "")
                    + " -> " + (doc.ContainsKey("angulo_nuevo") ? doc["angulo_nuevo"] : "")
                    + " deg\n"
                    + "S = " + (doc.ContainsKey("S_nuevo") ? doc["S_nuevo"] : "")
                    + "\nEsfuerzos V/T/L, graficos y 3D actualizados.";
                if (doc.ContainsKey("apoyos_movidos")
                    && doc["apoyos_movidos"] is List<object> movidos
                    && movidos.Count > 0)
                {
                    resumen += "\nCoordenadas aguas abajo actualizadas:\napoyos "
                        + string.Join(", ", movidos);
                }
                if (doc.ContainsKey("aviso_cascada")
                    && doc["aviso_cascada"] is string aviso
                    && !string.IsNullOrEmpty(aviso))
                {
                    resumen += "\n(aviso: " + aviso + ")";
                }
                mensaje.text = resumen;
                mensaje.color = new Color(0.4f, 1f, 0.5f);
                Invoke("RefrescarEstado", 0.3f);
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

    void RefrescarEstado() { CargarListado(); }

    void AvisarRecarga()
    {
        var generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador != null)
        {
            try { generador.ConstruirEscenaCompleta(); }
            catch (Exception ex)
            { UnityEngine.Debug.LogWarning("Recarga angulo: " + ex.Message); }
        }
    }


    // -----------------------------------------------------------------------
    // Creacion de la UI
    // -----------------------------------------------------------------------
    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemAngulo");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var go = new GameObject("CanvasAngulo");
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
        var raiz = new GameObject("VentanaAnguloUI");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(480, 400),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));
        // X visible arriba a la derecha para volver al menu de Gemelo digital
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(218, 178), new Vector2(40, 40), CerrarYVolver);

        titulo = CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 170), 20, TextAnchor.MiddleCenter);

        // Desplegable de APOYOS (sustituye a las flechas < >)
        apoyoDropdown = UIFactory.CrearDropdown(raiz, "ApoyoDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, 105), new Vector2(220, 36));
        apoyoDropdown.onValueChanged.AddListener(idx =>
        {
            if (!sincronizandoDropdown)
            {
                selApoyo = idx;
                MostrarEstado();
            }
        });

        detalle = CrearTexto(raiz, "Detalle", new Vector2(0.5f, 0.5f),
            new Vector2(0, 30), 15, TextAnchor.MiddleCenter);
        detalle.rectTransform.sizeDelta = new Vector2(440, 90);

        CrearTexto(raiz, "EtiquetaCampo", new Vector2(0.5f, 0.5f),
            new Vector2(0, -45), 14, TextAnchor.MiddleCenter).text =
            "Nuevo angulo (grados):";

        campo = CrearCampo(raiz, "Campo", new Vector2(0.5f, 0.5f),
            new Vector2(0, -95), new Vector2(160, 40));

        CrearBoton(raiz, "Aplicar", "APLICAR", new Vector2(0.5f, 0.5f),
            new Vector2(0, -150), new Vector2(200, 50), Aplicar);

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -235), 14, TextAnchor.UpperCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(440, 120);
        mensaje.raycastTarget = false;

        CrearBoton(raiz, "Cerrar", "CERRAR", new Vector2(0.5f, 0.5f),
            new Vector2(170, -175), new Vector2(120, 40), CerrarVentana);
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
