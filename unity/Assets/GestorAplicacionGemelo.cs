using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

/// <summary>Pantalla de entrada, gemelo 3D y herramientas de TwinElec.</summary>
public class GestorAplicacionGemelo : MonoBehaviour
{
    Canvas canvas;
    GameObject inicio, barra, ayudaCamara;
    GameObject menuGemelo, menuGraficos, menuDlr;
    Text textoDlr;
    Text etiquetaTerreno;
    float siguienteRefrescoDlr;
    Text rutaExcelTexto, rutaUtmTexto, rutaCuadrosTexto, rutaMdtTexto, rutaOrtoTexto, estado;
    string excelSeleccionado = "", utmSeleccionado = "", cuadrosSeleccionado = "";
    string ortoSeleccionado = "", carpetaTrabajo = "";
    static string carpetaExportacion = "";
    /// <summary>Carpeta destino de las exportaciones (junto al Excel original).</summary>
    public static string CarpetaExportacionActual => carpetaExportacion;
    readonly List<string> mdtSeleccionados = new List<string>();
    GeneradorDeLinea generador;
    InterfaceDLR hud;
    GameObject panelVistaPerfil;
    RawImage imagenVistaPerfil;
    Text textoVacioPerfil;
    VistaPerfilLinea perfilLinea;
    bool vistaPerfilVisible;
    Button botonVistaPerfil;
    Text textoBotonVistaPerfil;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    static void Instalar()
    {
        if (FindAnyObjectByType<GestorAplicacionGemelo>() != null) return;
        var go = new GameObject("GestorAplicacionGemelo");
        DontDestroyOnLoad(go);
        go.AddComponent<GestorAplicacionGemelo>();
    }

    void Awake()
    {
        SceneManager.sceneLoaded += AlCargarEscena;
        AutodetectarDatosActuales();
        CrearInterfaz();
        ActualizarResumen();
    }

    void OnDestroy() { SceneManager.sceneLoaded -= AlCargarEscena; }

    void AlCargarEscena(Scene escena, LoadSceneMode modo)
    {
        generador = FindAnyObjectByType<GeneradorDeLinea>();
        hud = FindAnyObjectByType<InterfaceDLR>();
        if (generador != null) generador.construirAlIniciar = false;
        if (hud != null) hud.mostrarHUD = false;
    }

    void AutodetectarDatosActuales()
    {
        string baseDatos = RutasGemelo.RutaDatosBase();
        if (!Directory.Exists(baseDatos)) return;
        excelSeleccionado = Primero(baseDatos, "*.xlsx", p =>
            !Path.GetFileName(p).StartsWith("~$") &&
            !p.EndsWith("_editada.xlsx", StringComparison.OrdinalIgnoreCase));
        utmSeleccionado = Primero(baseDatos, "*UTM*.doc*");
        cuadrosSeleccionado = Primero(baseDatos, "*Cuadros*.doc*");
        ortoSeleccionado = Primero(baseDatos, "PNOA_MA*.tif");
        mdtSeleccionados.AddRange(Directory.GetFiles(baseDatos, "PNOA_MDT05*.tif"));
        if (!string.IsNullOrEmpty(excelSeleccionado))
            carpetaExportacion = Path.GetDirectoryName(excelSeleccionado);
    }

    string Primero(string carpeta, string patron, Func<string, bool> filtro = null)
    {
        return Directory.GetFiles(carpeta, patron).FirstOrDefault(p => filtro == null || filtro(p)) ?? "";
    }

