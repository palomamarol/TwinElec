using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

/// <summary>
/// VentanaExportar — Exporta los archivos de trabajo de la linea (Excel editado
/// y/o archivo de coordenadas UTM) a la carpeta "Exportaciones" junto al Excel
/// original. Se abre desde la barra superior con el boton "Exportar archivos".
/// </summary>
public class VentanaExportar : MonoBehaviour
{
    private Canvas canvas;
    private GameObject ventana;
    private Toggle toggleExcel;
    private Toggle toggleCoordenadas;
    private Toggle togglePerfil;
    private Text mensaje;

    void Awake()
    {
        try
        {
            CrearCanvasYEventSystem();
            CrearVentana();
            DontDestroyOnLoad(gameObject);
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaExportar: " + ex.Message);
        }
    }

    public void AbrirVentana()
    {
        if (ventana != null) ventana.SetActive(true);
        if (mensaje != null) mensaje.text = "";
    }

    void CerrarVentana() { if (ventana != null) ventana.SetActive(false); }

    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystem");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var goCanvas = new GameObject("CanvasExportar");
        canvas = goCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 5000;
        goCanvas.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        goCanvas.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
        goCanvas.AddComponent<GraphicRaycaster>();
    }

    void CrearVentana()
    {
        var raiz = new GameObject("VentanaExportar");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(560, 400),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(258, 178), new Vector2(40, 40), CerrarVentana);

        CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 160), 24, TextAnchor.MiddleCenter).text = "EXPORTAR";

        // Casillas para elegir que se exporta
        toggleExcel = CrearToggle(raiz, "ToggleExcel",
            "Exportar el Excel de trabajo (*_editada.xlsx)",
            new Vector2(0.5f, 0.5f), new Vector2(0, 75), new Vector2(500, 50));
        toggleCoordenadas = CrearToggle(raiz, "ToggleCoordenadas",
            "Exportar el archivo de coordenadas (UTM)",
            new Vector2(0.5f, 0.5f), new Vector2(0, 15), new Vector2(500, 50));
        togglePerfil = CrearToggle(raiz, "TogglePerfil",
            "Exportar el PERFIL de la línea (PNG, últimos cambios)",
            new Vector2(0.5f, 0.5f), new Vector2(0, -45), new Vector2(500, 50));

        CrearBoton(raiz, "Exportar", "EXPORTAR", new Vector2(0.5f, 0.5f),
            new Vector2(0, -110), new Vector2(240, 50), Exportar);

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -180), 14, TextAnchor.UpperCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(520, 120);
        mensaje.raycastTarget = false;
    }

    void Exportar()
    {
        string carpetaTrabajo = RutasGemelo.RutaDatos();
        string destinoBase = GestorAplicacionGemelo.CarpetaExportacionActual;
        if (string.IsNullOrEmpty(destinoBase) || !Directory.Exists(destinoBase))
            destinoBase = carpetaTrabajo;
        string dir = Path.Combine(destinoBase, "Exportaciones");
        Directory.CreateDirectory(dir);
        string marca = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        var lineas = new List<string>();
        int exportados = 0;

        if (toggleExcel != null && toggleExcel.isOn)
        {
            string[] exceles = Directory.Exists(carpetaTrabajo)
                ? Directory.GetFiles(carpetaTrabajo, "*_editada.xlsx") : new string[0];
            if (exceles.Length > 0)
            {
                string origen = exceles.OrderByDescending(File.GetLastWriteTimeUtc).First();
                string destino = Path.Combine(dir, "TwinElec_Excel_" + marca + ".xlsx");
                File.Copy(origen, destino, true);
                exportados++;
                lineas.Add("Excel → " + Path.GetFileName(destino));
            }
            else lineas.Add("No hay Excel editado (*_editada.xlsx). Aplica antes un cambio.");
        }

        if (toggleCoordenadas != null && toggleCoordenadas.isOn)
        {
            string origen = null;
            string etiqueta = "Coordenadas";
            // 1) Documento UTM REGENERADO por el motor tras mover (tiene los cambios)
            string[] actualizados = Directory.Exists(carpetaTrabajo)
                ? Directory.GetFiles(carpetaTrabajo, "*UTM*actualizado*.doc*") : new string[0];
            if (actualizados.Length > 0)
            {
                origen = actualizados[0];
                etiqueta = "Coordenadas UTM (actualizado)";
            }
            else
            {
                // 2) json de coordenadas editadas
                string utmJson = Path.Combine(carpetaTrabajo, "utm_editado.json");
                if (File.Exists(utmJson))
                {
                    origen = utmJson;
                    etiqueta = "Coordenadas UTM (utm_editado.json)";
                }
                else
                {
                    // 3) documento UTM original (sin cambios aplicados)
                    string[] utm = Directory.Exists(carpetaTrabajo)
                        ? Directory.GetFiles(carpetaTrabajo, "*UTM*.doc*") : new string[0];
                    if (utm.Length > 0)
                    {
                        origen = utm[0];
                        etiqueta = "Coordenadas UTM (original)";
                    }
                }
            }
            if (origen != null)
            {
                string ext = Path.GetExtension(origen);
                string destino = Path.Combine(dir, "TwinElec_Coordenadas_" + marca + ext);
                File.Copy(origen, destino, true);
                exportados++;
                lineas.Add(etiqueta + " → " + Path.GetFileName(destino));
            }
            else lineas.Add("No se encontró el archivo de coordenadas (utm_editado.json o *UTM*.doc*).");
        }

        if (togglePerfil != null && togglePerfil.isOn)
        {
            var perfil = FindAnyObjectByType<VistaPerfilLinea>();
            if (perfil != null)
            {
                string destino = Path.Combine(dir, "TwinElec_Perfil_" + marca + ".png");
                try
                {
                    perfil.CapturarPNG(destino);
                    exportados++;
                    lineas.Add("Perfil de la línea (PNG) → " + Path.GetFileName(destino));
                }
                catch (Exception exP)
                {
                    lineas.Add("Perfil: no se pudo exportar (" + exP.Message + ").");
                }
            }
            else lineas.Add("Perfil: no hay línea cargada en la escena.");
        }

        mensaje.text = (exportados > 0 ? "✔ Exportación completada:\n" : "Nada exportado.\n")
            + string.Join("\n", lineas);
        mensaje.color = exportados > 0
            ? new Color(0.4f, 1f, 0.5f) : new Color(1f, 0.6f, 0.4f);
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
        txt.fontSize = 16;
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.text = etiqueta;
        txt.raycastTarget = false;
        return btn;
    }

    /// <summary>Crea una casilla de verificacion (Toggle) con su texto.</summary>
    Toggle CrearToggle(GameObject padre, string nombre, string etiqueta,
                       Vector2 ancla, Vector2 pos, Vector2 tam)
    {
        var go = new GameObject(nombre);
        go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = ancla; rt.anchorMax = ancla; rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = pos;
        rt.sizeDelta = tam;

        var fondo = go.AddComponent<Image>();
        fondo.color = new Color(0.15f, 0.22f, 0.34f, 1f);

        var toggle = go.AddComponent<Toggle>();
        toggle.targetGraphic = fondo;
        toggle.isOn = true;

        // Cuadrito de la casilla (a la izquierda)
        var caja = new GameObject("Caja");
        caja.transform.SetParent(go.transform, false);
        var crt = caja.AddComponent<RectTransform>();
        crt.anchorMin = new Vector2(0f, 0.5f); crt.anchorMax = new Vector2(0f, 0.5f);
        crt.pivot = new Vector2(0.5f, 0.5f);
        crt.sizeDelta = new Vector2(22, 22);
        crt.anchoredPosition = new Vector2(18, 0);
        var cimg = caja.AddComponent<Image>();
        cimg.color = new Color(0.3f, 0.42f, 0.58f, 1f);

        // Marca "✓" que se muestra cuando esta marcado
        var check = new GameObject("Check");
        check.transform.SetParent(caja.transform, false);
        var chrt = check.AddComponent<RectTransform>();
        chrt.anchorMin = Vector2.zero; chrt.anchorMax = Vector2.one;
        chrt.offsetMin = Vector2.zero; chrt.offsetMax = Vector2.zero;
        var chimg = check.AddComponent<Image>();
        chimg.sprite = UIFactory.CrearCheckmarkSprite();
        chimg.color = Color.white;
        chimg.raycastTarget = false;
        toggle.graphic = chimg;

        // Texto de la casilla
        var etq = new GameObject("Etiqueta");
        etq.transform.SetParent(go.transform, false);
        var ert = etq.AddComponent<RectTransform>();
        ert.anchorMin = new Vector2(0f, 0f); ert.anchorMax = new Vector2(1f, 1f);
        ert.offsetMin = new Vector2(50, 0); ert.offsetMax = new Vector2(-10, 0);
        var txt = etq.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = 14;
        txt.alignment = TextAnchor.MiddleLeft;
        txt.color = Color.white;
        txt.text = etiqueta;
        txt.horizontalOverflow = HorizontalWrapMode.Wrap;
        txt.verticalOverflow = VerticalWrapMode.Overflow;
        txt.raycastTarget = false;
        return toggle;
    }
}

