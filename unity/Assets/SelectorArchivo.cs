using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

/// <summary>
/// SelectorArchivo — Explorador de archivos integrado en la interfaz de Unity.
/// Funciona SIEMPRE en el .exe (no depende de los diálogos de Windows, que en
/// algunos equipos no aparecen delante de la ventana a pantalla completa).
/// Muestra las carpetas y los archivos del tipo pedido; clic en una carpeta
/// navega, clic en un archivo lo devuelve.
/// </summary>
public class SelectorArchivo : MonoBehaviour
{
    static SelectorArchivo _instancia;
    static Action<string> _alElegir;

    string _directorio;
    string _extension = "";
    List<string> _subcarpetas = new List<string>();
    List<string> _archivos = new List<string>();

    GameObject _ventana;
    Text _titulo;
    Text _ruta;
    Text _aviso;
    RectTransform _contenido;

    /// <summary>Abre el explorador. 'alElegir' recibe la ruta completa (o nada
    /// si se cancela).</summary>
    public static void Mostrar(string titulo, string directorioInicial,
                               string extension, Action<string> alElegir)
    {
        if (_instancia == null)
        {
            var go = new GameObject("SelectorArchivo");
            _instancia = go.AddComponent<SelectorArchivo>();
            DontDestroyOnLoad(go);
        }
        _alElegir = alElegir;
        _instancia.Abrir(titulo, directorioInicial, extension);
    }

