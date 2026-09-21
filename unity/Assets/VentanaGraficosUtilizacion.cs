using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections.Generic;
using System.IO;

/// <summary>
/// VentanaGraficosUtilizacion — Ventana con el grafico de utilizacion de cada apoyo.
/// =================================================================================
/// Al pulsar Play crea (sin setup manual) una ventana UI que muestra el PNG del
/// grafico de utilizacion del apoyo seleccionado.
///
/// Como abrirla:
///   - Haciendo clic sobre un apoyo 3D de la linea (los crea GeneradorDeLinea
///     con nombres "Apoyo_1__...", "Apoyo_2__...").
///   - Con el desplegable "Apoyo N" (abajo en la ventana).
///   - Con las teclas 1..9.
///
/// Los PNG se cargan de Resources/graficos_utilizacion/apoyo_N.png (generados
/// por generar_png_graficos.py). GENERAL: vale para cualquier linea.
/// </summary>
public class VentanaGraficosUtilizacion : MonoBehaviour
{
    [Header("Configuracion")]
    public string archivoJson = "Assets/graficos_utilizacion.json";
    public bool autoInstalarAlPlay = true;

    // UI
    private Canvas canvas;
    private GameObject ventana;
    private Image imagenGrafico;
    private Text tituloVentana;
    private Dropdown apoyoDropdown;

    // Datos
    private List<Dictionary<string, object>> apoyos = new List<Dictionary<string, object>>();
    private List<int> numerosApoyo = new List<int>();
    private int seleccionado = 1;
    private bool listo = false;
    private bool sincronizandoDropdown = false;
    private string error = "";

