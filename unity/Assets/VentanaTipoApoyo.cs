using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

/// <summary>
/// VentanaTipoApoyo — Asistente para cambiar el TIPO DE APOYO (gama + montaje
/// + cruceta/boveda) de un apoyo.
/// ==========================================================================
/// De mayor a menor:
///   1. GAMA    : Serie C (Andel), Andel M60, Andel M50, Serie G (Andel).
///   2. TIPO    : Tresbolillo, Bandera, Boveda en capa, Boveda en pico,
///                Boveda triangulo, Horizontal (doble circuito solo 6 fases).
///   3. DETALLE : la semicruceta / boveda concreta (longitud, atirantada...).
///
/// El catalogo se obtiene de Python ('cambiar_tipo_apoyo.py --catalogo'),
/// que solo ofrece opciones con FBX real y compatibles con Unity y con el
/// numero de fases de la linea.
///
/// Al pulsar "APLICAR" Python actualiza el Excel de trabajo y
/// apoyos_configurados.json, y la escena se reconstruye.
/// Se puede abrir pinchando sobre el FUSTE de un apoyo en el 3D.
/// </summary>
public class VentanaTipoApoyo : MonoBehaviour
{
    class OptDetalle
    {
        public string id;
        public string tipo;
        public float a_m;
        public bool atirantada;
        public string etiqueta;
    }

    class OptMontaje
    {
        public string tipo;
        public string nombre;
        public int niveles;
        public List<OptDetalle> detalles = new List<OptDetalle>();
    }

    class OptGama
    {
        public string id;
        public string nombre;
        public string familia;
        public List<OptMontaje> montajes = new List<OptMontaje>();
    }

    // Rutas
    private string rutaPython = "";
    private string rutaUtm = "";
    private string rutaExcel = "";
    private string rutaSalidaExcel = "";
    private string rutaConfig = "";

    // UI
    private Canvas canvas;
    private GameObject ventana;
    private Text titulo;
    private Dropdown apoyoDropdown;
    private Text gamaLabel;
    private Text montajeLabel;
    private Text detalleLabel;
    private Text mensaje;
    private Text pista;
    private Text componentesActuales;   // componentes ACTUALES del apoyo (referencia)
    private VistaPrevia3D vistaPrevia;  // vista 3D del detalle seleccionado
    private bool sincronizandoDropdown = false;

    // Estado del asistente
    private int seleccionado = 1;
    private int totalApoyos = 4;
    private int numeroFases = 3;
    private List<OptGama> gamas = new List<OptGama>();
    private int indiceGama = 0;
    private int indiceMontaje = 0;
    private int indiceDetalle = 0;