    void Abrir(string titulo, string directorioInicial, string extension)
    {
        if (_ventana == null) CrearVentana();
        _titulo.text = titulo;
        _extension = extension ?? "";
        string dir = directorioInicial;
        if (!string.IsNullOrEmpty(dir) && File.Exists(dir)) dir = Path.GetDirectoryName(dir);
        if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir))
        {
            try { dir = Directory.GetCurrentDirectory(); } catch { }
        }
        if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir))
        {
            try { dir = Path.GetPathRoot(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)); }
            catch { }
        }
        _directorio = dir;
        _aviso.text = "";
        _ventana.SetActive(true);
        Recargar();
    }

    bool CoincideFiltro(string nombre)
    {
        if (_extension == "xlsx")
            return nombre.EndsWith(".xlsx", StringComparison.OrdinalIgnoreCase);
        if (_extension == "tif")
            return nombre.EndsWith(".tif", StringComparison.OrdinalIgnoreCase)
                || nombre.EndsWith(".tiff", StringComparison.OrdinalIgnoreCase);
        return nombre.EndsWith(".doc", StringComparison.OrdinalIgnoreCase)
            || nombre.EndsWith(".docx", StringComparison.OrdinalIgnoreCase);
    }

    void Recargar()
    {
        _subcarpetas.Clear();
        _archivos.Clear();
        try
        {
            foreach (string d in Directory.GetDirectories(_directorio))
            {
                try
                {
                    var info = new DirectoryInfo(d);
                    if ((info.Attributes & FileAttributes.Hidden) != 0) continue;
                    _subcarpetas.Add(info.Name);
                }
                catch { }
            }
            _subcarpetas.Sort(StringComparer.CurrentCultureIgnoreCase);
            foreach (string f in Directory.GetFiles(_directorio))
            {
                try
                {
                    var info = new FileInfo(f);
                    if ((info.Attributes & FileAttributes.Hidden) != 0) continue;
                    if (CoincideFiltro(info.Name)) _archivos.Add(info.Name);
                }
                catch { }
            }
            _archivos.Sort(StringComparer.CurrentCultureIgnoreCase);
            _ruta.text = _directorio;
            _aviso.text = (_archivos.Count == 0 && _subcarpetas.Count == 0)
                ? "Esta carpeta no tiene archivos " + (string.IsNullOrEmpty(_extension) ? "Word" : _extension)
                    + " visibles."
                : "";
        }
        catch (Exception ex)
        {
            _aviso.text = "No se pudo leer la carpeta: " + ex.Message;
        }
        Renderizar();
    }

    // -----------------------------------------------------------------------
    // Construccion de la ventana (UI de Unity)
    // -----------------------------------------------------------------------
    void CrearVentana()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemSelector");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var goCanvas = new GameObject("CanvasSelectorArchivo");
        var canvas = goCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 3000;
        goCanvas.AddComponent<CanvasScaler>().uiScaleMode =
            CanvasScaler.ScaleMode.ScaleWithScreenSize;
        goCanvas.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
        goCanvas.AddComponent<GraphicRaycaster>();
        DontDestroyOnLoad(goCanvas);

        var raiz = new GameObject("VentanaSelector");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        _ventana = raiz;

        // Fondo oscuro semi-transparente de toda la pantalla
        var fondoPantalla = new GameObject("FondoPantalla");
        fondoPantalla.transform.SetParent(raiz.transform, false);
        var frt = fondoPantalla.AddComponent<RectTransform>();
        frt.anchorMin = Vector2.zero; frt.anchorMax = Vector2.one;
        frt.offsetMin = Vector2.zero; frt.offsetMax = Vector2.zero;
        var fImg = fondoPantalla.AddComponent<Image>();
        fImg.color = new Color(0f, 0f, 0f, 0.45f);

        // Ventana principal
        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(720, 540),
            new Color(0.07f, 0.09f, 0.14f, 0.99f));

        _titulo = CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 245), 22, TextAnchor.MiddleCenter);

        _ruta = CrearTexto(raiz, "Ruta", new Vector2(0.5f, 0.5f),
            new Vector2(-50, 195), 14, TextAnchor.MiddleLeft);
        _ruta.rectTransform.sizeDelta = new Vector2(560, 30);
        _ruta.color = new Color(0.78f, 0.83f, 0.9f);

        CrearBoton(raiz, "Subir", "⬆ SUBIR", new Vector2(0.5f, 0.5f),
            new Vector2(285, 195), new Vector2(120, 32), Subir);

        // Lista desplazable
        var scrollGo = new GameObject("Lista");
        scrollGo.transform.SetParent(raiz.transform, false);
        var srt = scrollGo.AddComponent<RectTransform>();
        srt.anchorMin = new Vector2(0.5f, 0.5f);
        srt.anchorMax = new Vector2(0.5f, 0.5f);
        srt.pivot = new Vector2(0.5f, 0.5f);
        srt.anchoredPosition = new Vector2(0, -35);
        srt.sizeDelta = new Vector2(660, 330);
        scrollGo.AddComponent<Image>().color = new Color(0.1f, 0.12f, 0.18f, 1f);
        var scroll = scrollGo.AddComponent<ScrollRect>();
        scroll.horizontal = false;
        scroll.vertical = true;
        scroll.movementType = ScrollRect.MovementType.Clamped;
        scroll.scrollSensitivity = 30f;

        var viewport = new GameObject("Viewport");
        viewport.transform.SetParent(scrollGo.transform, false);
        var vrt = viewport.AddComponent<RectTransform>();
        vrt.anchorMin = Vector2.zero; vrt.anchorMax = Vector2.one;
        vrt.offsetMin = Vector2.zero; vrt.offsetMax = Vector2.zero;
        viewport.AddComponent<Image>().color = new Color(0.08f, 0.1f, 0.15f, 1f);
        viewport.AddComponent<Mask>().showMaskGraphic = false;
        scroll.viewport = vrt;

        _contenido = new GameObject("Contenido").AddComponent<RectTransform>();
        _contenido.SetParent(viewport.transform, false);
        _contenido.anchorMin = new Vector2(0, 1);
        _contenido.anchorMax = new Vector2(1, 1);
        _contenido.pivot = new Vector2(0.5f, 1f);
        _contenido.offsetMin = Vector2.zero;
        _contenido.offsetMax = Vector2.zero;
        var layout = _contenido.gameObject.AddComponent<VerticalLayoutGroup>();
        layout.childForceExpandWidth = true;
        layout.childControlHeight = true;
        layout.childForceExpandHeight = false;
        layout.spacing = 2f;
        layout.padding = new RectOffset(4, 4, 4, 4);
        var fit = _contenido.gameObject.AddComponent<ContentSizeFitter>();
        fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
        scroll.content = _contenido;

        // Barra de desplazamiento vertical
        var scrollbarGo = new GameObject("Scrollbar");
        scrollbarGo.transform.SetParent(scrollGo.transform, false);
        var sbrt = scrollbarGo.AddComponent<RectTransform>();
        sbrt.anchorMin = new Vector2(1, 0);
        sbrt.anchorMax = new Vector2(1, 1);
        sbrt.pivot = new Vector2(1, 0.5f);
        sbrt.offsetMin = new Vector2(-14, 2);
        sbrt.offsetMax = new Vector2(-2, -2);
        scrollbarGo.AddComponent<Image>().color = new Color(0.15f, 0.18f, 0.26f, 1f);
        var scrollbar = scrollbarGo.AddComponent<Scrollbar>();
        scrollbar.direction = Scrollbar.Direction.BottomToTop;
        var handleArea = new GameObject("Sliding Area");
        handleArea.transform.SetParent(scrollbarGo.transform, false);
        var hart = handleArea.AddComponent<RectTransform>();
        hart.anchorMin = Vector2.zero; hart.anchorMax = Vector2.one;
        hart.offsetMin = new Vector2(2, 2); hart.offsetMax = new Vector2(-2, -2);
        var handle = new GameObject("Handle");
        handle.transform.SetParent(handleArea.transform, false);
        var hrt = handle.AddComponent<RectTransform>();
        hrt.anchorMin = new Vector2(0, 0); hrt.anchorMax = new Vector2(1, 1);
        hrt.offsetMin = Vector2.zero; hrt.offsetMax = Vector2.zero;
        handle.AddComponent<Image>().color = new Color(0.42f, 0.52f, 0.68f, 1f);
        scrollbar.handleRect = hrt;
        scrollbar.targetGraphic = handle.GetComponent<Image>();
        scroll.verticalScrollbar = scrollbar;
        scroll.verticalScrollbarVisibility = ScrollRect.ScrollbarVisibility.AutoHide;

        _aviso = CrearTexto(raiz, "Aviso", new Vector2(0.5f, 0.5f),
            new Vector2(0, -240), 14, TextAnchor.MiddleCenter);
        _aviso.rectTransform.sizeDelta = new Vector2(620, 24);
        _aviso.color = new Color(1f, 0.7f, 0.4f);

        CrearBoton(raiz, "Cancelar", "CANCELAR", new Vector2(0.5f, 0.5f),
            new Vector2(250, -245), new Vector2(140, 44), Cancelar);

        _ventana.SetActive(false);
    }



    void Renderizar()
    {
        for (int i = _contenido.childCount - 1; i >= 0; i--)
            Destroy(_contenido.GetChild(i).gameObject);

        if (!string.IsNullOrEmpty(_directorio)
            && Directory.GetParent(_directorio) != null)
            CrearItem("..", true);
        foreach (string s in _subcarpetas) CrearItem(s, true);
        foreach (string a in _archivos) CrearItem(a, false);
    }

    void CrearItem(string nombre, bool esCarpeta)
    {
        var go = new GameObject(esCarpeta ? "Carpeta" : "Archivo");
        go.transform.SetParent(_contenido, false);
        var rt = go.AddComponent<RectTransform>();
        rt.sizeDelta = new Vector2(0, 34);
        // Sin LayoutElement el VerticalLayoutGroup les da altura 0 y no se ven.
        var elem = go.AddComponent<LayoutElement>();
        elem.minHeight = 34f;
        elem.preferredHeight = 34f;
        var img = go.AddComponent<Image>();
        img.color = esCarpeta ? new Color(0.18f, 0.22f, 0.33f, 1f)
                              : new Color(0.12f, 0.15f, 0.22f, 1f);
        var btn = go.AddComponent<Button>();
        btn.targetGraphic = img;
        UiBoton.AplicarEstilo(btn);

        var txtGo = new GameObject("Etiqueta");
        txtGo.transform.SetParent(go.transform, false);
        var trt = txtGo.AddComponent<RectTransform>();
        trt.anchorMin = Vector2.zero; trt.anchorMax = Vector2.one;
        trt.offsetMin = new Vector2(12, 0); trt.offsetMax = new Vector2(-12, 0);
        var txt = txtGo.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = 16;
        txt.alignment = TextAnchor.MiddleLeft;
        txt.color = Color.white;
        txt.text = (esCarpeta ? "📁 " : "📄 ") + nombre + (esCarpeta ? "/" : "");
        txt.raycastTarget = false;
        txt.horizontalOverflow = HorizontalWrapMode.Overflow;

        if (esCarpeta)
        {
            string destino = nombre == ".."
                ? Directory.GetParent(_directorio).FullName
                : Path.Combine(_directorio, nombre);
            btn.onClick.AddListener(() => { _directorio = destino; Recargar(); });
        }
        else
        {
            string rutaCompleta = Path.Combine(_directorio, nombre);
            btn.onClick.AddListener(() => Elegir(rutaCompleta));
        }
    }

    void Subir()
    {
        var padre = Directory.GetParent(_directorio);
        if (padre != null) { _directorio = padre.FullName; Recargar(); }
    }

    void Elegir(string ruta)
    {
        _ventana.SetActive(false);
        var cb = _alElegir;
        _alElegir = null;
        cb?.Invoke(ruta);
    }

    void Cancelar()
    {
        _ventana.SetActive(false);
        _alElegir = null;
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
