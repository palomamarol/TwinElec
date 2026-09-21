using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

/// <summary>
/// VentanaTensiones — Edita MANUALMENTE la tension de un tramo en
/// 'T. reg. cond. fase' del gemelo digital.
/// ============================================================================
/// Al pulsar "APLICAR":
///   1. Escribe una peticion JSON en la raiz del proyecto.
///   2. Llama a Python:  py editar_tension.py --peticion ... --resultado ...
///   3. Python deduce el estado EDS (inversa del cambio de estado), recalcula
///      el RESTO de tensiones del vano de regulacion, la tabla por temperatura,
///      los ESFUERZOS V/T/L de las hipotesis 1a-4a, los graficos de utilizacion
///      y fisica_linea.json (para que el 3D refleje la nueva tension).
///   4. Unity reconstruye la escena 3D.
///
/// GENERAL: funciona para cualquier linea/excel de la plantilla.
/// </summary>
public class VentanaTensiones : MonoBehaviour
{
    private string rutaPython = "";
    private string rutaExcel = "";
    private string rutaSalidaExcel = "";

    private Canvas canvas;
    private GameObject ventana;
    private Text titulo;
    private Text detalle;
    private Text mensaje;
    private InputField campo;

    // Datos del listado (los trae Python)
    private List<Dictionary<string, object>> tramos =
        new List<Dictionary<string, object>>();
    private List<string> condiciones = new List<string>();
    private int selTramo = 0;
    private int selCond = 0;