    static void AutoInstalar()
    {
        if (FindAnyObjectByType<VentanaTipoApoyo>() == null)
        {
            var go = new GameObject("VentanaTipoApoyo");
            go.AddComponent<VentanaTipoApoyo>();
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
            rutaUtm = BuscarRutaUtm(rutaPython, nombreExcel);
            if (File.Exists(rutaSalidaExcel)) rutaExcel = rutaSalidaExcel;
            rutaConfig = Path.Combine(RutasGemelo.RutaAssetsGemelo(),
                                      "apoyos_configurados.json");

            CargarApoyosConfig();
            CrearCanvasYEventSystem();
            CrearVentana();
            MostrarApoyo(1);
            // El catalogo se carga SIN bloquear la app (Python tarda ~1-2 s)
            StartCoroutine(CargarCatalogoAsync());
            DontDestroyOnLoad(gameObject);
            UnityEngine.Debug.Log("[VentanaTipoApoyo] catalogo con "
                + gamas.Count + " gamas (" + numeroFases + " fases).");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaTipoApoyo: " + ex.Message);
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

    /// <summary>Localiza el JSON UTM de la linea (mismo criterio que las
    /// demas ventanas): carpeta de trabajo y despues la base.</summary>
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

    /// <summary>Interpreta el JSON del catalogo devuelto por Python.</summary>
    bool ProcesarCatalogoJson(string stdout)
    {
        try
        {
            var doc = Json.Deserialize(stdout) as Dictionary<string, object>;
            if (doc == null || !(doc["gamas"] is List<object>)) return false;
            numeroFases = Convert.ToInt32(doc["numero_fases"]);
            gamas.Clear();
            foreach (var gObj in (List<object>)doc["gamas"])
            {
                var g = gObj as Dictionary<string, object>;
                if (g == null) continue;
                OptGama gama = new OptGama
                {
                    id = g["id"].ToString(),
                    nombre = g["nombre"].ToString(),
                    familia = g["familia"].ToString(),
                };
                foreach (var mObj in (List<object>)g["montajes"])
                {
                    var m = mObj as Dictionary<string, object>;
                    if (m == null) continue;
                    OptMontaje montaje = new OptMontaje
                    {
                        tipo = m["tipo"].ToString(),
                        nombre = m["nombre"].ToString(),
                        niveles = Convert.ToInt32(m["niveles"]),
                    };
                    foreach (var dObj in (List<object>)m["detalles"])
                    {
                        var d = dObj as Dictionary<string, object>;
                        if (d == null) continue;
                        montaje.detalles.Add(new OptDetalle
                        {
                            id = d["id"].ToString(),
                            tipo = d["tipo"].ToString(),
                            a_m = Convert.ToSingle(d["a_m"]),
                            atirantada = Convert.ToBoolean(d["atirantada"]),
                            etiqueta = d["etiqueta"].ToString(),
                        });
                    }
                    gama.montajes.Add(montaje);
                }
                gamas.Add(gama);
            }
            return gamas.Count > 0;
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError("VentanaTipoApoyo catalogo: " + ex.Message);
            return false;
        }
    }

    /// <summary>Carga el catalogo de gamas SIN bloquear la app.</summary>
    IEnumerator CargarCatalogoAsync()
    {
        // Catalogo de solo lectura: cacheado para que abrir la ventana por
        // segunda vez sea instantaneo (el arranque del motor es lo que tarda).
        string stdout = CacheCatalogos.Obtener(CacheCatalogos.ClaveTipoApoyo, null);
        if (stdout == null)
        {
            string salida = null;
            yield return MotorHelper.EjecutarMotorCoroutine(
                "cambiar_tipo_apoyo", "--catalogo", s => salida = s);
            stdout = salida;
            if (!string.IsNullOrWhiteSpace(stdout))
                CacheCatalogos.Precargar(CacheCatalogos.ClaveTipoApoyo, stdout);
        }
        if (!ProcesarCatalogoJson(stdout))
        {
            // Muestra la salida REAL del motor (traceback, JSON de error...)
            // para poder diagnosticar sin abrir la consola.
            string detalle = string.IsNullOrEmpty(stdout) ? "(sin salida)" : stdout;
            if (detalle.Length > 400) detalle = detalle.Substring(detalle.Length - 400);
            UnityEngine.Debug.LogError("[VentanaTipoApoyo] No se pudo cargar el catalogo.\n"
                + "Salida del motor:\n" + detalle);
            if (pista != null)
                pista.text = "No se pudo cargar el catalogo de tipos de apoyo:\n"
                    + detalle.Replace("\n", " ");
            yield break;
        }
        MostrarApoyo(1); // refresca GAMA/TIPO/DETALLE con los datos reales
    }

    // ====================================================================
    // Navegacion del asistente
    // ====================================================================
    List<OptMontaje> MontajesActuales()
    {
        if (indiceGama < 0 || indiceGama >= gamas.Count) return new List<OptMontaje>();
        return gamas[indiceGama].montajes;
    }

    List<OptDetalle> DetallesActuales()
    {
        var montajes = MontajesActuales();
        if (indiceMontaje < 0 || indiceMontaje >= montajes.Count)
            return new List<OptDetalle>();
        return montajes[indiceMontaje].detalles;
    }

    void CambiarGama(int delta)
    {
        if (gamas.Count == 0) return;
        indiceGama = (indiceGama + delta + gamas.Count) % gamas.Count;
        indiceMontaje = 0;
        indiceDetalle = 0;
        ActualizarLabels();
        mensaje.text = "";
    }

    void CambiarMontaje(int delta)
    {
        var montajes = MontajesActuales();
        if (montajes.Count == 0) return;
        indiceMontaje = (indiceMontaje + delta + montajes.Count) % montajes.Count;
        indiceDetalle = 0;
        ActualizarLabels();
        mensaje.text = "";
    }

    void CambiarDetalle(int delta)
    {
        var detalles = DetallesActuales();
        if (detalles.Count == 0) return;
        indiceDetalle = (indiceDetalle + delta + detalles.Count) % detalles.Count;
        ActualizarLabels();
        mensaje.text = "";
    }

    void ActualizarLabels()
    {
        if (indiceGama >= 0 && indiceGama < gamas.Count)
            gamaLabel.text = gamas[indiceGama].nombre;
        var montajes = MontajesActuales();
        if (indiceMontaje >= 0 && indiceMontaje < montajes.Count)
            montajeLabel.text = montajes[indiceMontaje].nombre;
        var detalles = DetallesActuales();
        if (indiceDetalle >= 0 && indiceDetalle < detalles.Count)
            detalleLabel.text = detalles[indiceDetalle].etiqueta;
        ActualizarVistaPrevia();
    }

    /// <summary>Muestra en 3D el detalle seleccionado (gama -> tipo -> detalle).</summary>
    void ActualizarVistaPrevia()
    {
        if (vistaPrevia == null) return;
        var detalles = DetallesActuales();
        if (indiceDetalle < 0 || indiceDetalle >= detalles.Count)
        {
            vistaPrevia.Ocultar();
            return;
        }
        // 'id' es la referencia del catalogo (p.ej. C_ASC-12); VistaPrevia3D
        // resuelve el FBX real (tambien las variantes atirantadas _H).
        // Las semicrucetas PLANAS se muestran en planta (desde arriba) para
        // apreciar su forma triangular; atirantadas y bovedas en 3/4.
        bool esPlanta = false;
        var montajes = MontajesActuales();
        if (indiceMontaje >= 0 && indiceMontaje < montajes.Count)
        {
            string tipoMontaje = montajes[indiceMontaje].tipo;
            bool montajePlano = tipoMontaje == "TRESBOLILLO"
                || tipoMontaje == "BANDERA"
                || tipoMontaje == "HORIZONTAL"
                || tipoMontaje == "DOBLE_CIRCUITO"
                || tipoMontaje == "PASO_LATERAL";
            esPlanta = montajePlano && !detalles[indiceDetalle].atirantada;
        }
        vistaPrevia.Mostrar(detalles[indiceDetalle].id, esPlanta);
    }

    // ====================================================================
    // Estado actual del apoyo (desde apoyos_configurados.json)
    // ====================================================================
    void CargarApoyosConfig()
    {
        if (!File.Exists(rutaConfig)) return;
        var doc = JsonUtility.FromJson<DocumentoApoyosConfigurados>(
            File.ReadAllText(rutaConfig, System.Text.Encoding.UTF8));
        if (doc != null && doc.apoyos != null && doc.apoyos.Length > 0)
            totalApoyos = doc.apoyos.Length;
    }

    void MostrarApoyo(int n)
    {
        if (n < 1) n = 1;
        if (n > totalApoyos) n = totalApoyos;
        seleccionado = n;
        titulo.text = "CAMBIAR TIPO DE APOYO - APOYO " + n;
        sincronizandoDropdown = true;
        if (apoyoDropdown != null) apoyoDropdown.value = n - 1;
        sincronizandoDropdown = false;
        SincronizarConActual();
        ActualizarComponentesActuales();
        ActualizarLabels();
        mensaje.text = "";
    }

    void SincronizarConActual()
    {
        if (gamas.Count == 0 || !File.Exists(rutaConfig)) return;
        var doc = JsonUtility.FromJson<DocumentoApoyosConfigurados>(
            File.ReadAllText(rutaConfig, System.Text.Encoding.UTF8));
        if (doc == null || doc.apoyos == null) return;

        foreach (var a in doc.apoyos)
        {
            if (a == null || a.apoyo == null || a.apoyo.numero != seleccionado)
                continue;

            // 1) Gama actual (se deduce de la familia del armado)
            string fam = (a.armado != null) ? a.armado.familia ?? "" : "";
            for (int i = 0; i < gamas.Count; i++)
            {
                bool misma = (gamas[i].id == "SERIE_C" && fam == "C")
                    || (gamas[i].id == "ANDEL_M60" && fam == "M60")
                    || (gamas[i].id == "ANDEL_M50" && fam == "M50")
                    || (gamas[i].id == "SERIE_G" && fam == "G");
                if (misma) { indiceGama = i; break; }
            }

            // 2) Montaje actual (si existe en esta gama)
            string montajeActual = (a.montaje != null) ? a.montaje.tipo ?? "" : "";
            indiceMontaje = 0;
            var montajes = MontajesActuales();
            for (int i = 0; i < montajes.Count; i++)
            {
                if (montajes[i].tipo == montajeActual) { indiceMontaje = i; break; }
            }

            // 3) Detalle actual (coincide por 'tipo')
            string crucetaActual = (a.cruceta != null)
                ? a.cruceta.tipo_origen ?? "" : "";
            indiceDetalle = 0;
            var detalles = DetallesActuales();
            for (int i = 0; i < detalles.Count; i++)
            {
                if (detalles[i].tipo == crucetaActual) { indiceDetalle = i; break; }
            }
            return;
        }
    }

    static string NombreGamaDeFamilia(string familia)
    {
        if (familia == "C") return "Serie C (Andel)";
        if (familia == "M60") return "Andel M60";
        if (familia == "M50") return "Andel M50";
        if (familia == "G") return "Serie G (Andel)";
        return string.IsNullOrEmpty(familia) ? "—" : familia;
    }

    static string NombreMontajeDeTipo(string tipo)
    {
        if (tipo == "TRESBOLILLO") return "Tresbolillo";
        if (tipo == "BANDERA") return "Bandera";
        if (tipo == "BOVEDA_CAPA") return "Bóveda en capa";
        if (tipo == "BOVEDA_PICO") return "Bóveda en pico";
        if (tipo == "BOVEDA_TRIANGULO") return "Bóveda triángulo";
        if (tipo == "HORIZONTAL") return "Horizontal";
        if (tipo == "DOBLE_CIRCUITO") return "Doble circuito";
        return string.IsNullOrEmpty(tipo) ? "—" : tipo;
    }

    /// <summary>Muestra los componentes ACTUALES del apoyo (gama, montaje y
    /// cruceta) como referencia fija, leidos de apoyos_configurados.json.</summary>
    void ActualizarComponentesActuales()
    {
        if (componentesActuales == null) return;
        string texto = "ACTUAL: —";
        try
        {
            if (File.Exists(rutaConfig))
            {
                var doc = JsonUtility.FromJson<DocumentoApoyosConfigurados>(
                    File.ReadAllText(rutaConfig, System.Text.Encoding.UTF8));
                foreach (var a in doc?.apoyos ?? new ApoyoConfigurado[0])
                {
                    if (a == null || a.apoyo == null || a.apoyo.numero != seleccionado)
                        continue;
                    string gama = NombreGamaDeFamilia(
                        (a.armado != null) ? a.armado.familia : "");
                    string montaje = NombreMontajeDeTipo(
                        (a.montaje != null) ? a.montaje.tipo : "");
                    string detalle = "—";
                    if (a.cruceta != null && !string.IsNullOrEmpty(a.cruceta.tipo_origen))
                    {
                        detalle = a.cruceta.tipo_origen
                            + (a.cruceta.a_m > 0f
                                ? " · " + a.cruceta.a_m.ToString("F2") + " m"
                                : "")
                            + (a.cruceta.es_atirantada ? " · ATIRANTADA" : " · PLANA");
                    }
                    texto = "ACTUAL:  " + gama + "  ·  " + montaje + "  ·  " + detalle;
                    break;
                }
            }
        }
        catch (Exception ex)
        {
            texto = "ACTUAL: (no se pudo leer la configuracion: " + ex.Message + ")";
        }
        componentesActuales.text = texto;
    }

    // ====================================================================
    // Aplicar: llama a Python y reconstruye la escena
    // ====================================================================
    void Aplicar()
    {
        try
        {
            if (gamas.Count == 0 || MontajesActuales().Count == 0
                || DetallesActuales().Count == 0)
            {
                throw new Exception("Catalogo de tipos de apoyo vacio.");
            }
            mensaje.text = "Procesando...";
            mensaje.color = Color.yellow;
            OptGama g = gamas[indiceGama];
            OptMontaje m = MontajesActuales()[indiceMontaje];
            OptDetalle d = DetallesActuales()[indiceDetalle];
            string json = "{\n"
                + "  \"excel\": \"" + Json.Esc(rutaExcel) + "\",\n"
                + "  \"utm\": \"" + Json.Esc(rutaUtm) + "\",\n"
                + "  \"salida_excel\": \"" + Json.Esc(rutaSalidaExcel) + "\",\n"
                + "  \"apoyo\": " + seleccionado + ",\n"
                + "  \"gama\": \"" + g.id + "\",\n"
                + "  \"montaje\": \"" + m.tipo + "\",\n"
                + "  \"detalle\": \"" + Json.Esc(d.id) + "\",\n"
                + "  \"numero_fases\": " + numeroFases + "\n"
                + "}";
            string rutaPeticion = Path.Combine(rutaPython, "peticion_tipo_apoyo.json");
            string rutaResultado = Path.Combine(rutaPython, "resultado_tipo_apoyo.json");
            File.WriteAllText(rutaPeticion, json, Json.Utf8SinBom);

            MotorHelper.EjecutarMotor("cambiar_tipo_apoyo",
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
                string gamaCambiada = doc.ContainsKey("cambio_gama")
                    && Convert.ToBoolean(doc["cambio_gama"])
                    ? "\nGama y armado actualizados." : "";
                string alturaCambiada = "";
                if (doc.ContainsKey("delta_altura_m")
                    && doc["delta_altura_m"] != null
                    && float.TryParse(doc["delta_altura_m"].ToString().Replace(',', '.'),
                        System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out float dAlt)
                    && dAlt > 0.001f)
                {
                    alturaCambiada = "\nAltura total subida +"
                        + dAlt.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture)
                        + " m\n(cota UTM, desniveles y tensiones actualizados).";
                }
                mensaje.text = "APOYO " + seleccionado + ":\n"
                    + g.nombre + " / " + m.nombre + "\n"
                    + d.etiqueta + gamaCambiada + alturaCambiada + "\n"
                    + "Excel y escena actualizados.";
                mensaje.color = new Color(0.4f, 1f, 0.5f);
                AvisarRecarga();
                SincronizarConActual();
                ActualizarLabels();
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
    // Seleccion desde el 3D: clic sobre el FUSTE de un apoyo
    // ====================================================================
    void Update()
    {
        if (!Input.GetMouseButtonDown(0)) return;
        if (EventSystem.current != null
            && EventSystem.current.IsPointerOverGameObject()) return;

        var cam = FindAnyObjectByType<Camera>();
        if (cam == null) return;
        AsegurarColisionadoresFuste();
        Ray rayo = cam.ScreenPointToRay(Input.mousePosition);
        if (Physics.Raycast(rayo, out RaycastHit hit, 1000f))
        {
            string nombre = hit.collider.transform.name;
            // Solo el fuste/cabeza abre este asistente; las semicrucetas las
            // gestiona la ventana de crucetas.
            if (nombre != "Cabeza" && !nombre.StartsWith("Cuerpo_"))
                return;
            int numero = NumeroApoyoDesde(hit.collider.transform);
            if (numero > 0) SeleccionarApoyoDesde3D(numero);
        }
    }

    public void SeleccionarApoyoDesde3D(int numero)
    {
        if (numero < 1 || numero > totalApoyos) return;
        MostrarApoyo(numero);
        if (ventana != null && !ventana.activeSelf) ventana.SetActive(true);
    }

    int NumeroApoyoDesde(Transform t)
    {
        while (t != null)
        {
            var match = System.Text.RegularExpressions.Regex.Match(
                t.name, @"^Apoyo_(\d+)__");
            if (match.Success) return int.Parse(match.Groups[1].Value);
            t = t.parent;
        }
        return -1;
    }

    void AsegurarColisionadoresFuste()
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
                    if (nombre != "Cabeza" && !nombre.StartsWith("Cuerpo_"))
                        continue; // solo fuste/cabeza
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
    // Creacion de la UI
    // ====================================================================
    void CrearCanvasYEventSystem()
    {
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var es = new GameObject("EventSystemTipoApoyo");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }
        var go = new GameObject("CanvasTipoApoyo");
        canvas = go.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 2000;
        go.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        go.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
        go.AddComponent<GraphicRaycaster>();
    }

    void CrearVentana()
    {
        var raiz = new GameObject("VentanaTipoApoyoUI");
        raiz.transform.SetParent(canvas.transform, false);
        var rtr = raiz.AddComponent<RectTransform>();
        rtr.anchorMin = Vector2.zero; rtr.anchorMax = Vector2.one;
        rtr.offsetMin = Vector2.zero; rtr.offsetMax = Vector2.zero;
        ventana = raiz;

        CrearImagen(raiz, "Fondo", new Vector2(0.5f, 0.5f),
            Vector2.zero, new Vector2(500, 650),
            new Color(0.08f, 0.1f, 0.16f, 0.97f));
        // X visible arriba a la derecha para volver al menu de Gemelo digital
        CrearBoton(raiz, "CerrarX", "X", new Vector2(0.5f, 0.5f),
            new Vector2(228, 296), new Vector2(40, 40), CerrarYVolver);

        pista = CrearTexto(raiz, "Pista", new Vector2(0.5f, 0.5f),
            new Vector2(0, 278), 13, TextAnchor.MiddleCenter);
        pista.rectTransform.sizeDelta = new Vector2(460, 32);
        pista.color = new Color(0.75f, 0.78f, 0.85f);
        pista.text = "Pulsa sobre el FUSTE de un apoyo en el 3D para seleccionarlo.";

        titulo = CrearTexto(raiz, "Titulo", new Vector2(0.5f, 0.5f),
            new Vector2(0, 230), 24, TextAnchor.MiddleCenter);
        titulo.rectTransform.sizeDelta = new Vector2(460, 42);

        // Desplegable de APOYOS (sustituye a las flechas < >)
        apoyoDropdown = UIFactory.CrearDropdown(raiz, "ApoyoDropdown",
            new Vector2(0.5f, 0.5f), new Vector2(0, 174), new Vector2(230, 38));
        for (int i = 1; i <= totalApoyos; i++)
            apoyoDropdown.options.Add(new Dropdown.OptionData("Apoyo " + i));
        apoyoDropdown.value = seleccionado - 1;
        apoyoDropdown.onValueChanged.AddListener(idx =>
        {
            if (!sincronizandoDropdown) MostrarApoyo(idx + 1);
        });

        // Componentes ACTUALES del apoyo (referencia fija)
        componentesActuales = CrearTexto(raiz, "Actuales", new Vector2(0.5f, 0.5f),
            new Vector2(0, 130), 12, TextAnchor.MiddleCenter);
        componentesActuales.rectTransform.sizeDelta = new Vector2(470, 24);
        componentesActuales.color = new Color(1f, 0.85f, 0.4f);

        CrearFila(raiz, "Gama", 75);
        CrearFila(raiz, "Tipo", 15);
        CrearFila(raiz, "Detalle", -45);

        CrearBoton(raiz, "Aplicar", "APLICAR TIPO", new Vector2(0.5f, 0.5f),
            new Vector2(0, -115), new Vector2(250, 52), Aplicar);

        mensaje = CrearTexto(raiz, "Mensaje", new Vector2(0.5f, 0.5f),
            new Vector2(0, -190), 15, TextAnchor.MiddleCenter);
        mensaje.rectTransform.sizeDelta = new Vector2(460, 110);
        mensaje.raycastTarget = false;

        CrearBoton(raiz, "Cerrar", "CERRAR", new Vector2(0.5f, 0.5f),
            new Vector2(0, -285), new Vector2(130, 42), CerrarVentana);
        // --- VISTA PREVIA 3D a la derecha (selector tipo videojuego) ---
        CrearImagen(raiz, "PanelPreview", new Vector2(0.5f, 0.5f),
            new Vector2(440, 10), new Vector2(340, 500),
            new Color(0.055f, 0.075f, 0.12f, 0.98f));
        CrearTexto(raiz, "TituloPreview", new Vector2(0.5f, 0.5f),
            new Vector2(440, 225), 15, TextAnchor.MiddleCenter).text =
            "VISTA PREVIA 3D";
        var rawGo = new GameObject("ImagenPreview");
        rawGo.transform.SetParent(raiz.transform, false);
        var rawRt = rawGo.AddComponent<RectTransform>();
        rawRt.anchorMin = new Vector2(0.5f, 0.5f);
        rawRt.anchorMax = new Vector2(0.5f, 0.5f);
        rawRt.pivot = new Vector2(0.5f, 0.5f);
        rawRt.anchoredPosition = new Vector2(440, 0);
        rawRt.sizeDelta = new Vector2(320, 430);
        var rawImage = rawGo.AddComponent<RawImage>();
        vistaPrevia = new VistaPrevia3D(rawImage, "CamaraPreviewTipoApoyo", 320, 430);

    }

    void CrearFila(GameObject padre, string tituloFila, float y)
    {
        // Etiqueta (GAMA / TIPO / DETALLE) pequena, alineada a la izquierda
        Text etiqueta = CrearTexto(padre, "Label_" + tituloFila,
            new Vector2(0.5f, 0.5f), new Vector2(-205, y), 15,
            TextAnchor.MiddleLeft);
        etiqueta.color = new Color(0.65f, 0.7f, 0.8f);
        etiqueta.text = tituloFila.ToUpper();
        etiqueta.rectTransform.sizeDelta = new Vector2(80, 26);

        // Valor actual centrado entre los botones < >
        if (tituloFila == "Gama") gamaLabel = CrearTexto(padre, "Valor_Gama",
            new Vector2(0.5f, 0.5f), new Vector2(0, y), 14, TextAnchor.MiddleCenter);
        if (tituloFila == "Tipo") montajeLabel = CrearTexto(padre, "Valor_Tipo",
            new Vector2(0.5f, 0.5f), new Vector2(0, y), 14, TextAnchor.MiddleCenter);
        if (tituloFila == "Detalle") detalleLabel = CrearTexto(padre, "Valor_Detalle",
            new Vector2(0.5f, 0.5f), new Vector2(0, y), 14, TextAnchor.MiddleCenter);

        if (tituloFila == "Gama") gamaLabel.rectTransform.sizeDelta = new Vector2(150, 30);
        else if (tituloFila == "Tipo") montajeLabel.rectTransform.sizeDelta = new Vector2(150, 30);
        else detalleLabel.rectTransform.sizeDelta = new Vector2(150, 30);

        if (tituloFila == "Gama")
        {
            CrearBoton(padre, "PrevGama", "<", new Vector2(0.5f, 0.5f),
                new Vector2(-108, y), new Vector2(42, 36), () => CambiarGama(-1));
            CrearBoton(padre, "NextGama", ">", new Vector2(0.5f, 0.5f),
                new Vector2(108, y), new Vector2(42, 36), () => CambiarGama(1));
        }
        else if (tituloFila == "Tipo")
        {
            CrearBoton(padre, "PrevTipo", "<", new Vector2(0.5f, 0.5f),
                new Vector2(-108, y), new Vector2(42, 36), () => CambiarMontaje(-1));
            CrearBoton(padre, "NextTipo", ">", new Vector2(0.5f, 0.5f),
                new Vector2(108, y), new Vector2(42, 36), () => CambiarMontaje(1));
        }
        else
        {
            CrearBoton(padre, "PrevDetalle", "<", new Vector2(0.5f, 0.5f),
                new Vector2(-108, y), new Vector2(42, 36), () => CambiarDetalle(-1));
            CrearBoton(padre, "NextDetalle", ">", new Vector2(0.5f, 0.5f),
                new Vector2(108, y), new Vector2(42, 36), () => CambiarDetalle(1));
        }
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






