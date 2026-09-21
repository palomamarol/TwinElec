using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

/// <summary>
/// VentanaMoverApoyo — Mueve un apoyo escribiendo sus coordenadas UTM.
/// =====================================================================
/// Ventana con DOS GRADOS DE LIBERTAD: se eligen las dos coordenadas que se
/// escriben (X-Y, X-Z o Y-Z) y la tercera la calcula automaticamente el motor
/// a partir de la orografia PNOA.
///
/// Al pulsar "Aplicar":
///   1. Escribe una peticion JSON en la raiz del proyecto.
///   2. Llama a Python:  py mover_apoyo.py --peticion ... --resultado ...
///   3. Lee el resultado: si es un error (fuera del PNOA, sin dato, ...) lo
///      muestra en rojo como aviso/paron; si es OK actualiza el Excel de
///      trabajo (line_example_editada.xlsx) y el CSV de la línea.
///
/// GENERAL: funciona para cualquier linea/excel de la plantilla.
/// </summary>
public class VentanaMoverApoyo : MonoBehaviour
{
    // Rutas
    private string rutaPython = "";
    private string rutaUtm = "";
    private string rutaExcel = "";
    private string rutaSalidaExcel = "";
    private string nombreExcelTrabajo = "";

    // UI
    private Canvas canvas;
    private GameObject ventana;
    private Dropdown apoyoDropdown;
    private Text etiquetaCoordenadas;
    private InputField campo1;
    private InputField campo2;
    private Text mensaje;
    private Text antiguasCoordenadas;   // coords actuales del apoyo (solo lectura)
    private int seleccionado = 1;
    private int totalApoyos = 4;
    private string ejeAuto = "z";   // eje calculado por la orografia
    private bool sincronizandoDropdown = false;

