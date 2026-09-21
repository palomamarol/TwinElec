using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

/// <summary>
/// VentanaCrucetas — Cambia la semicruceta de un apoyo por otra del catalogo.
/// ==========================================================================
/// Permite, para el apoyo seleccionado: cambiar la LONGITUD (1,25..2,50 m) y
/// hacerla PLANA (ASC) o ATIRANTADA (ATC), es decir, sustituirla por cualquier
/// otra semicruceta del catalogo.
///
/// Al pulsar "APLICAR":
///   1. Escribe una peticion JSON en la raiz del proyecto.
///   2. Llama a Python:  py cambiar_cruceta.py --peticion ... --resultado ...
///   3. Python actualiza el Excel de trabajo ('Apoyos y crucetas') y
///      apoyos_configurados.json.
///   4. La escena se reconstruye con la nueva semicruceta.
/// </summary>
public class VentanaCrucetas : MonoBehaviour
{
    private struct OpcionCruceta
    {
        public string referencia; // "ASC-20"
        public string tipo;       // "ASC" | "ATC"
        public float longitud;    // metros
        public bool atirantada;
    }

    // Rutas
    private string rutaPython = "";
    private string rutaExcel = "";
    private string rutaSalidaExcel = "";
    private string rutaConfig = "";

    // UI
    private Canvas canvas;
    private GameObject ventana;
    private Text titulo;
    private Text crucetaActual;
    private Text mensaje;
    private Text pista;
    private Dropdown apoyoDropdown;
    private Dropdown crucetaDropdown;
    private VistaPrevia3D vistaPrevia;  // vista 3D de la semicruceta seleccionada