    /// <summary>
    /// Auto-instalacion: al pulsar Play crea la ventana si no existe ya.
    /// </summary>
    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaGraficosUtilizacion>() == null)
        {
            var go = new GameObject("VentanaGraficosUtilizacion");
            go.AddComponent<VentanaGraficosUtilizacion>();
        }
    }

    void Awake()
    {
        Inicializar();
    }

    void Inicializar()
    {
        try
        {
            CargarApoyos();
            CrearCanvasYEventSystem();
            CrearVentana();
            listo = true;
            ventana.SetActive(false);
            UnityEngine.Debug.Log("[VentanaGraficosUtilizacion] ventana creada con "
                + numerosApoyo.Count + " apoyos");
        }
        catch (Exception ex)
        {
            error = "Error: " + ex.Message;
            Debug.LogError(error);
        }
    }

    void CargarApoyos()
    {
        apoyos.Clear();
        numerosApoyo.Clear();
        error = "";
        string json = null;
        // Ruta robusta: primero la carpeta de datos activa (build), luego el
        // Assets del proyecto (editor) y por ultimo la ruta relativa legacy.
        string[] candidatos = new[]
        {
            Path.Combine(RutasGemelo.RutaAssetsGemelo(), "graficos_utilizacion.json"),
            Path.Combine(Application.dataPath, "graficos_utilizacion.json"),
            archivoJson,
        };
        foreach (string ruta in candidatos)
        {
            if (File.Exists(ruta))
            {
                json = File.ReadAllText(ruta, System.Text.Encoding.UTF8);
                break;
            }
        }
        if (json == null)
            error = "No se encontro graficos_utilizacion.json";

        var doc = json == null ? null
            : Json.Deserialize(json) as Dictionary<string, object>;
        if (doc != null && doc.ContainsKey("apoyos")
            && doc["apoyos"] is List<object> lista)
        {
            foreach (var item in lista)
            {
                var a = item as Dictionary<string, object>;
                if (a == null) continue;
                apoyos.Add(a);
                AgregarNumero(ParseNumero(a));
            }
            // Orden por numero SIEMPRE: el PNG y el titulo se correlacionan por
            // 'numero' (apoyo_N.png). Si el Excel de origen no viene ordenado,
            // aqui se corrige para que posicion y numero coincidan.
            apoyos.Sort((x, y) => ParseNumero(x).CompareTo(ParseNumero(y)));
        }

        // El JSON de graficos puede estar regenerandose o ser una copia antigua.
        // El desplegable debe representar la linea real, no solo los registros
        // que haya en ese archivo en un instante concreto.
        CargarNumerosDeLinea();
        CargarNumerosDesdeCoordenadas();
        CargarNumerosDeEscena();
        numerosApoyo.Sort();
    }

    void AgregarNumero(int numero)
    {
        if (numero > 0 && numero != int.MaxValue && !numerosApoyo.Contains(numero))
            numerosApoyo.Add(numero);
    }

    /// <summary>Completa la lista desde la configuracion maestra de apoyos. Se
    /// usa la primera copia disponible, respetando la linea activa.</summary>
    void CargarNumerosDeLinea()
    {
        string[] candidatos = new[]
        {
            Path.Combine(RutasGemelo.RutaAssetsGemelo(), "apoyos_configurados.json"),
            Path.Combine(Application.dataPath, "apoyos_configurados.json"),
        };

        foreach (string ruta in candidatos)
        {
            if (!File.Exists(ruta)) continue;
            try
            {
                var doc = Json.Deserialize(File.ReadAllText(ruta, System.Text.Encoding.UTF8))
                    as Dictionary<string, object>;
                if (doc != null && doc.ContainsKey("apoyos")
                    && doc["apoyos"] is List<object> lista)
                {
                    foreach (object item in lista)
                    {
                        var apoyo = item as Dictionary<string, object>;
                        AgregarNumero(ParseNumeroConfigurado(apoyo));
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning("No se pudo leer la lista completa de apoyos: " + ex.Message);
            }
            break;
        }
    }

    /// <summary>Las coordenadas son una segunda fuente general de la linea y
    /// permiten completar el desplegable si algun JSON estuviese incompleto.</summary>
    void CargarNumerosDesdeCoordenadas()
    {
        string[] candidatos = new[]
        {
            Path.Combine(RutasGemelo.RutaAssetsGemelo(), "coordenadas_linea.csv"),
            Path.Combine(Application.dataPath, "coordenadas_linea.csv"),
        };
        foreach (string ruta in candidatos)
        {
            if (!File.Exists(ruta)) continue;
            try
            {
                foreach (string linea in File.ReadAllLines(ruta))
                {
                    string primera = linea.Split(linea.Contains(";") ? ';' : ',')[0]
                        .Trim().Trim('\uFEFF', '"');
                    if (int.TryParse(primera, out int numero)) AgregarNumero(numero);
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning("No se pudieron leer las coordenadas de apoyos: "
                    + ex.Message);
            }
            break;
        }
    }

    /// <summary>Ultimo respaldo: incorpora los apoyos que realmente existen en
    /// la escena 3D, con nombres generales Apoyo_N__...</summary>
    void CargarNumerosDeEscena()
    {
        foreach (Transform t in FindObjectsByType<Transform>())
        {
            string nombre = t.name;
            if (!nombre.StartsWith("Apoyo_")) continue;
            string resto = nombre.Substring("Apoyo_".Length);
            int separador = resto.IndexOf('_');
            if (separador >= 0) resto = resto.Substring(0, separador);
            if (int.TryParse(resto, out int numero)) AgregarNumero(numero);
        }
    }

    private float ultimoClicGrafico = -999f;

    void Update()
    {
        if (!listo) return;
        // Con Alt pulsado la camara orbita (Alt+clic izq): no abrir la ventana.
        if (Input.GetKey(KeyCode.LeftAlt) || Input.GetKey(KeyCode.RightAlt)) return;
        // Clic sobre un apoyo 3D. El DOBLE clic es del nuevo centro de camara
        // (CamaraLinea), asi que aqui no se abre la ventana.
        if (Input.GetMouseButtonDown(0))
        {
            if (Time.time - ultimoClicGrafico < 0.3f)
            {
                ultimoClicGrafico = -999f;
            }
            else
            {
                ultimoClicGrafico = Time.time;
                int n = BuscarApoyoBajoCursor();
                if (n > 0) MostrarApoyo(n);
            }
        }
        // Teclado
        if (Input.GetKeyDown(KeyCode.Escape)) CerrarVentana();
        for (int k = 1; k <= 9; k++)
            if (Input.GetKeyDown(KeyCode.Alpha0 + k)) MostrarApoyo(k);
    }

    int BuscarApoyoBajoCursor()
    {
        if (Camera.main == null) return -1;
        Ray rayo = Camera.main.ScreenPointToRay(Input.mousePosition);
        RaycastHit hit;
        if (!Physics.Raycast(rayo, out hit)) return -1;
        Transform t = hit.collider.transform;
        while (t.parent != null) t = t.parent;
        // Nombre del tipo "Apoyo_3__SERIE_C_C2000"
        string nombre = t.name;
        if (nombre.StartsWith("Apoyo_"))
        {
            string resto = nombre.Substring("Apoyo_".Length);
            int sub = resto.IndexOf('_');
            if (sub > 0) resto = resto.Substring(0, sub);
            int n;
            if (int.TryParse(resto, out n)) return n;
        }
        return -1;
    }

    // Carga el PNG del grafico de utilizacion del apoyo N: primero desde la
    // carpeta de datos (Assets/Resources/graficos_utilizacion en el editor;
    // Datos/graficos_utilizacion en el .exe), y si no esta, desde Resources.
    Texture2D CargarGrafico(int n)
    {
        string nombre = "apoyo_" + n + ".png";
        string[] candidatos = new[]
        {
            Path.Combine(RutasGemelo.RutaGraficos(), nombre),
            Path.Combine(Application.dataPath, "Resources", "graficos_utilizacion", nombre),
        };
        foreach (string archivo in candidatos)
        {
            try
            {
                if (!File.Exists(archivo)) continue;
                byte[] bytes = File.ReadAllBytes(archivo);
                Texture2D tex = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (tex.LoadImage(bytes)) return tex;
                Destroy(tex);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("No se pudo cargar " + archivo + ": " + ex.Message);
            }
        }
        return Resources.Load<Texture2D>("graficos_utilizacion/apoyo_" + n);
    }

    void MostrarApoyo(int n)
    {
        if (numerosApoyo.Count > 0 && !numerosApoyo.Contains(n))
            n = numerosApoyo[Mathf.Clamp(IndiceApoyo(n), 0, numerosApoyo.Count - 1)];
        else if (n < 1)
            n = 1;
        seleccionado = n;
        sincronizandoDropdown = true;
        if (apoyoDropdown != null) apoyoDropdown.value = IndiceApoyo(n);
        sincronizandoDropdown = false;

        Texture2D tex = CargarGrafico(n);
        if (tex == null)
        {
            Debug.LogWarning("No se encontro el grafico de utilizacion del apoyo " + n + " (PNG).");
            if (imagenGrafico != null)
            {
                imagenGrafico.sprite = null;
                imagenGrafico.color = new Color(0.12f, 0.14f, 0.18f, 1f);
            }
            if (tituloVentana != null)
                tituloVentana.text = "Apoyo #" + n + "  -  grafico no disponible (PNG)";
            ventana.SetActive(true);
            return;
        }
        imagenGrafico.sprite = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height),
                                             new Vector2(0.5f, 0.5f));
        imagenGrafico.color = Color.white;
        imagenGrafico.preserveAspect = true;

        var a = BuscarApoyo(n);
        if (a == null)
        {
            if (tituloVentana != null)
                tituloVentana.text = "Apoyo #" + n
                    + "  -  sin datos en graficos_utilizacion.json";
            ventana.SetActive(true);
            return;
        }
        tituloVentana.text = string.Format("Apoyo #{0}  {1}  ({2})  Zona {3}  Montaje {4}",
            Obj(a, "numero"), Obj(a, "tipo"), Obj(a, "tipo_texto"),
            Obj(a, "zona"), Obj(a, "montaje"));
        ventana.SetActive(true);
    }

    void Siguiente() { MostrarApoyo(seleccionado + 1); }
    void Anterior() { MostrarApoyo(seleccionado - 1); }

    // ====================================================================
    // Creacion de la UI (Canvas + ventana + botones)
    // ====================================================================
    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystem");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        // Canvas propio SIEMPRE encima del canvas de la aplicacion (orden 1000).
        var goCanvas = new GameObject("CanvasGraficos");
        canvas = goCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 2000;
        goCanvas.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        goCanvas.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
        goCanvas.AddComponent<GraphicRaycaster>();
    }

    void CrearVentana()
    {
        var raiz = new GameObject("VentanaGrafico");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        // Fondo a pantalla completa. El grafico necesita conservar casi su
        // resolucion original para que la cabecera y la leyenda sean legibles.
        Image fondo = CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            Vector2.zero, Vector2.zero, new Color(0.08f, 0.1f, 0.16f, 0.98f));
        fondo.rectTransform.anchorMin = Vector2.zero;
        fondo.rectTransform.anchorMax = Vector2.one;
        fondo.rectTransform.offsetMin = Vector2.zero;
        fondo.rectTransform.offsetMax = Vector2.zero;

        // X visible arriba a la derecha para volver al menu de Graficos
        CrearBoton(raiz, "CerrarX", "X", Vector2.one,
            new Vector2(-28, -28), new Vector2(44, 44), CerrarYVolver);

        // Titulo
        tituloVentana = CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.925f),
            Vector2.zero, 24, TextAnchor.MiddleCenter);
        tituloVentana.rectTransform.sizeDelta = new Vector2(1100, 48);

        // Imagen grande y adaptable: deja franjas independientes para titulo y
        // controles, evitando que la informacion interna quede apelotonada.
        var goImg = CrearImagen(raiz, "Grafico", new Vector2(0.5f, 0.5f),
            Vector2.zero, Vector2.zero, Color.white);
        imagenGrafico = goImg.GetComponent<Image>();
        imagenGrafico.rectTransform.anchorMin = new Vector2(0.025f, 0.15f);
        imagenGrafico.rectTransform.anchorMax = new Vector2(0.975f, 0.84f);
        imagenGrafico.rectTransform.offsetMin = Vector2.zero;
        imagenGrafico.rectTransform.offsetMax = Vector2.zero;
        imagenGrafico.raycastTarget = false;
        imagenGrafico.preserveAspect = true;

        // Desplegable de APOYOS (sustituye a las flechas < >) + cerrar
        apoyoDropdown = UIFactory.CrearDropdown(raiz, "ApoyoDropdown",
            new Vector2(0.15f, 0.075f), Vector2.zero, new Vector2(190, 42));
        RellenarApoyos();
        apoyoDropdown.onValueChanged.AddListener(idx =>
        {
            if (sincronizandoDropdown) return;
            if (idx >= 0 && idx < numerosApoyo.Count)
                MostrarApoyo(numerosApoyo[idx]);
        });
        CrearBoton(raiz, "Cerrar", "CERRAR", new Vector2(0.85f, 0.075f),
            Vector2.zero, new Vector2(150, 46), CerrarVentana);
    }

    /// <summary>Rellena el desplegable con todos los numeros reales de la linea,
    /// aunque el JSON de graficos estuviese temporalmente incompleto.</summary>
    void RellenarApoyos()
    {
        if (apoyoDropdown == null) return;
        apoyoDropdown.options.Clear();
        for (int i = 0; i < numerosApoyo.Count; i++)
            apoyoDropdown.options.Add(new Dropdown.OptionData("Apoyo " + numerosApoyo[i]));
        sincronizandoDropdown = true;
        if (apoyoDropdown.options.Count > 0)
            apoyoDropdown.value = IndiceApoyo(seleccionado);
        apoyoDropdown.RefreshShownValue();
        sincronizandoDropdown = false;
    }

    /// <summary>Indice del numero real dentro del desplegable.</summary>
    int IndiceApoyo(int n)
    {
        for (int i = 0; i < numerosApoyo.Count; i++)
            if (numerosApoyo[i] == n) return i;
        return 0;
    }

    // ====================================================================
    // Utilidades UI
    // ====================================================================
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
        rt.sizeDelta = new Vector2(720, 40);
        var txt = go.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = tamano;
        txt.alignment = alineacion;
        txt.color = Color.white;
        txt.horizontalOverflow = HorizontalWrapMode.Wrap;
        txt.resizeTextForBestFit = true;
        txt.resizeTextMinSize = 12;
        txt.resizeTextMaxSize = tamano;
        return txt;
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
        txt.fontSize = 18;
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.text = etiqueta;
        txt.raycastTarget = false;
        return btn;
    }

    // ====================================================================
    // Utilidades de datos
    // ====================================================================
    static string Obj(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] != null) return d[clave].ToString();
        return "";
    }

    static int ParseNumero(Dictionary<string, object> d)
    {
        int n;
        if (d != null && int.TryParse(Obj(d, "numero"), out n)) return n;
        return int.MaxValue;
    }

    /// <summary>En apoyos_configurados.json el numero vive dentro del objeto
    /// "apoyo"; acepta tambien el formato plano del JSON de graficos.</summary>
    static int ParseNumeroConfigurado(Dictionary<string, object> d)
    {
        int numero = ParseNumero(d);
        if (numero != int.MaxValue) return numero;
        if (d != null && d.ContainsKey("apoyo")
            && d["apoyo"] is Dictionary<string, object> datosApoyo)
            return ParseNumero(datosApoyo);
        return int.MaxValue;
    }

    /// <summary>Devuelve el apoyo cuyo 'numero' es exactamente n. La imagen se
    /// carga como apoyo_N.png por numero; el titulo debe salir del MISMO apoyo,
    /// nunca de la posicion del array (que puede ir desordenada).</summary>
    Dictionary<string, object> BuscarApoyo(int n)
    {
        foreach (var item in apoyos)
            if (ParseNumero(item) == n) return item;
        return null;
    }

    public void AbrirVentana()
    {
        // Recarga los apoyos y el desplegable para reflejar la linea actual
        CargarApoyos();
        RellenarApoyos();
        if (ventana != null) MostrarApoyo(seleccionado);
    }
    void CerrarVentana() { if (ventana != null) ventana.SetActive(false); }

    void CerrarYVolver()
    {
        CerrarVentana();
        var gestor = FindAnyObjectByType<GestorAplicacionGemelo>();
        if (gestor != null) gestor.ReabrirMenuGraficos();
    }
}