    private static readonly Dictionary<string, string> ETIQUETAS =
        new Dictionary<string, string>
    {
        { "TVF",  "T.max viento (-10C, Sv)" },
        { "THF",  "T.max hielo (-15C, Sh)" },
        { "TVHF", "T.max hielo+viento" },
        { "TVM",  "T.viento 1/2 (-10C)" },
        { "15V",  "15C + Viento" },
        { "T0H",  "0C + Hielo" },
        { "TTemp","50C (temp. max)" },
    };

    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaTensiones>() == null)
        {
            var go = new GameObject("VentanaTensiones");
            go.AddComponent<VentanaTensiones>();
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

            CrearCanvasYEventSystem();
            CrearVentana();
            Invoke("CargarListado", 0.6f);
            DontDestroyOnLoad(gameObject);
            UnityEngine.Debug.Log("[VentanaTensiones] ventana creada");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaTensiones: " + ex.Message);
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

    string EjecutarPython(string argumentos)
    {
        return MotorHelper.EjecutarMotor("editar_tension", argumentos);
    }

    // -----------------------------------------------------------------------
    // Cargar el listado de tensiones actuales (Python)
    // -----------------------------------------------------------------------
    void CargarListado()
    {
        try
        {
            // Listado de solo lectura: se cachea para aperturas rapidas. Si se
            // aplica un cambio, CacheCatalogos se invalida al reconstruir.
            string texto = CacheCatalogos.Obtener(CacheCatalogos.ClaveTensiones, () =>
            {
                string rutaPeticion = Path.Combine(rutaPython, "peticion_listado.json");
                string rutaResultado = Path.Combine(rutaPython, "resultado_listado.json");
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
            if (doc == null || !(doc.ContainsKey("ok")) || !(bool)doc["ok"]
                || !doc.ContainsKey("datos"))
            {
                string error = doc != null && doc.ContainsKey("error")
                    ? doc["error"].ToString() : "Error al leer las tensiones.";
                mensaje.text = "AVISO / PARON:\n" + error;
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }
            var datos = doc["datos"] as Dictionary<string, object>;
            if (datos != null && datos.ContainsKey("tramos")
                && datos["tramos"] is List<object> lista)
            {
                tramos.Clear();
                foreach (var item in lista)
                    if (item is Dictionary<string, object> d) tramos.Add(d);
            }
            condiciones.Clear();
            if (datos != null && datos.ContainsKey("condiciones")
                && datos["condiciones"] is List<object> conds)
            {
                foreach (var c in conds) condiciones.Add(c.ToString());
            }
            if (tramos.Count == 0)
            {
                mensaje.text = "No se leyeron tramos. Revisa el Excel.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }
            MostrarEstado();
        }
        catch (Exception ex)
        {
            mensaje.text = "AVISO / PARON:\n" + ex.Message;
            mensaje.color = new Color(1f, 0.5f, 0.4f);
        }
    }

    string CondActual()
    {
        if (condiciones.Count == 0) return "";
        return condiciones[Mathf.Clamp(selCond, 0, condiciones.Count - 1)];
    }

    void MostrarEstado()
    {
        if (tramos.Count == 0) return;
        var tramo = tramos[Mathf.Clamp(selTramo, 0, tramos.Count - 1)];
        string cond = CondActual();
        string actual = "";
        if (tramo.ContainsKey("tensiones") && tramo["tensiones"] is Dictionary<string, object> tens
            && tens.ContainsKey(cond) && tens[cond] != null)
            actual = tens[cond].ToString().Replace(',', '.');

        titulo.text = "EDITAR TENSIONES";
        detalle.text = "Tramo: " + tramo["tramo"]
            + "\nCondicion: " + cond + "\n"
            + (ETIQUETAS.ContainsKey(cond) ? ETIQUETAS[cond] : "")
            + "\nTension actual: " + (actual == "" ? "--" : actual + " daN");
        campo.text = actual == "" ? "" : actual;
        mensaje.text = "";
    }

    void CambiarTramo(int delta)
    {
        if (tramos.Count == 0) return;
        selTramo = Mathf.Clamp(selTramo + delta, 0, tramos.Count - 1);
        MostrarEstado();
    }

    void CambiarCondicion(int delta)
    {
        if (condiciones.Count == 0) return;
        selCond = Mathf.Clamp(selCond + delta, 0, condiciones.Count - 1);
        MostrarEstado();
    }


    // -----------------------------------------------------------------------
    // Aplicar la edicion
    // -----------------------------------------------------------------------
    void Aplicar()
    {
        try
        {
            if (tramos.Count == 0 || condiciones.Count == 0)
            {
                mensaje.text = "Primero carga el listado de tensiones.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }
            var tramo = tramos[Mathf.Clamp(selTramo, 0, tramos.Count - 1)];
            string cond = CondActual();
            if (!tramo.ContainsKey("i") || !tramo.ContainsKey("j"))
            {
                mensaje.text = "Tramo sin numeros validos.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }

            string textoCampo = campo.text.Replace(',', '.');
            double nuevaT;
            if (!double.TryParse(textoCampo, System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out nuevaT)
                || nuevaT <= 0.0)
            {
                mensaje.text = "Introduce una tension valida (> 0 daN).";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
                return;
            }

            mensaje.text = "Procesando...";
            mensaje.color = Color.yellow;

            string json = "{\n"
                + "  \"excel\": \"" + Json.Esc(rutaExcel) + "\",\n"
                + "  \"salida_excel\": \"" + Json.Esc(rutaSalidaExcel) + "\",\n"
                + "  \"tramo_i\": " + tramo["i"] + ",\n"
                + "  \"tramo_j\": " + tramo["j"] + ",\n"
                + "  \"condicion\": \"" + cond + "\",\n"
                + "  \"tension_daN\": "
                + nuevaT.ToString(System.Globalization.CultureInfo.InvariantCulture)
                + "\n}";

            string rutaPeticion = Path.Combine(rutaPython, "peticion_tension.json");
            string rutaResultado = Path.Combine(rutaPython, "resultado_tension.json");
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
                string resumen = "TENSION APLICADA\n"
                    + "Tramo " + tramo["tramo"] + " | " + cond + "\n"
                    + "T pedida: " + (doc.ContainsKey("tension_pedida_daN") ? doc["tension_pedida_daN"] : "")
                    + " daN\n"
                    + "T resultante: " + (doc.ContainsKey("tension_resultante_daN") ? doc["tension_resultante_daN"] : "")
                    + " daN\n"
                    + "EDS t0: " + (doc.ContainsKey("t0_anterior_daN") ? doc["t0_anterior_daN"] : "")
                    + " -> " + (doc.ContainsKey("t0_nuevo_daN") ? doc["t0_nuevo_daN"] : "")
                    + " daN\n"
                    + "Resto de tensiones, V/T/L y graficos recalculados.";
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
            { UnityEngine.Debug.LogWarning("Recarga tensiones: " + ex.Message); }
        }
    }


    // -----------------------------------------------------------------------
    // Creacion de la UI
    // -----------------------------------------------------------------------
    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemTensiones");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var go = new GameObject("CanvasTensiones");
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
        var raiz = new GameObject("VentanaTensionesUI");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(500, 430),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));
        // X visible arriba a la derecha para volver al menu de Gemelo digital
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(228, 193), new Vector2(40, 40), CerrarYVolver);

        titulo = CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 190), 20, TextAnchor.MiddleCenter);

        CrearBoton(raiz, "PrevTramo", "< Tramo", new Vector2(0.5f, 0.5f),
            new Vector2(-105, 120), new Vector2(130, 40), () => CambiarTramo(-1));
        CrearBoton(raiz, "NextTramo", "Tramo >", new Vector2(0.5f, 0.5f),
            new Vector2(105, 120), new Vector2(130, 40), () => CambiarTramo(1));

        CrearBoton(raiz, "PrevCond", "< Cond", new Vector2(0.5f, 0.5f),
            new Vector2(-105, 60), new Vector2(130, 40), () => CambiarCondicion(-1));
        CrearBoton(raiz, "NextCond", "Cond >", new Vector2(0.5f, 0.5f),
            new Vector2(105, 60), new Vector2(130, 40), () => CambiarCondicion(1));

        detalle = CrearTexto(raiz, "Detalle", new Vector2(0.5f, 0.5f),
            new Vector2(0, 20), 15, TextAnchor.MiddleCenter);
        detalle.rectTransform.sizeDelta = new Vector2(460, 90);

        CrearTexto(raiz, "EtiquetaCampo", new Vector2(0.5f, 0.5f),
            new Vector2(0, -60), 14, TextAnchor.MiddleCenter).text =
            "Nueva tension (daN):";

        campo = CrearCampo(raiz, "Campo", new Vector2(0.5f, 0.5f),
            new Vector2(0, -110), new Vector2(160, 40));

        CrearBoton(raiz, "Aplicar", "APLICAR", new Vector2(0.5f, 0.5f),
            new Vector2(0, -165), new Vector2(200, 50), Aplicar);

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -260), 14, TextAnchor.UpperCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(460, 130);
        mensaje.raycastTarget = false;

        CrearBoton(raiz, "Cerrar", "CERRAR", new Vector2(0.5f, 0.5f),
            new Vector2(175, -195), new Vector2(120, 40), CerrarVentana);
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