    // Estado
    private int seleccionado = 1;
    private int totalApoyos = 4;
    private int indiceOpcion = 0;
    private bool sincronizandoDropdown = false;
    private List<OpcionCruceta> opciones = new List<OpcionCruceta>();

    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaCrucetas>() == null)
        {
            var go = new GameObject("VentanaCrucetas");
            go.AddComponent<VentanaCrucetas>();
        }
    }

    void Awake()
    {
        try
        {
            rutaPython = RutasGemelo.RutaDatos(); // raiz TFG (editor) o Datos/ (build)
            string nombreExcel = BuscarExcelTrabajo();
            rutaExcel = Path.Combine(rutaPython, nombreExcel + ".xlsx");
            rutaSalidaExcel = Path.Combine(rutaPython, nombreExcel + "_editada.xlsx");
            if (File.Exists(rutaSalidaExcel)) rutaExcel = rutaSalidaExcel;
            rutaConfig = Path.Combine(RutasGemelo.RutaAssetsGemelo(),
                                      "apoyos_configurados.json");

            ConstruirOpciones();
            CargarApoyosConfig();
            CrearCanvasYEventSystem();
            CrearVentana();
            MostrarApoyo(1);
            DontDestroyOnLoad(gameObject);
            UnityEngine.Debug.Log("[VentanaCrucetas] creada con "
                + opciones.Count + " semicrucetas del catalogo.");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaCrucetas: " + ex.Message);
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

    void ConstruirOpciones()
    {
        // Catalogo Serie C: semicrucetas ASC (planas) y ATC (atirantadas)
        int[] codigos = { 12, 15, 17, 20, 22, 25 };
        float[] longitudes = { 1.25f, 1.50f, 1.75f, 2.00f, 2.25f, 2.50f };
        opciones.Clear();
        foreach (string tipo in new string[] { "ASC", "ATC" })
        {
            for (int i = 0; i < codigos.Length; i++)
            {
                opciones.Add(new OpcionCruceta
                {
                    referencia = tipo + "-" + codigos[i],
                    tipo = tipo,
                    longitud = longitudes[i],
                    atirantada = tipo == "ATC",
                });
            }
        }
    }

    void CargarApoyosConfig()
    {
        if (!File.Exists(rutaConfig)) return;
        var doc = JsonUtility.FromJson<DocumentoApoyosConfigurados>(
            File.ReadAllText(rutaConfig, System.Text.Encoding.UTF8));
        if (doc != null && doc.apoyos != null && doc.apoyos.Length > 0)
        {
            totalApoyos = doc.apoyos.Length;
        }
    }

    string CrucetaActualDelApoyo(int numero)
    {
        if (!File.Exists(rutaConfig)) return "";
        var doc = JsonUtility.FromJson<DocumentoApoyosConfigurados>(
            File.ReadAllText(rutaConfig, System.Text.Encoding.UTF8));
        if (doc == null || doc.apoyos == null) return "";
        foreach (var a in doc.apoyos)
        {
            if (a != null && a.apoyo != null && a.apoyo.numero == numero
                && a.cruceta != null)
            {
                string refe = a.cruceta.tipo_origen;
                if (string.IsNullOrEmpty(refe)) refe = a.cruceta.modelo_id;
                return refe == null ? "" : refe.Replace("C_", "");
            }
        }
        return "";
    }

    void MostrarApoyo(int n)
    {
        if (n < 1) n = 1;
        if (n > totalApoyos) n = totalApoyos;
        seleccionado = n;
        titulo.text = "CAMBIAR SEMICRUCETA - APOYO " + n;
        sincronizandoDropdown = true;
        if (apoyoDropdown != null) apoyoDropdown.value = n - 1;
        sincronizandoDropdown = false;
        SincronizarConActual();
        ActualizarLabelOpcion();
        ActualizarVistaPrevia();
        mensaje.text = "";
    }

    void SincronizarConActual()
    {
        string actual = CrucetaActualDelApoyo(seleccionado);
        crucetaActual.text = "Semicruceta actual: " + actual;
        for (int i = 0; i < opciones.Count; i++)
        {
            if (opciones[i].referencia == actual)
            {
                indiceOpcion = i;
                return;
            }
        }
        // Si la actual no es una semicruceta ASC/ATC, se deja la primera
        // opcion (la referencia actual se sigue viendo arriba).
        indiceOpcion = 0;
    }

    void ActualizarLabelOpcion()
    {
        if (crucetaDropdown == null || opciones.Count == 0) return;
        if (indiceOpcion < 0 || indiceOpcion >= opciones.Count) return;
        sincronizandoDropdown = true;
        crucetaDropdown.value = indiceOpcion;
        sincronizandoDropdown = false;
    }

    /// <summary>Muestra en 3D la semicruceta seleccionada del desplegable.</summary>
    void ActualizarVistaPrevia()
    {
        if (vistaPrevia == null) return;
        if (indiceOpcion < 0 || indiceOpcion >= opciones.Count)
        {
            vistaPrevia.Ocultar();
            return;
        }
        // Las semicrucetas planas (ASC) se muestran desde ARRIBA para apreciar
        // su forma triangular; las atirantadas (ATC) mantienen la vista 3/4.
        vistaPrevia.Mostrar(opciones[indiceOpcion].referencia,
            opciones[indiceOpcion].tipo == "ASC");
    }

    // ====================================================================
    // Aplicar: llama a Python y reconstruye la escena
    // ====================================================================
    void Aplicar()
    {
        try
        {
            if (opciones.Count == 0)
            {
                throw new Exception("Catalogo de semicrucetas vacio.");
            }
            mensaje.text = "Procesando...";
            mensaje.color = Color.yellow;
            OpcionCruceta o = opciones[indiceOpcion];
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            string json = "{\n"
                + "  \"excel\": \"" + Json.Esc(rutaExcel) + "\",\n"
                + "  \"salida_excel\": \"" + Json.Esc(rutaSalidaExcel) + "\",\n"
                + "  \"apoyo\": " + seleccionado + ",\n"
                + "  \"tipo\": \"" + o.tipo + "\",\n"
                + "  \"longitud\": " + o.longitud.ToString("0.00", inv) + "\n"
                + "}";
            string rutaPeticion = Path.Combine(rutaPython, "peticion_cruceta.json");
            string rutaResultado = Path.Combine(rutaPython, "resultado_cruceta.json");
            File.WriteAllText(rutaPeticion, json, Json.Utf8SinBom);

            MotorHelper.EjecutarMotor("cambiar_cruceta",
                "--peticion \"" + rutaPeticion + "\""
                + " --resultado \"" + rutaResultado + "\"");

            if (!File.Exists(rutaResultado))
            {
                throw new Exception("Python no genero resultado. Revisa que 'py' este en el PATH.");
            }
            string texto = File.ReadAllText(rutaResultado, System.Text.Encoding.UTF8);
            var doc = Json.Deserialize(texto) as Dictionary<string, object>;
            bool ok = doc != null && doc.ContainsKey("ok") && doc["ok"] is bool b && b;
            if (ok && doc != null)
            {
                string anterior = (doc.ContainsKey("modelo_anterior")
                    ? doc["modelo_anterior"].ToString() : "?");
                string nuevo = (doc.ContainsKey("modelo_nuevo")
                    ? doc["modelo_nuevo"].ToString() : o.referencia);
                mensaje.text = "APOYO " + seleccionado + ":\n"
                    + anterior + " -> " + nuevo + "\n"
                    + o.tipo + " " + o.longitud.ToString("0.00") + " m | "
                    + (o.atirantada ? "ATIRANTADA" : "PLANA") + "\n"
                    + "Excel y escena actualizados.";
                mensaje.color = new Color(0.4f, 1f, 0.5f);
                AvisarRecarga();
                SincronizarConActual();
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

    void AvisarRecarga()
    {
        var generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador != null)
        {
            try { generador.ConstruirEscenaCompleta(); }
            catch (Exception ex) { UnityEngine.Debug.LogWarning("Recarga: " + ex.Message); }
        }
    }

    // ====================================================================
    // Creacion de la UI
    // ====================================================================
    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemCrucetas");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var go = new GameObject("CanvasCrucetas");
        canvas = go.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 2000;
        go.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        go.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
        go.AddComponent<GraphicRaycaster>();
    }

    void CrearVentana()
    {
        var raiz = new GameObject("VentanaCrucetasUI");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(440, 540),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));
        // X visible arriba a la derecha para volver al menu de Gemelo digital
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(198, 248), new Vector2(40, 40), CerrarYVolver);

        // Ayuda (arriba, separada del titulo)
        pista = CrearTexto(raiz, "Pista", new Vector2(0.5f, 0.5f),
            new Vector2(0, 256), 13, TextAnchor.MiddleCenter);
        pista.color = new Color(0.75f, 0.78f, 0.85f);
        pista.rectTransform.sizeDelta = new Vector2(420, 24);
        pista.text = "Pulsa sobre una semicruceta en el 3D para seleccionar su apoyo.";

        titulo = CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 220), 20, TextAnchor.MiddleCenter);
        titulo.rectTransform.sizeDelta = new Vector2(420, 48);

        // Desplegable de APOYOS (sustituye a los botones < >)
        apoyoDropdown = UIFactory.CrearDropdown(raiz, "ApoyoDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, 178), new Vector2(220, 36));
        for (int i = 1; i <= totalApoyos; i++)
            apoyoDropdown.options.Add(new Dropdown.OptionData("Apoyo " + i));
        apoyoDropdown.value = seleccionado - 1;
        apoyoDropdown.onValueChanged.AddListener(idx =>
        {
            if (!sincronizandoDropdown) MostrarApoyo(idx + 1);
        });

        crucetaActual = CrearTexto(raiz, "CrucetaActual", new Vector2(0.5f, 0.5f),
            new Vector2(0, 126), 15, TextAnchor.MiddleCenter);
        crucetaActual.rectTransform.sizeDelta = new Vector2(420, 26);

        // Desplegable de SEMICRUCETAS (sustituye a los botones < >)
        crucetaDropdown = UIFactory.CrearDropdown(raiz, "CrucetaDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, 78), new Vector2(300, 36));
        foreach (var o in opciones)
            crucetaDropdown.options.Add(new Dropdown.OptionData(TextoOpcion(o)));
        crucetaDropdown.value = 0;
        crucetaDropdown.onValueChanged.AddListener(idx =>
        {
            if (sincronizandoDropdown) return;
            if (idx >= 0 && idx < opciones.Count)
            {
                indiceOpcion = idx;
                mensaje.text = "";
                ActualizarVistaPrevia();
            }
        });

        CrearBoton(raiz, "Aplicar", "APLICAR CRUCETA", new Vector2(0.5f, 0.5f),
            new Vector2(0, 22), new Vector2(220, 50), Aplicar);

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -150), 15, TextAnchor.UpperCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(410, 230);
        mensaje.raycastTarget = false;

        CrearBoton(raiz, "Aceptar", "ACEPTAR", new Vector2(0.5f, 0.5f),
            new Vector2(150, -235), new Vector2(110, 40), AceptarCambios);

        // --- VISTA PREVIA 3D a la derecha (selector tipo videojuego) ---
        CrearImagen(raiz, "PanelPreview", new Vector2(0.5f, 0.5f),
            new Vector2(440, 10), new Vector2(340, 460),
            new Color(0.055f, 0.075f, 0.12f, 0.98f));
        CrearTexto(raiz, "TituloPreview", new Vector2(0.5f, 0.5f),
            new Vector2(440, 205), 15, TextAnchor.MiddleCenter).text =
            "VISTA PREVIA 3D";
        var rawGo = new GameObject("ImagenPreview");
        rawGo.transform.SetParent(raiz.transform, false);
        var rawRt = rawGo.AddComponent<RectTransform>();
        rawRt.anchorMin = new Vector2(0.5f, 0.5f);
        rawRt.anchorMax = new Vector2(0.5f, 0.5f);
        rawRt.pivot = new Vector2(0.5f, 0.5f);
        rawRt.anchoredPosition = new Vector2(440, 0);
        rawRt.sizeDelta = new Vector2(320, 400);
        var rawImage = rawGo.AddComponent<RawImage>();
        vistaPrevia = new VistaPrevia3D(rawImage, "CamaraPreviewCrucetas", 320, 400);
    }


    public void AbrirVentana()
    {
        if (ventana != null) ventana.SetActive(true);
        ActualizarVistaPrevia();
    }
    void CerrarVentana()
    {
        if (ventana != null) ventana.SetActive(false);
        if (vistaPrevia != null) vistaPrevia.Ocultar();
    }

    /// <summary>Aplica el cambio de semicruceta y cierra la ventana.</summary>
    void AceptarCambios()
    {
        Aplicar();
        CerrarVentana();
    }

    void CerrarYVolver()
    {
        CerrarVentana();
        var gestor = FindAnyObjectByType<GestorAplicacionGemelo>();
        if (gestor != null) gestor.ReabrirMenuGemelo();
    }

    // ====================================================================
    // Seleccion desde el 3D: clic sobre una semicruceta
    // ====================================================================
    void Update()
    {
        if (!Input.GetMouseButtonDown(0)) return;
        // No seleccionar si el clic es sobre un elemento de la interfaz
        if (EventSystem.current != null
            && EventSystem.current.IsPointerOverGameObject()) return;

        var cam = FindAnyObjectByType<Camera>();
        if (cam == null) return;
        AsegurarColisionadoresCrucetas();
        Ray rayo = cam.ScreenPointToRay(Input.mousePosition);
        if (Physics.Raycast(rayo, out RaycastHit hit, 1000f))
        {
            int numero = NumeroApoyoDesde(hit.collider.transform);
            if (numero > 0) SeleccionarApoyoDesde3D(numero);
        }
    }

    /// <summary>Selecciona un apoyo y muestra la ventana (para el clic 3D).</summary>
    public void SeleccionarApoyoDesde3D(int numero)
    {
        if (numero < 1 || numero > totalApoyos) return;
        MostrarApoyo(numero);
        if (ventana != null && !ventana.activeSelf) ventana.SetActive(true);
    }

    /// <summary>Sube por la jerarquia hasta el apoyo 'Apoyo_N__...'.</summary>
    int NumeroApoyoDesde(Transform t)
    {
        while (t != null)
        {
            var m = System.Text.RegularExpressions.Regex.Match(
                t.name, @"^Apoyo_(\d+)__");
            if (m.Success) return int.Parse(m.Groups[1].Value);
            t = t.parent;
        }
        return -1;
    }

    /// <summary>
    /// Anade (si no existen) colliders a las piezas de cruceta de cada apoyo.
    /// Se identifican por nombre: se excluyen la cabeza y el fuste ('Cabeza'
    /// y 'Cuerpo_...'). Se llaman bajo demanda en el clic, asi funcionan
    /// tambien tras reconstruir la escena.
    /// </summary>
    void AsegurarColisionadoresCrucetas()
    {
        var generadores = FindObjectsByType<GeneradorDeLinea>(
            FindObjectsInactive.Exclude);
        foreach (var g in generadores)
        {
            if (g == null) continue;
            foreach (Transform apoyo in g.transform)
            {
                if (apoyo == null || !apoyo.name.StartsWith("Apoyo_")) continue;
                foreach (Transform pieza in apoyo)
                {
                    if (pieza == null) continue;
                    string nombre = pieza.name;
                    if (nombre == "Cabeza" || nombre.StartsWith("Cuerpo_"))
                        continue; // no es semicruceta (fuste/cabeza)
                    Bounds b = ObtenerLimites(pieza);
                    if (b.size.sqrMagnitude <= 0f) continue;
                    var bc = pieza.GetComponent<BoxCollider>();
                    if (bc == null) bc = pieza.gameObject.AddComponent<BoxCollider>();
                    AjustarBoxCollider(bc, b);
                }
            }
        }
    }

    static Bounds ObtenerLimites(Transform pieza)
    {
        Renderer[] renders = pieza.GetComponentsInChildren<Renderer>(true);
        if (renders.Length == 0) return new Bounds();
        Bounds b = renders[0].bounds;
        for (int i = 1; i < renders.Length; i++) b.Encapsulate(renders[i].bounds);
        return b;
    }

    static void AjustarBoxCollider(BoxCollider bc, Bounds mundo)
    {
        // Convierte los limites del mundo al espacio LOCAL de la pieza, de
        // modo que el collider sigue a la pieza aunque este rotada/escalada.
        Transform t = bc.transform;
        Vector3 min = Vector3.one * float.PositiveInfinity;
        Vector3 max = Vector3.one * float.NegativeInfinity;
        for (int i = 0; i < 8; i++)
        {
            Vector3 c = new Vector3(
                (i & 1) == 0 ? mundo.min.x : mundo.max.x,
                (i & 2) == 0 ? mundo.min.y : mundo.max.y,
                (i & 4) == 0 ? mundo.min.z : mundo.max.z);
            Vector3 local = t.InverseTransformPoint(c);
            min = Vector3.Min(min, local);
            max = Vector3.Max(max, local);
        }
        bc.center = (min + max) * 0.5f;
        bc.size = max - min;
    }


    // ====================================================================
    // Utilidades UI
    // ====================================================================
    static string TextoOpcion(OpcionCruceta o)
    {
        return o.referencia + "  |  " + o.longitud.ToString("0.00")
            + " m  |  " + (o.atirantada ? "ATIRANTADA" : "PLANA");
    }

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

    Button CrearBoton(GameObject padre, string nombre, string etiqueta,
                      Vector2 ancla, Vector2 pos, Vector2 tam,
                      UnityEngine.Events.UnityAction onClic)
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