    // Datos UTM actuales
    private List<Dictionary<string, object>> apoyosUtm = new List<Dictionary<string, object>>();

    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaMoverApoyo>() == null)
        {
            var go = new GameObject("VentanaMoverApoyo");
            go.AddComponent<VentanaMoverApoyo>();
        }
    }

    void Awake()
    {
        try
        {
            rutaPython = RutasGemelo.RutaDatos();   // raiz del TFG (editor) o Datos/ (build)
            string nombreExcel = BuscarExcelTrabajo();
            nombreExcelTrabajo = nombreExcel;
            rutaExcel = Path.Combine(rutaPython, nombreExcel + ".xlsx");
            rutaSalidaExcel = Path.Combine(rutaPython, nombreExcel + "_editada.xlsx");
            // Preferir el Excel de trabajo si ya existe (acumula movimientos)
            if (File.Exists(rutaSalidaExcel)) rutaExcel = rutaSalidaExcel;
            rutaUtm = BuscarRutaUtm(rutaPython, nombreExcel);
            CargarApoyosUtm();
            CrearCanvasYEventSystem();
            CrearVentana();
            MostrarApoyo(1);
            DontDestroyOnLoad(gameObject);
            UnityEngine.Debug.Log("[VentanaMoverApoyo] ventana creada con " + apoyosUtm.Count + " apoyos UTM");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaMoverApoyo: " + ex.Message);
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
    /// (RutaDatos) NO contiene los utm_*.json (PrepararCarpetaTrabajo solo copia
    /// el Excel y el documento UTM), por eso hay que buscarlos tambien en la
    /// base (raiz del TFG en editor, Datos/ en build). Se prefiere
    /// 'utm_editado.json' porque acumula los movimientos ya aplicados.</summary>
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

    void CargarApoyosUtm()
    {
        apoyosUtm.Clear();
        if (string.IsNullOrEmpty(rutaUtm) || !File.Exists(rutaUtm)) return;
        string json = File.ReadAllText(rutaUtm, System.Text.Encoding.UTF8);
        var doc = Json.Deserialize(json);
        if (doc is List<object> lista)
        {
            foreach (var item in lista)
            {
                if (item is Dictionary<string, object> d) apoyosUtm.Add(d);
            }
        }
        else if (doc is Dictionary<string, object> d2 && d2.ContainsKey("apoyos")
                 && d2["apoyos"] is List<object> l2)
        {
            foreach (var item in l2)
            {
                if (item is Dictionary<string, object> d) apoyosUtm.Add(d);
            }
        }
        if (apoyosUtm.Count > 0) totalApoyos = apoyosUtm.Count;
    }

    /// <summary>Tras un cambio (mover el apoyo o +/− modulos), las coordenadas
    /// ACTUALES ya no son las de antes: se relee la ruta UTM (prefiriendo
    /// 'utm_editado.json', que acumula los cambios) y se refrescan el letrero
    /// "Coordenadas actuales" y los campos de edicion.</summary>
    void RefrescarCoordenadasActuales()
    {
        try
        {
            rutaUtm = BuscarRutaUtm(rutaPython, nombreExcelTrabajo);
            CargarApoyosUtm();
            PrellenarCampos();
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogWarning("RefrescarCoordenadasActuales: " + ex.Message);
        }
    }

    float NumeroCoordenada(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] != null)
        {
            float v;
            if (float.TryParse(d[clave].ToString().Replace(',', '.'), System.Globalization.NumberStyles.Float,
                               System.Globalization.CultureInfo.InvariantCulture, out v)) return v;
        }
        return 0f;
    }

    float CampoA(InputField campo)
    {
        string texto = campo.text.Replace(',', '.');
        float v;
        if (float.TryParse(texto, System.Globalization.NumberStyles.Float,
                           System.Globalization.CultureInfo.InvariantCulture, out v)) return v;
        throw new FormatException("Introduce un numero valido.");
    }

    void MostrarApoyo(int n)
    {
        if (n < 1) n = 1;
        if (n > totalApoyos) n = totalApoyos;
        seleccionado = n;
        sincronizandoDropdown = true;
        if (apoyoDropdown != null) apoyoDropdown.value = n - 1;
        sincronizandoDropdown = false;
        PrellenarCampos();
        mensaje.text = "";
    }

    void PrellenarCampos()
    {
        Dictionary<string, object> a = null;
        if (seleccionado - 1 < apoyosUtm.Count) a = apoyosUtm[seleccionado - 1];
        float x = NumeroCoordenada(a, "x");
        float y = NumeroCoordenada(a, "y");
        float z = NumeroCoordenada(a, "cota");
        if (ejeAuto == "z") { campo1.text = x.ToString("F2"); campo2.text = y.ToString("F2"); }
        else if (ejeAuto == "x") { campo1.text = y.ToString("F2"); campo2.text = z.ToString("F2"); }
        else { campo1.text = x.ToString("F2"); campo2.text = z.ToString("F2"); }
        // Coordenadas antiguas como referencia fija (no editables)
        if (antiguasCoordenadas != null)
        {
            antiguasCoordenadas.text = "Coordenadas actuales:  X = " + x.ToString("F2")
                + "   Y = " + y.ToString("F2") + "   Z = " + z.ToString("F2");
        }
        ActualizarEtiquetas();
    }

    void ActualizarEtiquetas()
    {
        if (ejeAuto == "z")
        {
            etiquetaCoordenadas.text = "Introduce X (este) e Y (norte).\nLa cota Z se calcula automatica de la orografia.";
        }
        else if (ejeAuto == "x")
        {
            etiquetaCoordenadas.text = "Introduce Y (norte) y Z (cota).\nLa X se calcula automatica de la orografia.";
        }
        else
        {
            etiquetaCoordenadas.text = "Introduce X (este) y Z (cota).\nLa Y se calcula automatica de la orografia.";
        }
    }

    void CambiarEje(string eje)
    {
        ejeAuto = eje;
        PrellenarCampos();
        mensaje.text = "";
    }

    void Aplicar()
    {
        try
        {
            mensaje.text = "Procesando...";
            mensaje.color = Color.yellow;
            float c1 = CampoA(campo1);
            float c2 = CampoA(campo2);
            string json = ConstruirPeticion(c1, c2);
            string rutaPeticion = Path.Combine(rutaPython, "peticion_mover.json");
            string rutaResultado = Path.Combine(rutaPython, "resultado_mover.json");
            File.WriteAllText(rutaPeticion, json, Json.Utf8SinBom);

            MotorHelper.EjecutarMotor("mover_apoyo",
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
                var pos = doc["posicion"] as Dictionary<string, object>;
                string resumen = "APOYO " + seleccionado + " MOVIDO\n";
                if (pos != null)
                {
                    resumen += "X = " + pos["x"] + "\nY = " + pos["y"] + "\nZ (cota) = " + pos["cota"] + "\n";
                }
                resumen += "Excel de trabajo actualizado y CSV de la linea regenerado.";
                mensaje.text = resumen;
                mensaje.color = new Color(0.4f, 1f, 0.5f);
                AvisarRecarga();
                RefrescarCoordenadasActuales();
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

    void AplicarModulos(int delta)
    {
        try
        {
            mensaje.text = "Procesando modulos...";
            mensaje.color = Color.yellow;
            string json = "{\n"
                + "  \"excel\": \"" + Json.Esc(rutaExcel) + "\",\n"
                + "  \"utm\": \"" + Json.Esc(rutaUtm) + "\",\n"
                + "  \"salida_excel\": \"" + Json.Esc(rutaSalidaExcel) + "\",\n"
                + "  \"apoyo\": " + seleccionado + ",\n"
                + "  \"modulos\": " + delta + "\n"
                + "}";
            string rutaPeticion = Path.Combine(rutaPython, "peticion_modulos.json");
            string rutaResultado = Path.Combine(rutaPython, "resultado_modulos.json");
            File.WriteAllText(rutaPeticion, json, Json.Utf8SinBom);

            string salidaMotor = MotorHelper.EjecutarMotor("modulos_fuste",
                "--peticion \"" + rutaPeticion + "\""
                + " --resultado \"" + rutaResultado + "\"");

            if (!File.Exists(rutaResultado))
            {
                string detalle = "Python no genero resultado. Revisa que 'py' este en el PATH.";
                if (!string.IsNullOrWhiteSpace(salidaMotor))
                {
                    string ultima = salidaMotor.Trim();
                    int corte = ultima.Length > 300 ? ultima.Length - 300 : 0;
                    detalle = "El motor no escribio resultado. Ultima salida del motor:\n"
                        + ultima.Substring(corte);
                }
                throw new Exception(detalle);
            }
            string texto = File.ReadAllText(rutaResultado, System.Text.Encoding.UTF8);
            var doc = Json.Deserialize(texto) as Dictionary<string, object>;
            bool ok = doc != null && doc.ContainsKey("ok") && doc["ok"] is bool b && b;
            if (ok && doc != null)
            {
                string resumen = "APOYO " + seleccionado + ": " + (delta > 0 ? "+" : "") + delta + " MODULO\n";
                if (doc.ContainsKey("altura_total_antes") && doc.ContainsKey("altura_total_despues"))
                {
                    resumen += "Altura total: " + doc["altura_total_antes"]
                        + " -> " + doc["altura_total_despues"] + " m\n";
                }
                if (doc.ContainsKey("cota_utm_antes") && doc.ContainsKey("cota_utm_despues")
                    && doc["cota_utm_antes"] != null && doc["cota_utm_despues"] != null)
                {
                    resumen += "Cota UTM: " + doc["cota_utm_antes"]
                        + " -> " + doc["cota_utm_despues"] + " m\n";
                }
                resumen += "Excel actualizado: desniveles y tensiones recalculados.";
                if (doc.ContainsKey("aviso_utm")
                    && doc["aviso_utm"] is string avisoUtm
                    && !string.IsNullOrEmpty(avisoUtm))
                {
                    resumen += "\n(aviso UTM: " + avisoUtm + ")";
                }
                mensaje.text = resumen;
                mensaje.color = new Color(0.4f, 1f, 0.5f);
                AvisarRecarga();
                RefrescarCoordenadasActuales();
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

    /// <summary>Aplica los cambios de posicion y cierra la ventana.</summary>
    void AceptarCambios()
    {
        Aplicar();
        CerrarVentana();
    }

    string ConstruirPeticion(float c1, float c2)
    {
        var inv = System.Globalization.CultureInfo.InvariantCulture;
        string x = "null", y = "null", z = "null";
        if (ejeAuto == "z") { x = c1.ToString("F2", inv); y = c2.ToString("F2", inv); }
        else if (ejeAuto == "x") { y = c1.ToString("F2", inv); z = c2.ToString("F2", inv); }
        else { x = c1.ToString("F2", inv); z = c2.ToString("F2", inv); }
        return "{\n"
            + "  \"excel\": \"" + Json.Esc(rutaExcel) + "\",\n"
            + "  \"utm\": \"" + Json.Esc(rutaUtm) + "\",\n"
            + "  \"salida_excel\": \"" + Json.Esc(rutaSalidaExcel) + "\",\n"
            + "  \"apoyo\": " + seleccionado + ",\n"
            + "  \"x\": " + x + ",\n"
            + "  \"y\": " + y + ",\n"
            + "  \"z\": " + z + ",\n"
            + "  \"eje_auto\": \"" + ejeAuto + "\"\n"
            + "}";
    }

    void AvisarRecarga()
    {
        // Regenera la linea 3D desde el CSV actualizado (el apoyo se mueve
        // en la escena y los cables se recalculan).
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
            var es = new GameObject("EventSystemMover");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        // Canvas propio SIEMPRE encima del canvas de la aplicacion (orden 1000)
        var go = new GameObject("CanvasMover");
        canvas = go.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 2000;
        go.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        go.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
        go.AddComponent<GraphicRaycaster>();
    }

    void CrearVentana()
    {
        var raiz = new GameObject("VentanaMover");
        raiz.transform.SetParent(canvas.transform, false);
        // El raiz necesita un RectTransform que ocupe el canvas: sin el, los
        // hijos (RectTransform) se anclan a un padre sin rect y el layout se
        // colapsa (era la causa del panel "vacio" con solo un cuadrado azul).
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 0), new Vector2(460, 560),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));

        // Desplegable de APOYOS (sustituye a las flechas < > y al titulo)
        apoyoDropdown = UIFactory.CrearDropdown(raiz, "ApoyoDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, 200), new Vector2(240, 36));
        for (int i = 1; i <= totalApoyos; i++)
            apoyoDropdown.options.Add(new Dropdown.OptionData("Apoyo " + i));
        apoyoDropdown.value = seleccionado - 1;
        apoyoDropdown.onValueChanged.AddListener(idx =>
        {
            if (!sincronizandoDropdown) MostrarApoyo(idx + 1);
        });

        CrearBoton(raiz, "EjeZ", "Z auto (X,Y)", new Vector2(0.5f, 0.5f),
            new Vector2(-140, 150), new Vector2(120, 42), () => CambiarEje("z"));
        CrearBoton(raiz, "EjeX", "X auto (Y,Z)", new Vector2(0.5f, 0.5f),
            new Vector2(0, 150), new Vector2(120, 42), () => CambiarEje("x"));
        CrearBoton(raiz, "EjeY", "Y auto (X,Z)", new Vector2(0.5f, 0.5f),
            new Vector2(140, 150), new Vector2(120, 42), () => CambiarEje("y"));

        etiquetaCoordenadas = CrearTexto(raiz, "Etiqueta", new Vector2(0.5f, 0.5f),
            new Vector2(0, 88), 15, TextAnchor.MiddleCenter);

        campo1 = CrearCampo(raiz, "Campo1", new Vector2(0.5f, 0.5f),
            new Vector2(-110, 30), new Vector2(180, 42));
        campo2 = CrearCampo(raiz, "Campo2", new Vector2(0.5f, 0.5f),
            new Vector2(110, 30), new Vector2(180, 42));

        // Coordenadas ANTIGUAS del apoyo (fijas, solo como referencia)
        antiguasCoordenadas = CrearTexto(raiz, "Antiguas", new Vector2(0.5f, 0.5f),
            new Vector2(0, -25), 14, TextAnchor.MiddleCenter);
        antiguasCoordenadas.rectTransform.sizeDelta = new Vector2(440, 24);
        antiguasCoordenadas.color = new Color(1f, 0.85f, 0.4f);

        CrearBoton(raiz, "Aplicar", "APLICAR", new Vector2(0.5f, 0.5f),
            new Vector2(0, -70), new Vector2(180, 50), Aplicar);

        // Modulos del fuste: anadir/quitar celdas ENTERAS (0,6 m en Serie C)
        CrearBoton(raiz, "ModuloMas", "+1 MOD", new Vector2(0.5f, 0.5f),
            new Vector2(-95, -120), new Vector2(90, 38), () => AplicarModulos(1));
        CrearBoton(raiz, "ModuloMenos", "-1 MOD", new Vector2(0.5f, 0.5f),
            new Vector2(95, -120), new Vector2(90, 38), () => AplicarModulos(-1));

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -215), 15, TextAnchor.UpperCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(420, 140);
        mensaje.raycastTarget = false; // no bloquea los botones de modulos

        CrearBoton(raiz, "Aceptar", "ACEPTAR", new Vector2(0.5f, 0.5f),
            new Vector2(170, -245), new Vector2(120, 40), AceptarCambios);

        // X visible arriba a la derecha para volver al menu de Gemelo digital
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(208, 258), new Vector2(40, 40), CerrarYVolver);
    }

    public void AbrirVentana() { if (ventana != null) ventana.SetActive(true); }
    void CerrarVentana() { if (ventana != null) ventana.SetActive(false); }

    void CerrarYVolver()
    {
        CerrarVentana();
        var gestor = FindAnyObjectByType<GestorAplicacionGemelo>();
        if (gestor != null) gestor.ReabrirMenuGemelo();
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
        txt.fontSize = 16;
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.text = etiqueta;
        txt.raycastTarget = false;
        return btn;
    }
}
