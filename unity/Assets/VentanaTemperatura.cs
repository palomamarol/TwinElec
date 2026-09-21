using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;

/// <summary>
/// VentanaTemperatura — Cambia la temperatura de calculo de los cables del
/// gemelo digital: la tension y la flecha de cada vano se recalculan al
/// instante en la escena 3D (el mismo "programa" de temperatura del scene
/// de Unity, ahora accesible desde el menu del gemelo digital).
/// ============================================================================
/// Al escribir la temperatura en la casilla y pulsar "APLICAR":
///   1. Se actualiza GeneradorDeLinea.temperaturaVisualizacion.
///   2. Se redibujan los cables con esa temperatura (misma fisica que usa el
///      resto del gemelo: cadenas, catenarias y arcos de amarre).
/// FUNCIONA CON CUALQUIER LINEA YA CARGADA en la escena.
/// </summary>
public class VentanaTemperatura : MonoBehaviour
{
    private Canvas canvas;
    private GameObject ventana;
    private Text valorTexto;
    private Text mensaje;
    private InputField campo;

    private float temperatura = 15f;

    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaTemperatura>() == null)
        {
            var go = new GameObject("VentanaTemperatura");
            go.AddComponent<VentanaTemperatura>();
        }
    }

    void Awake()
    {
        try
        {
            CrearCanvasYEventSystem();
            CrearVentana();
            // Partimos de la temperatura que tenga puesta la escena ahora mismo.
            var generador = FindAnyObjectByType<GeneradorDeLinea>();
            if (generador != null) temperatura = generador.temperaturaVisualizacion;
            if (campo != null) campo.text = TextoTemperatura();
            ActualizarEtiqueta();
            DontDestroyOnLoad(gameObject);
            UnityEngine.Debug.Log("[VentanaTemperatura] ventana creada");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaTemperatura: " + ex.Message);
        }
    }

    public void AbrirVentana()
    {
        if (ventana == null) return;
        var generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador != null)
        {
            temperatura = generador.temperaturaVisualizacion;
            if (campo != null) campo.text = TextoTemperatura();
        }
        ActualizarEtiqueta();
        ventana.SetActive(true);
    }

    void ActualizarEtiqueta()
    {
        if (valorTexto != null)
            valorTexto.text = "Temperatura: " + temperatura.ToString("0") + " °C";
    }

    string TextoTemperatura()
    {
        return temperatura.ToString("0",
            System.Globalization.CultureInfo.InvariantCulture);
    }

    void Aplicar()
    {
        float valor = temperatura;
        if (campo != null)
        {
            string texto = campo.text.Replace(',', '.');
            if (!float.TryParse(texto,
                System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out valor))
            {
                if (mensaje != null)
                {
                    mensaje.text = "Introduce una temperatura válida (ej. 15).";
                    mensaje.color = new Color(1f, 0.5f, 0.4f);
                }
                return;
            }
        }
        // SIN TOPE: se usa el mismo programa de tensiones de 'GeneradorDeLinea'
        // (RedibujarCablesPorTemperatura), que resuelve la ecuacion de cambio
        // de estado para CUALQUIER temperatura (no es una interpolacion).
        temperatura = valor;
        var generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador == null)
        {
            if (mensaje != null)
            {
                mensaje.text = "No hay una línea cargada en la escena.";
                mensaje.color = new Color(1f, 0.5f, 0.4f);
            }
            return;
        }
        generador.temperaturaVisualizacion = temperatura;
        try { generador.RedibujarCablesPorTemperatura(); }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogWarning("Redibujado por temperatura: " + ex.Message);
        }
        if (mensaje != null)
        {
            mensaje.text = "Cables recalculados a " + temperatura.ToString("0")
                + " °C (tensión y flecha actualizadas).";
            mensaje.color = new Color(0.4f, 1f, 0.5f);
        }
    }

    void CerrarVentana() { if (ventana != null) ventana.SetActive(false); }

    void CerrarYVolver()
    {
        CerrarVentana();
        var gestor = FindAnyObjectByType<GestorAplicacionGemelo>();
        if (gestor != null) gestor.ReabrirMenuGemelo();
    }

    // -----------------------------------------------------------------------
    // Creacion de la UI
    // -----------------------------------------------------------------------
    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemTemperatura");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var go = new GameObject("CanvasTemperatura");
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
        var raiz = new GameObject("VentanaTemperaturaUI");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(500, 400),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));
        // X visible arriba a la derecha para volver al menu de Gemelo digital
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(228, 178), new Vector2(40, 40), CerrarYVolver);

        CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 170), 22, TextAnchor.MiddleCenter).text =
            "TEMPERATURA DEL CONDUCTOR";

        CrearTexto(raiz, "Subtitulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 123), 13, TextAnchor.MiddleCenter).text =
            "La tensión de los cables y la flecha se recalculan con esta temperatura.";

        valorTexto = CrearTexto(raiz, "Valor", new Vector2(0.5f, 0.5f),
            new Vector2(0, 75), 20, TextAnchor.MiddleCenter);
        valorTexto.rectTransform.sizeDelta = new Vector2(460, 32);

        CrearTexto(raiz, "EtiquetaCampo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 35), 14, TextAnchor.MiddleCenter).text =
            "Temperatura (°C):";

        // Casilla de texto: se escribe la temperatura directamente (sin barra).
        campo = CrearCampo(raiz, "CampoTemp", new Vector2(0.5f, 0.5f),
            new Vector2(0, -2), new Vector2(160, 40));
        campo.characterValidation = InputField.CharacterValidation.None;
        campo.onValueChanged.AddListener(s =>
        {
            float v;
            if (float.TryParse(s.Replace(',', '.'),
                System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out v))
            {
                temperatura = v;
                ActualizarEtiqueta();
            }
        });

        CrearBoton(raiz, "Aplicar", "APLICAR", new Vector2(0.5f, 0.5f),
            new Vector2(0, -60), new Vector2(200, 50), Aplicar);

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -130), 14, TextAnchor.UpperCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(460, 110);
        mensaje.raycastTarget = false;

        CrearBoton(raiz, "Cerrar", "CERRAR", new Vector2(0.5f, 0.5f),
            new Vector2(175, -168), new Vector2(120, 40), CerrarVentana);
    }

    InputField CrearCampo(GameObject padre, string nombre, Vector2 ancla,
                          Vector2 pos, Vector2 tam)
    {
        var go = new GameObject(nombre);
        go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = ancla; rt.anchorMax = ancla; rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = pos; rt.sizeDelta = tam;

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