    void CrearInterfaz()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemAplicacion");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
            DontDestroyOnLoad(es);
        }
        var goCanvas = new GameObject("CanvasAplicacion");
        goCanvas.transform.SetParent(transform, false);
        canvas = goCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 1000;
        var scaler = goCanvas.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1600, 900);
        scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
        scaler.matchWidthOrHeight = .5f;
        goCanvas.AddComponent<GraphicRaycaster>();
        CrearPantallaInicio();
        CrearBarra();
        CrearAyudaCamara();
        CrearMenusAplicacion();
        CrearVistaPerfil();
        barra.transform.SetAsLastSibling(); // la barra superior queda por encima del perfil
    }

    void Update()
    {
        if (menuDlr != null && menuDlr.activeSelf && Time.unscaledTime >= siguienteRefrescoDlr)
        {
            siguienteRefrescoDlr = Time.unscaledTime + 1f;
            RefrescarTextoDlr();
        }
    }

    void CrearPantallaInicio()
    {
        inicio = Panel(canvas.gameObject, "PantallaInicio", Vector2.zero, Vector2.one,
            Vector2.zero, Vector2.zero, new Color(.012f, .016f, .025f, 1f));
        var tarjeta = Panel(inicio, "Tarjeta", new Vector2(.5f, .5f), new Vector2(.5f, .5f),
            Vector2.zero, new Vector2(1120, 800), new Color(.048f, .056f, .075f, 1f));
        Texto(tarjeta, "TwinElec", 36, FontStyle.Bold, TextAnchor.MiddleCenter,
            new Vector2(0, 350), new Vector2(1000, 52));
        Texto(tarjeta, "NUEVO GEMELO DIGITAL · ARCHIVOS DE ENTRADA", 15, FontStyle.Bold,
            TextAnchor.MiddleCenter, new Vector2(0, 310), new Vector2(1000, 28), new Color(.35f, .72f, 1f));
        Texto(tarjeta,
            "Necesarios: Excel de cálculo de Andelec · coordenadas UTM · archivo de Cuadros · " +
            "PNOA MDT (elevaciones) · PNOA MA (ortofoto).\n" +
            "TwinElec añade automáticamente los catálogos internos de conductores, apoyos y cadenas.",
            16, FontStyle.Normal, TextAnchor.MiddleCenter, new Vector2(0, 250),
            new Vector2(1000, 70), new Color(.78f, .82f, .88f));

        rutaExcelTexto = FilaEntrada(tarjeta, "EXCEL ANDELEC", "Libro .xlsx original de la línea",
            155, "SELECCIONAR", () => SeleccionarSimple(TipoEntrada.Excel));
        rutaUtmTexto = FilaEntrada(tarjeta, "COORDENADAS UTM", "Documento .doc o .docx con los apoyos",
            80, "SELECCIONAR", () => SeleccionarSimple(TipoEntrada.Utm));
        rutaCuadrosTexto = FilaEntrada(tarjeta, "ARCHIVO CUADROS", "Documento de cuadros y cadenas",
            5, "SELECCIONAR", () => SeleccionarSimple(TipoEntrada.Cuadros));
        rutaMdtTexto = FilaEntrada(tarjeta, "PNOA MDT", "Pulsa varias veces para añadir varios TIFF",
            -70, "AÑADIR TIFF", SeleccionarMdt);
        rutaOrtoTexto = FilaEntrada(tarjeta, "PNOA ORTOFOTO", "TIFF PNOA_MA con la imagen aérea",
            -145, "SELECCIONAR", () => SeleccionarSimple(TipoEntrada.Ortofoto));

        Boton(tarjeta, "LIMPIAR PNOA MDT", new Vector2(-340, -230), new Vector2(220, 42),
            () => { mdtSeleccionados.Clear(); ActualizarResumen(); });
        Boton(tarjeta, "CARGAR Y CREAR LÍNEA", new Vector2(135, -230), new Vector2(430, 52),
            () => StartCoroutine(CargarLinea()));
        estado = Texto(tarjeta, "", 15, FontStyle.Normal, TextAnchor.MiddleCenter,
            new Vector2(0, -315), new Vector2(1000, 80), new Color(.95f, .72f, .3f));
    }

    Text FilaEntrada(GameObject tarjeta, string titulo, string ayuda, float y,
        string textoBoton, Action accion)
    {
        var fila = Panel(tarjeta, "Fila_" + titulo, new Vector2(.5f, .5f), new Vector2(.5f, .5f),
            new Vector2(0, y), new Vector2(1000, 64), new Color(.075f, .086f, .11f, 1f));
        Texto(fila, titulo, 15, FontStyle.Bold, TextAnchor.MiddleLeft,
            new Vector2(25, 12), new Vector2(220, 24), new Color(.55f, .78f, 1f), new Vector2(0, .5f));
        Texto(fila, ayuda, 12, FontStyle.Normal, TextAnchor.MiddleLeft,
            new Vector2(25, -13), new Vector2(250, 22), new Color(.55f, .59f, .66f), new Vector2(0, .5f));
        Text valor = Texto(fila, "No seleccionado", 14, FontStyle.Normal, TextAnchor.MiddleLeft,
            new Vector2(285, 0), new Vector2(500, 52), new Color(.82f, .85f, .9f), new Vector2(0, .5f));
        valor.horizontalOverflow = HorizontalWrapMode.Wrap;
        valor.verticalOverflow = VerticalWrapMode.Truncate;
        Boton(fila, textoBoton, new Vector2(390, 0), new Vector2(180, 40), accion);
        return valor;
    }

    void CrearBarra()
    {
        barra = Panel(canvas.gameObject, "BarraSuperior", new Vector2(0, 1), new Vector2(1, 1),
            new Vector2(0, -30), new Vector2(0, 60), new Color(.035f, .045f, .065f, .97f));
        barra.SetActive(false);
        Texto(barra, "TwinElec", 22, FontStyle.Bold, TextAnchor.MiddleLeft,
            new Vector2(25, 0), new Vector2(180, 60), Color.white, new Vector2(0, .5f));
        Boton(barra, "Proyecto", new Vector2(210, 0), new Vector2(120, 38), VolverAInicio, new Vector2(0, .5f));
        Boton(barra, "Gemelo digital", new Vector2(345, 0), new Vector2(210, 38),
            () => MostrarMenu(menuGemelo), new Vector2(0, .5f));
        Boton(barra, "Gráficos de utilización", new Vector2(570, 0), new Vector2(240, 38),
            () => MostrarMenu(menuGraficos), new Vector2(0, .5f));
        Boton(barra, "Datos DLR", new Vector2(825, 0), new Vector2(160, 38),
            () => MostrarMenu(menuDlr), new Vector2(0, .5f));
        Boton(barra, "Exportar archivos", new Vector2(1000, 0), new Vector2(180, 38),
            () => Abrir<VentanaExportar>(), new Vector2(0, .5f));
        // Conmutar el terreno y la elevacion (ver la linea "flotando").
        var btnTerreno = Boton(barra, "OCULTAR TERRENO", new Vector2(1175, 0), new Vector2(130, 38),
            AlternarTerrenoBtn, new Vector2(0, .5f));
        etiquetaTerreno = btnTerreno.transform.Find("Etiqueta").GetComponent<Text>();
        botonVistaPerfil = Boton(barra, "Vista perfil", new Vector2(1320, 0), new Vector2(150, 38),
            MostrarVistaPerfil, new Vector2(0, .5f));
        textoBotonVistaPerfil = botonVistaPerfil.transform.Find("Etiqueta").GetComponent<Text>();
        ActualizarPestanaVistaPerfil();
    }

    void AlternarTerrenoBtn()
    {
        var camara = FindAnyObjectByType<CamaraLinea>();
        if (camara == null) return;
        bool visible = camara.AlternarTerreno();
        if (etiquetaTerreno != null)
            etiquetaTerreno.text = visible ? "OCULTAR TERRENO" : "VER TERRENO";
    }

    void CrearAyudaCamara()
    {
        ayudaCamara = Panel(canvas.gameObject, "AyudaCamara", Vector2.zero, Vector2.zero,
            new Vector2(260, 52), new Vector2(760, 64), new Color(.025f, .035f, .052f, .88f));
        Texto(ayudaCamara,
            "ORBITA: botón der. o Alt+clic izq  ·  PAN: botón central  ·  ZOOM: rueda (hacia el cursor)  ·  "
            + "DOBLE CLIC: nuevo centro  ·  F: enfocar apoyo  ·  INICIO: encuadrar línea  ·  Botón der.+WASD: vuelo",
            13, FontStyle.Normal, TextAnchor.MiddleCenter, Vector2.zero,
            new Vector2(730, 52), new Color(.83f, .87f, .92f));
        ayudaCamara.SetActive(false);
    }

    void CrearMenusAplicacion()
    {
        menuGemelo = CrearPanelLateral("MenuGemeloDigital", "GEMELO DIGITAL",
            "Modifica la geometría y la configuración eléctrica de la línea.");
        AccionMenu(menuGemelo, "Mover apoyo y altura",
            "Cambia dos coordenadas UTM; la cota se obtiene del PNOA. Añade o quita módulos del fuste.",
            236, () => Abrir<VentanaMoverApoyo>());
        AccionMenu(menuGemelo, "Tipo, gama y montaje",
            "Selecciona familia de apoyo, tresbolillo/bandera/bóveda y detalle constructivo.",
            150, () => Abrir<VentanaTipoApoyo>());
        AccionMenu(menuGemelo, "Crucetas",
            "Cambia longitud, referencia y configuración plana o atirantada.",
            64, () => Abrir<VentanaCrucetas>());
        AccionMenu(menuGemelo, "Cadenas y conductor",
            "Configura aisladores, material, cadena simple/doble y conductor de la línea.",
            -22, () => Abrir<VentanaCadenaConductor>());
        AccionMenu(menuGemelo, "Ángulos de los apoyos",
            "Edita la orientación de un apoyo y reconstruye cables y amarres.",
            -108, () => Abrir<VentanaAngulo>());
        AccionMenu(menuGemelo, "Tensiones y flechas",
            "Consulta y modifica las condiciones mecánicas por tramo y conductor.",
            -194, () => Abrir<VentanaTensiones>());
        AccionMenu(menuGemelo, "Temperatura del conductor",
            "Cambia la temperatura de cálculo: la tensión y la flecha de los cables se recalculan en la escena.",
            -280, () => Abrir<VentanaTemperatura>());
        menuGemelo.SetActive(false);

        menuGraficos = CrearPanelLateral("MenuGraficos", "GRÁFICOS DE UTILIZACIÓN",
            "Comprobación resistente de cada apoyo según los esfuerzos calculados.");
        Texto(menuGraficos,
            "Cada gráfico representa el punto real L–N del apoyo frente a su zona utilizable. " +
            "Puedes recorrer todos los apoyos, comprobar su margen y detectar configuraciones no válidas.",
            15, FontStyle.Normal, TextAnchor.UpperLeft, new Vector2(0, 165),
            new Vector2(400, 150), new Color(.78f, .82f, .88f));
        Boton(menuGraficos, "ABRIR GRÁFICOS", new Vector2(0, 45), new Vector2(360, 52),
            () => Abrir<VentanaGraficosUtilizacion>());
        Texto(menuGraficos,
            "Contenido disponible\n\n• Gráfico individual por apoyo\n• Tipo y montaje instalado\n" +
            "• Punto de utilización real\n• Límites resistentes\n• Navegación anterior/siguiente",
            15, FontStyle.Normal, TextAnchor.UpperLeft, new Vector2(0, -105),
            new Vector2(390, 240), new Color(.68f, .74f, .82f));
        menuGraficos.SetActive(false);

        menuDlr = CrearPanelLateral("MenuDLR", "DATOS DEL DLR",
            "Capacidad dinámica de transporte y meteorología de operación.");
        textoDlr = Texto(menuDlr, "Esperando datos DLR…", 14, FontStyle.Normal,
            TextAnchor.UpperLeft, new Vector2(0, -5), new Vector2(400, 570),
            new Color(.86f, .89f, .93f));
        textoDlr.horizontalOverflow = HorizontalWrapMode.Wrap;
        textoDlr.verticalOverflow = VerticalWrapMode.Truncate;
        Boton(menuDlr, "ACTUALIZAR DATOS", new Vector2(0, -330), new Vector2(360, 46), ActualizarDlr);
        menuDlr.SetActive(false);
    }

    GameObject CrearPanelLateral(string nombre, string titulo, string subtitulo)
    {
        var panel = Panel(canvas.gameObject, nombre, new Vector2(1, 0), new Vector2(1, 1),
            new Vector2(-245, -30), new Vector2(470, -60), new Color(.035f, .045f, .065f, .97f));
        // Titulo CENTRADO dentro del panel: el ancla (.5,.5) + pos (0,355) lo
        // mantiene centrado respecto al propio panel a cualquier resolucion.
        Texto(panel, titulo, 24, FontStyle.Bold, TextAnchor.MiddleCenter,
            new Vector2(0, 355), new Vector2(380, 42), new Color(.45f, .78f, 1f), new Vector2(.5f, .5f));
        Texto(panel, subtitulo, 14, FontStyle.Normal, TextAnchor.UpperLeft,
            new Vector2(0, 310), new Vector2(410, 58), new Color(.7f, .75f, .82f));
        Boton(panel, "×", new Vector2(205, 355), new Vector2(38, 38), CerrarMenus);
        return panel;
    }

    void AccionMenu(GameObject padre, string titulo, string descripcion, float y, Action accion)
    {
        var bloque = Panel(padre, "Accion_" + titulo, new Vector2(.5f, .5f), new Vector2(.5f, .5f),
            new Vector2(0, y), new Vector2(410, 74), new Color(.07f, .085f, .11f, 1f));
        Texto(bloque, titulo, 16, FontStyle.Bold, TextAnchor.MiddleLeft,
            new Vector2(18, 18), new Vector2(270, 26), new Color(.88f, .91f, .95f), new Vector2(0, .5f));
        Text detalle = Texto(bloque, descripcion, 12, FontStyle.Normal, TextAnchor.UpperLeft,
            new Vector2(18, -16), new Vector2(275, 42), new Color(.62f, .68f, .76f), new Vector2(0, .5f));
        detalle.horizontalOverflow = HorizontalWrapMode.Wrap;
        detalle.verticalOverflow = VerticalWrapMode.Truncate;
        Boton(bloque, "ABRIR", new Vector2(150, 0), new Vector2(90, 42), accion);
    }

    void MostrarMenu(GameObject menu)
    {
        bool abrir = menu != null && !menu.activeSelf;
        CerrarMenus();
        if (menu != null) menu.SetActive(abrir);
        if (abrir && menu == menuDlr) RefrescarTextoDlr();
    }

    void CerrarMenus()
    {
        OcultarVistaPerfil();
        if (menuGemelo != null) menuGemelo.SetActive(false);
        if (menuGraficos != null) menuGraficos.SetActive(false);
        if (menuDlr != null) menuDlr.SetActive(false);
    }

    void ActualizarDlr()
    {
        StartCoroutine(ActualizarDlrCoroutine());
    }

    IEnumerator ActualizarDlrCoroutine()
    {
        if (textoDlr != null)
        {
            textoDlr.text = "Obteniendo datos meteorológicos...";
        }
        // El motor clima.py genera meteorologia_actual.json (y el resto de JSON
        // del DLR) en la carpeta de trabajo actual. Si no hay conexion, usa la
        // ultima observacion valida o el fallback manual (nunca inventa 0).
        string salida = "";
        yield return MotorHelper.EjecutarMotorCoroutine("clima", "", s => salida = s);
        if (hud == null) hud = FindAnyObjectByType<InterfaceDLR>();
        if (hud != null && hud.servicioMeteorologia != null) hud.servicioMeteorologia.ActualizarAhora();
        if (hud != null && hud.servicioResultados != null) hud.servicioResultados.ActualizarAhora();
        RefrescarTextoDlr();
    }

    /// <summary>Reabre el menu lateral de Gemelo digital (lo usan las X de las
    /// ventanas de edicion para volver atras sin alterar datos).</summary>
    public void ReabrirMenuGemelo()
    {
        MostrarMenu(menuGemelo);
    }

    // -----------------------------------------------------------------------
    // Vista perfil (pestana de la barra superior)
    // -----------------------------------------------------------------------
    void CrearVistaPerfil()
    {
        var goPerfil = new GameObject("VistaPerfilLinea");
        goPerfil.transform.SetParent(transform, false);
        perfilLinea = goPerfil.AddComponent<VistaPerfilLinea>();

        panelVistaPerfil = Panel(canvas.gameObject, "PanelVistaPerfil",
            Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero,
            new Color(.014f, .02f, .032f, .99f));
        // PESTAÑA aparte: el panel ocupa todo el area de contenido MENOS la
        // franja superior de la barra de pestañas (60 px), como una pagina de
        // pestaña real y dinamica (no una ventana flotante).
        var prtVistaPerfil = panelVistaPerfil.GetComponent<RectTransform>();
        prtVistaPerfil.offsetMin = new Vector2(0, 0);
        prtVistaPerfil.offsetMax = new Vector2(0, -60);

        // Imagen con la camara 2D (antes que los textos para que quede detras)
        var imgGo = new GameObject("ImagenPerfil");
        imgGo.transform.SetParent(panelVistaPerfil.transform, false);
        var imgt = imgGo.AddComponent<RectTransform>();
        imgt.anchorMin = new Vector2(0, 0); imgt.anchorMax = new Vector2(1, 1);
        imgt.offsetMin = new Vector2(20, 20); imgt.offsetMax = new Vector2(-20, -20);
        imagenVistaPerfil = imgGo.AddComponent<RawImage>();
        imagenVistaPerfil.raycastTarget = false;

        Texto(panelVistaPerfil, "VISTA PERFIL DE LA LÍNEA", 24, FontStyle.Bold,
            TextAnchor.UpperLeft, new Vector2(30, -24), new Vector2(640, 40),
            new Color(.45f, .78f, 1f), new Vector2(0, 1));
        Texto(panelVistaPerfil,
            "Vanos 1-2, 2-3, 3-4... concatenados en 2D · en tiempo real con la escena 3D · alturas exageradas",
            14, FontStyle.Normal, TextAnchor.UpperLeft,
            new Vector2(30, -58), new Vector2(1000, 28),
            new Color(.7f, .75f, .82f), new Vector2(0, 1));
        Boton(panelVistaPerfil, "×", new Vector2(-36, -36), new Vector2(40, 40),
            OcultarVistaPerfil, new Vector2(1, 1));

        textoVacioPerfil = Texto(panelVistaPerfil, "Construye la línea para ver el perfil.",
            18, FontStyle.Normal, TextAnchor.MiddleCenter, Vector2.zero,
            new Vector2(800, 44), new Color(.62f, .68f, .76f));
        panelVistaPerfil.SetActive(false);
    }

    void MostrarVistaPerfil()
    {
        if (perfilLinea == null || panelVistaPerfil == null) return;
        bool mostrar = !vistaPerfilVisible;
        CerrarMenus(); // oculta los menus laterales y (por si acaso) el perfil
        vistaPerfilVisible = mostrar;
        panelVistaPerfil.SetActive(mostrar);
        if (mostrar) perfilLinea.Activar(imagenVistaPerfil, textoVacioPerfil);
        else perfilLinea.Desactivar();
        ActualizarPestanaVistaPerfil();
    }

    void OcultarVistaPerfil()
    {
        vistaPerfilVisible = false;
        if (panelVistaPerfil != null) panelVistaPerfil.SetActive(false);
        if (perfilLinea != null) perfilLinea.Desactivar();
        ActualizarPestanaVistaPerfil();
    }

    /// <summary>Realza la pestaña "Vista perfil" cuando esta activa (estilo de
    /// pestana seleccionada) y la deja normal cuando no.</summary>
    void ActualizarPestanaVistaPerfil()
    {
        if (textoBotonVistaPerfil == null) return;
        textoBotonVistaPerfil.fontStyle =
            vistaPerfilVisible ? FontStyle.Bold : FontStyle.Normal;
        textoBotonVistaPerfil.color =
            vistaPerfilVisible ? new Color(1f, 0.85f, 0.4f) : Color.white;
    }

    /// <summary>Precarga en cache los catalogos de solo lectura que usan las
    /// ventanas (tipos de apoyo, cadenas y conductores) para que abrirlas
    /// despues de cargar la linea sea instantaneo (el arranque del motor.exe
    /// es lo que tarda ~1-3 s por llamada).</summary>
    IEnumerator PrecargarCatalogos()
    {
        // Catalogo de tipos de apoyo (gamas -> montajes -> detalles)
        string s1 = null;
        yield return MotorHelper.EjecutarMotorCoroutine(
            "cambiar_tipo_apoyo", "--catalogo", x => s1 = x);
        if (!string.IsNullOrWhiteSpace(s1))
            CacheCatalogos.Precargar(CacheCatalogos.ClaveTipoApoyo, s1);

        // Catalogo de conductores
        string s2 = null;
        yield return MotorHelper.EjecutarMotorCoroutine(
            "cambiar_cadena_conductor",
            "cambiar_cadena_conductor.py --catalogo_conductores",
            x => s2 = x);
        if (!string.IsNullOrWhiteSpace(s2))
            CacheCatalogos.Precargar(CacheCatalogos.ClaveConductores, s2);

        // Catalogo de cadenas (depende del conductor de la linea)
        string conductor = LeerConductorLinea();
        string argsCadenas = "cambiar_cadena_conductor.py --catalogo_cadenas";
        if (!string.IsNullOrEmpty(conductor))
            argsCadenas += " --conductor \"" + conductor + "\"";
        string s3 = null;
        yield return MotorHelper.EjecutarMotorCoroutine(
            "cambiar_cadena_conductor", argsCadenas, x => s3 = x);
        if (!string.IsNullOrWhiteSpace(s3))
            CacheCatalogos.Precargar("catalogo_cadenas_" + conductor, s3);
    }

    string LeerConductorLinea()
    {
        try
        {
            string ruta = Path.Combine(RutasGemelo.RutaAssetsGemelo(),
                                       "conductor_configurado.json");
            if (!File.Exists(ruta)) return "";
            var doc = Json.Deserialize(File.ReadAllText(ruta, System.Text.Encoding.UTF8))
                as Dictionary<string, object>;
            if (doc != null && doc.ContainsKey("nomenclatura_excel")
                && doc["nomenclatura_excel"] != null)
                return doc["nomenclatura_excel"].ToString();
        }
        catch (Exception) { }
        return "";
    }


    /// <summary>Reabre el menu lateral de Graficos de utilizacion.</summary>
    public void ReabrirMenuGraficos()
    {
        MostrarMenu(menuGraficos);
    }

    void RefrescarTextoDlr()
    {
        if (textoDlr == null) return;
        if (hud == null) hud = FindAnyObjectByType<InterfaceDLR>();
        if (generador == null) generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (hud == null)
        {
            textoDlr.text = "No se ha encontrado el servicio DLR de la escena.";
            return;
        }
        float corriente = generador != null ? generador.dlrCorrienteMaximaA : hud.limiteLineaA;
        // Si hay archivo con datos (aunque sean de respaldo manual), se muestran
        // los valores; solo se ocultan con "—" cuando NO existe ningun dato.
        bool hayMeteorologia = hud.estadoMeteorologia != "SIN_DATOS";
        string estadoOperacion = hud.datosMeteorologicosValidos
            ? "OPERATIVO"
            : (hud.estadoMeteorologia == "FALLBACK"
                ? "FALLBACK (datos NO reales)"
                : hud.estadoMeteorologia);
        string prevision = LimitarLineas(hud.prevision, 10);
        string aviso = "";
        if (hud.estadoMeteorologia == "CACHE"
            || (!hud.datosMeteorologicosValidos && hud.estadoMeteorologia != "SIN_DATOS"))
            aviso = "\n\nAVISO: " + (string.IsNullOrWhiteSpace(hud.mensajeMeteorologia)
                ? "Sin conexion. Se muestra la ultima observacion disponible."
                : hud.mensajeMeteorologia);
        textoDlr.text =
            "ESTADO DE OPERACIÓN\n" + estadoOperacion + "\n\n" +
            "CAPACIDAD DINÁMICA\n" +
            "I máxima IEEE 738: " + (corriente > 0 ? corriente.ToString("0.0") + " A" : "no disponible") + "\n" +
            "Límite RLAT: " + (hud.iRlatA > 0 ? hud.iRlatA.ToString("0.0") + " A" : "no disponible") + "\n" +
            "Límite de línea: " + (hud.limiteLineaA > 0 ? hud.limiteLineaA.ToString("0.0") + " A" : "no disponible") + "\n\n" +
            "METEOROLOGÍA ACTUAL\n" +
            "Temperatura: " + (hayMeteorologia
                ? hud.taC.ToString("0.0") + " °C" : "—") + "\n" +
            "Viento: " + (hayMeteorologia
                ? hud.vwMs.ToString("0.0") + " m/s · " + hud.dirViento.ToString("0") + "°"
                : "—") + "\n" +
            "Estación: " + hud.fuente + " (" + hud.tipoEstacion + ")\n" +
            "Fecha/hora: " + hud.fechaHora + "\n" +
            "Antigüedad: " + (hud.antiguedadMin >= 0 ? hud.antiguedadMin.ToString("0") + " min" : "—") + "\n\n" +
            "ÁMBITO GEOGRÁFICO\n" +
            "Municipios: " + hud.numMunicipios + "\n" +
            "Municipio crítico: " + hud.municipioCritico + "\n" +
            (string.IsNullOrWhiteSpace(hud.listaMunicipios) ? "" : hud.listaMunicipios + "\n") +
            "\nPREVISIÓN DE CAPACIDAD\n" +
            (string.IsNullOrWhiteSpace(prevision) ? "Sin previsión disponible." : prevision) + aviso;
    }

    string LimitarLineas(string valor, int maximo)
    {
        if (string.IsNullOrWhiteSpace(valor)) return "";
        string[] lineas = valor.Split(new[] {'\r', '\n'}, StringSplitOptions.RemoveEmptyEntries);
        return string.Join("\n", lineas.Take(maximo).ToArray());
    }

    enum TipoEntrada { Excel, Utm, Cuadros, Ortofoto }

    void SeleccionarSimple(TipoEntrada tipo)
    {
        string extension = tipo == TipoEntrada.Excel ? "xlsx" : tipo == TipoEntrada.Ortofoto ? "tif" : "";
        string titulo = tipo == TipoEntrada.Excel ? "Selecciona el Excel de Andelec"
            : tipo == TipoEntrada.Utm ? "Selecciona las coordenadas UTM"
            : tipo == TipoEntrada.Cuadros ? "Selecciona el archivo de Cuadros"
            : "Selecciona la ortofoto PNOA";
#if UNITY_EDITOR
        AplicarSeleccionSimple(tipo, DialogoArchivo.Abrir(titulo, DirectorioInicial(), extension));
#else
        // En el .exe usamos el explorador integrado de Unity (los diálogos de
        // Windows no siempre aparecen delante de la ventana a pantalla completa).
        SelectorArchivo.Mostrar(titulo, DirectorioInicial(), extension,
            ruta => AplicarSeleccionSimple(tipo, ruta));
#endif
    }

    void AplicarSeleccionSimple(TipoEntrada tipo, string ruta)
    {
        if (string.IsNullOrWhiteSpace(ruta)) return;
        if (tipo == TipoEntrada.Excel) { excelSeleccionado = ruta; carpetaExportacion = Path.GetDirectoryName(ruta); }
        else if (tipo == TipoEntrada.Utm) utmSeleccionado = ruta;
        else if (tipo == TipoEntrada.Cuadros) cuadrosSeleccionado = ruta;
        else ortoSeleccionado = ruta;
        ActualizarResumen();
    }

    void SeleccionarMdt()
    {
#if UNITY_EDITOR
        string ruta = DialogoArchivo.Abrir("Añade un PNOA MDT de elevaciones", DirectorioInicial(), "tif");
        if (!string.IsNullOrWhiteSpace(ruta) && !mdtSeleccionados.Contains(ruta)) mdtSeleccionados.Add(ruta);
        ActualizarResumen();
#else
        SelectorArchivo.Mostrar("Añade un PNOA MDT de elevaciones", DirectorioInicial(), "tif",
            ruta =>
            {
                if (!string.IsNullOrWhiteSpace(ruta) && !mdtSeleccionados.Contains(ruta))
                    mdtSeleccionados.Add(ruta);
                ActualizarResumen();
            });
#endif
    }

    string DirectorioInicial()
    {
        return !string.IsNullOrEmpty(excelSeleccionado)
            ? Path.GetDirectoryName(excelSeleccionado) : RutasGemelo.RutaDatosBase();
    }

    void ActualizarResumen()
    {
        if (rutaExcelTexto == null) return;
        rutaExcelTexto.text = Resumen(excelSeleccionado);
        rutaUtmTexto.text = Resumen(utmSeleccionado);
        rutaCuadrosTexto.text = Resumen(cuadrosSeleccionado);
        rutaOrtoTexto.text = Resumen(ortoSeleccionado);
        rutaMdtTexto.text = mdtSeleccionados.Count == 0 ? "No seleccionado"
            : mdtSeleccionados.Count + " TIFF: " + string.Join(", ", mdtSeleccionados.Select(Path.GetFileName).ToArray());
        bool correcto = ValidarSeleccion(false);
        estado.text = correcto ? "Todos los archivos necesarios están seleccionados."
            : "Selecciona los cinco tipos de entrada antes de cargar la línea.";
        estado.color = correcto ? new Color(.45f, .86f, .58f) : new Color(.95f, .72f, .3f);
    }

    string Resumen(string ruta) { return File.Exists(ruta) ? "✓  " + Path.GetFileName(ruta) : "No seleccionado"; }

    bool ValidarSeleccion(bool mostrarDetalle)
    {
        var faltan = new List<string>();
        if (!File.Exists(excelSeleccionado)) faltan.Add("Excel de Andelec");
        if (!File.Exists(utmSeleccionado)) faltan.Add("coordenadas UTM");
        if (!File.Exists(cuadrosSeleccionado)) faltan.Add("archivo de Cuadros");
        if (!mdtSeleccionados.Any(File.Exists)) faltan.Add("PNOA MDT");
        if (!File.Exists(ortoSeleccionado)) faltan.Add("ortofoto PNOA");
        if (mostrarDetalle && faltan.Count > 0) estado.text = "Faltan: " + string.Join(", ", faltan.ToArray()) + ".";
        return faltan.Count == 0;
    }

    IEnumerator CargarLinea()
    {
        if (!ValidarSeleccion(true)) yield break;
        estado.color = new Color(.95f, .72f, .3f);
        estado.text = "Preparando una copia de trabajo de los archivos…";
        yield return null;
        try { PrepararCarpetaTrabajo(); }
        catch (Exception ex)
        {
            estado.color = new Color(1f, .42f, .42f);
            estado.text = "No se pudo preparar la línea: " + ex.Message;
            yield break;
        }
        RutasGemelo.ConfigurarRutaDatos(carpetaTrabajo);
        estado.text = "Procesando terreno, apoyos, cables y cadenas…";
        string salida = "";
        yield return MotorHelper.EjecutarMotorCoroutine("principal", "", s => salida = s);
        if (!File.Exists(Path.Combine(RutasGemelo.RutaAssetsGemelo(), "coordenadas_linea.csv")))
        {
            estado.color = new Color(1f, .42f, .42f);
            estado.text = "No se pudo generar la línea. Revisa los archivos de entrada.\n" + UltimaLinea(salida);
            yield break;
        }
        generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador != null) generador.ConstruirEscenaCompleta();
        StartCoroutine(PrecargarCatalogos());
        if (hud == null) hud = FindAnyObjectByType<InterfaceDLR>();
        if (hud != null) hud.mostrarHUD = false;
        ActualizarDlr();
        CerrarMenus();
        inicio.SetActive(false); barra.SetActive(true); ayudaCamara.SetActive(true);
        var cam = FindAnyObjectByType<CamaraLinea>();
        if (cam != null) { yield return null; cam.EncuadrarLinea(); }
    }

    void PrepararCarpetaTrabajo()
    {
        string sesiones = Path.Combine(Application.persistentDataPath, "Lineas");
        carpetaTrabajo = Path.Combine(sesiones, "Linea_" + DateTime.Now.ToString("yyyyMMdd_HHmmssfff"));
        Directory.CreateDirectory(carpetaTrabajo);
        Copiar(excelSeleccionado, Path.Combine(carpetaTrabajo, Path.GetFileName(excelSeleccionado)));
        Copiar(utmSeleccionado, Path.Combine(carpetaTrabajo, "Coordenadas_UTM" + Path.GetExtension(utmSeleccionado)));
        Copiar(cuadrosSeleccionado, Path.Combine(carpetaTrabajo, "Cuadros_linea" + Path.GetExtension(cuadrosSeleccionado)));
        for (int i = 0; i < mdtSeleccionados.Count; i++)
            EnlazarOCopiar(mdtSeleccionados[i], Path.Combine(carpetaTrabajo, "PNOA_MDT05_" + (i + 1).ToString("00") + ".tif"));
        EnlazarOCopiar(ortoSeleccionado, Path.Combine(carpetaTrabajo, "PNOA_MA_01.tif"));
        // El estado base de Unity tambien se copia a la carpeta
        // de trabajo para que la linea activa sea autonoma: graficos de
        // utilizacion (titulos de la ventana), meteorologia de respaldo y RLAT.
        string assetsBase = RutasGemelo.RutaAssetsGemelo();
        string assetsTrabajo = Path.Combine(carpetaTrabajo, "unity", "Assets");
        foreach (string nombre in new[] { "graficos_utilizacion.json",
                                          "meteorologia_ultima_valida.json",
                                          "meteorologia_actual.json",
                                          "intensidadreglamento.json" })
        {
            string origen = Path.Combine(assetsBase, nombre);
            if (File.Exists(origen)) Copiar(origen, Path.Combine(assetsTrabajo, nombre));
        }
    }

    void Copiar(string origen, string destino)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(destino));
        File.Copy(origen, destino, false);
    }

    void CopiarDirectorio(string origen, string destino)
    {
        if (!Directory.Exists(origen)) throw new DirectoryNotFoundException("Faltan los catálogos internos: " + origen);
        foreach (string directorio in Directory.GetDirectories(origen, "*", SearchOption.AllDirectories))
            Directory.CreateDirectory(directorio.Replace(origen, destino));
        foreach (string archivo in Directory.GetFiles(origen, "*", SearchOption.AllDirectories))
            Copiar(archivo, archivo.Replace(origen, destino));
    }

    void EnlazarOCopiar(string origen, string destino)
    {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
        if (CreateHardLink(destino, origen, IntPtr.Zero)) return;
#endif
        Copiar(origen, destino);
    }

#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
    [DllImport("Kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateHardLink(string nombreNuevo, string nombreExistente, IntPtr seguridad);
#endif

    string UltimaLinea(string texto)
    {
        if (string.IsNullOrWhiteSpace(texto)) return "El motor no devolvió detalles.";
        string[] lineas = texto.Split(new[] {'\r','\n'}, StringSplitOptions.RemoveEmptyEntries);
        return lineas.Length == 0 ? texto : lineas[lineas.Length - 1];
    }

    void VolverAInicio()
    {
        CerrarMenus();
        barra.SetActive(false);
        ayudaCamara.SetActive(false);
        inicio.SetActive(true);
        ActualizarResumen();
    }

    void Abrir<T>() where T : MonoBehaviour
    {
        CerrarMenus();
        T herramienta = FindAnyObjectByType<T>();
        if (herramienta == null) herramienta = new GameObject(typeof(T).Name).AddComponent<T>();
        herramienta.SendMessage("AbrirVentana", SendMessageOptions.DontRequireReceiver);
    }

    GameObject Panel(GameObject padre, string nombre, Vector2 amin, Vector2 amax, Vector2 pos, Vector2 tam, Color color)
    {
        var go = new GameObject(nombre); go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>(); rt.anchorMin = amin; rt.anchorMax = amax;
        rt.anchoredPosition = pos; rt.sizeDelta = tam;
        go.AddComponent<Image>().color = color; return go;
    }

    Text Texto(GameObject padre, string contenido, int tam, FontStyle estilo, TextAnchor alineacion,
        Vector2 pos, Vector2 size, Color? color = null, Vector2? ancla = null)
    {
        var go = new GameObject("Texto"); go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>(); Vector2 a = ancla ?? new Vector2(.5f, .5f);
        rt.anchorMin = a; rt.anchorMax = a; rt.pivot = a.x == 0 ? new Vector2(0, .5f) : new Vector2(.5f, .5f);
        rt.anchoredPosition = pos; rt.sizeDelta = size;
        var texto = go.AddComponent<Text>(); texto.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        texto.text = contenido; texto.fontSize = tam; texto.fontStyle = estilo;
        texto.alignment = alineacion; texto.color = color ?? Color.white; return texto;
    }

    Button Boton(GameObject padre, string etiqueta, Vector2 pos, Vector2 size, Action accion, Vector2? ancla = null)
    {
        var go = new GameObject("Boton_" + etiqueta); go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>(); Vector2 a = ancla ?? new Vector2(.5f, .5f);
        rt.anchorMin = a; rt.anchorMax = a; rt.pivot = a.x == 0 ? new Vector2(0, .5f) : new Vector2(.5f, .5f);
        rt.anchoredPosition = pos; rt.sizeDelta = size;
        var imagen = go.AddComponent<Image>(); imagen.color = new Color(.12f, .31f, .52f, 1f);
        var boton = go.AddComponent<Button>(); boton.targetGraphic = imagen;
        UiBoton.AplicarEstilo(boton);
        boton.onClick.AddListener(() => accion?.Invoke());

        // Image y Text son ambos Graphic; el texto debe vivir en un hijo.
        var hijo = new GameObject("Etiqueta"); hijo.transform.SetParent(go.transform, false);
        var hrt = hijo.AddComponent<RectTransform>(); hrt.anchorMin = Vector2.zero; hrt.anchorMax = Vector2.one;
        hrt.offsetMin = Vector2.zero; hrt.offsetMax = Vector2.zero;
        var texto = hijo.AddComponent<Text>(); texto.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        texto.text = etiqueta; texto.fontSize = 14; texto.fontStyle = FontStyle.Bold;
        texto.alignment = TextAnchor.MiddleCenter; texto.color = Color.white; texto.raycastTarget = false;
        return boton;
    }
}

static class DialogoArchivo
{
#if UNITY_EDITOR
    public static string Abrir(string titulo, string inicial, string extension)
    {
        return UnityEditor.EditorUtility.OpenFilePanel(titulo, inicial, extension);
    }
#elif UNITY_STANDALONE_WIN
    // Estructura OPENFILENAMEW (Unicode) de comdlg32, tal cual Windows x64.
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct OPENFILENAME
    {
        public int lStructSize;
        public IntPtr hwndOwner, hInstance;
        public string lpstrFilter, lpstrCustomFilter;
        public int nMaxCustFilter, nFilterIndex;
        public System.Text.StringBuilder lpstrFile;
        public int nMaxFile;
        public string lpstrFileTitle;
        public int nMaxFileTitle;
        public string lpstrInitialDir, lpstrTitle;
        public int Flags;
        public short nFileOffset, nFileExtension;
        public string lpstrDefExt;
        public IntPtr lCustData, lpfnHook;
        public string lpTemplateName;
        public IntPtr pvReserved;
        public int dwReserved, FlagsEx;
    }
    [DllImport("comdlg32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool GetOpenFileName(ref OPENFILENAME ofn);
    [DllImport("user32.dll")]
    static extern IntPtr GetForegroundWindow();

    // Flags de OPENFILENAME: OFN_EXPLORER (dialogo moderno), FILE/PATHMUSTEXIST
    // y NOCHANGEDIR (no alterar el directorio de trabajo al navegar).
    const int OFN_EXPLORER = 0x00080000;
    const int OFN_FILEMUSTEXIST = 0x00001000;
    const int OFN_PATHMUSTEXIST = 0x00000800;
    const int OFN_NOCHANGEDIR = 0x00000008;

    public static string Abrir(string titulo, string inicial, string extension)
    {
        try
        {
            string filtro = extension == "xlsx" ? "Excel (*.xlsx)\0*.xlsx\0\0"
                : extension == "tif" ? "GeoTIFF (*.tif)\0*.tif\0\0"
                : "Documentos Word (*.doc;*.docx)\0*.doc;*.docx\0Todos (*.*)\0*.*\0\0";
            var archivo = new System.Text.StringBuilder(4096);
            var ofn = new OPENFILENAME
            {
                lStructSize = Marshal.SizeOf(typeof(OPENFILENAME)),
                hwndOwner = VentanaPropietaria(),
                lpstrFilter = filtro,
                lpstrFile = archivo,
                nMaxFile = archivo.Capacity,
                lpstrInitialDir = string.IsNullOrEmpty(inicial) ? null : inicial,
                lpstrTitle = titulo,
                Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR,
                lpstrDefExt = string.IsNullOrEmpty(extension) ? null : extension,
            };
            bool aceptado = GetOpenFileName(ref ofn);
            return aceptado ? archivo.ToString() : "";
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("DialogoArchivo: no se pudo abrir el selector: " + ex.Message);
            return "";
        }
    }

    // Ventana propietaria para que el dialogo salga DELANTE de la ventana de
    // Unity (a pantalla completa) y sea modal, en vez de quedarse detras.
    static IntPtr VentanaPropietaria()
    {
        try
        {
            IntPtr h = System.Diagnostics.Process.GetCurrentProcess().MainWindowHandle;
            if (h != IntPtr.Zero) return h;
        }
        catch { }
        return GetForegroundWindow();
    }
#else
    public static string Abrir(string titulo, string inicial, string extension) { return ""; }
#endif
}
