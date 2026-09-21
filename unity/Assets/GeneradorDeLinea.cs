using UnityEngine;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq; // Necesario para buscar objetos

[System.Serializable]
public class EntradaModeloArmado
{
    public string modeloId;
    public GameObject prefab;
}

[System.Serializable]
public class DatosArmadoConfigurado
{
    public string modelo_id;
    public string referencia_origen;
    public string recurso_unity;
    public string familia;
    public float altura_cabeza_m;
    public float altura_modulo_m;
    public string recurso_modulo_a;
    public string recurso_modulo_b;
    public string primer_patron_bajo_cabeza;
}

[System.Serializable]
public class DatosMontajeConfigurado
{
    public string tipo;
    public string referencia_armado;
    public float separacion_vertical_m;
    public float altura_cupula_m;
    public int lado_inicial = 1;
}

[System.Serializable]
public class DatosCrucetaConfigurada
{
    public string modelo_id;
    public string tipo_origen;
    public string referencia_origen;
    public float a_m;
    public bool es_atirantada;
}

[System.Serializable]
public class DatosCaracteristicasCadena
{
    public float longitud_m;
    public float peso_daN;
    public float carga_rotura_daN;
    public float esfuerzo_viento_120_daN;
    public float esfuerzo_viento_140_daN;
    public float esfuerzo_viento_60_daN;
}

[System.Serializable]
public class DatosCadenaConfigurada
{
    public string nombre;
    public string denominacion;
    public string conductor;
    public int tension_kv;
    public string tipo;      // "SUS" (suspensión) o "ANC" (amarre/anclaje)
    public string material;  // "VID" o "POL"
    public bool doble;
    public int n_cadenas = 1;
    public DatosCaracteristicasCadena caracteristicas;
}

[System.Serializable]
public class DatosApoyoConfigurado
{
    public int numero;
    public float altura_total_m;
}

[System.Serializable]
public class ApoyoConfigurado
{
    public string apoyo_id;
    public DatosArmadoConfigurado armado;
    public DatosApoyoConfigurado apoyo;
    public DatosMontajeConfigurado montaje;
    public DatosCrucetaConfigurada cruceta;
    public string tipo_clave;
    public string tipo_texto;
    public string coef_seguridad;
    public DatosCadenaConfigurada cadena;
}

[System.Serializable]
public class DocumentoApoyosConfigurados
{
    public ApoyoConfigurado[] apoyos;
}

// Geometría de las cadenas de un apoyo (una por fase): extremos inferiores
// hacia el vano anterior (izquierda) y hacia el vano siguiente (derecha).
// Son puntos reales del cable sobre los que se cuelga el conductor.
public class PuntosCadenasApoyo
{
    public Vector3[] izquierda = new Vector3[0];
    public Vector3[] derecha = new Vector3[0];
    public bool suspension;
}

[System.Serializable]
public class DatosConductorConfigurado
{
    public string nomenclatura_excel;
    public string designacion;
    public string composicion;
    public float diametro_mm;
    public float diametro_m;
    public float seccion_mm2;
    public float masa_kg_km;
    public float peso_daN_m;
    public float modulo_elasticidad_daN_mm2;
    public float coef_dilatacion_1_C;
    public bool propiedades_mecanicas_verificadas;
    public string fuente_propiedades_mecanicas;
    public int numero_fases = 3;
    // --- Campos eléctricos para el DLR (enriquecidos por principal.py) ---
    public double r_low_ohm_km = 0.0;
    public double r_high_ohm_km = 0.0;
    public double t_low_C = 25.0;
    public double t_high_C = 70.0;
    public double emisividad = 0.8;
    public double absortividad = 0.8;
    public double t_limite_C = 0.0;
    public string fuente_resistencias;
}

[System.Serializable]
public class EstadoMecanicoExcel
{
    public float temperatura_C;
    public float tension_daN;
    public float flecha_m;
    public float tension_invertida_daN;
    public float diferencia_inversion_pct;
}

[System.Serializable]
public class VanoMecanico
{
    public int indice;
    public string tramo;
    public int canton_id;
    public int fila_excel;
    public float a_utm_m;
    public float h_cotas_m;
    public float a_excel_m;
    public float h_excel_m;
    public float vano_regulacion_excel_m;
    public float temperatura_referencia_C;
    public float tension_referencia_daN;
    public float flecha_referencia_m;
    public EstadoMecanicoExcel[] estados_excel;
}

[System.Serializable]
public class CantonMecanico
{
    public int id;
    public int[] vanos;
    public float temperatura_referencia_C;
    public float tension_referencia_daN;
}

[System.Serializable]
public class PropiedadesMecanicasConductor
{
    public string designacion;
    public string composicion;
    public float seccion_mm2;
    public float masa_kg_km;
    public float peso_daN_m;
    public float modulo_elasticidad_daN_mm2;
    public float coef_dilatacion_1_C;
    public bool propiedades_mecanicas_verificadas;
    public string fuente_propiedades_mecanicas;
}

[System.Serializable]
public class DocumentoFisicaLinea
{
    public int version_esquema;
    public string fuente_excel;
    public string hoja;
    public string hipotesis;
    public string criterio_cantones;
    public PropiedadesMecanicasConductor propiedades_conductor;
    public CantonMecanico[] cantones;
    public VanoMecanico[] vanos;
    public string[] avisos;
}

public class ModeloCantonFase
{
    public int cantonId;
    public int fase;
    public double vanoRegulacionM;
    public double temperaturaReferenciaC;
    public double tensionReferenciaDaN;
}

[ExecuteAlways]
public class GeneradorDeLinea : MonoBehaviour
{
    // Factor exclusivamente visual. El diámetro físico almacenado en
    // conductorConfigurado se mantiene intacto para todos los cálculos.
    private const float MultiplicadorDiametroVisual = 8f;

    [Header("Archivos de Datos (desde Python)")]
    public string csvApoyos = "coordenadas_linea.csv";
    public string csvInfoTerreno = "info_terreno.csv";
    public string jsonFisica = "fisica_linea.json";
    public string jsonApoyosConfigurados = "apoyos_configurados.json";
    public string jsonConductorConfigurado = "conductor_configurado.json";
    public string imagenRelieve = "terreno_real.png";
    public string imagenTextura = "textura_real.jpg";

    [Header("Referencias Unity")]
    public Terrain terrenoUnity;
    [Tooltip("Opcional: permite sustituir manualmente un modelo cargado desde Resources.")]
    public List<EntradaModeloArmado> modelosArmado = new List<EntradaModeloArmado>();
    public Material materialCable;
    [Tooltip("Color de los tres conductores de fase (rosa fosforito por defecto).")]
    public Color colorConductorCable = new Color(1f, 0f, 0.6f);

    [Header("Parámetros Eléctricos")]
    public float alturaCruceta = 20.0f;
    public float grosorCable = 0.15f;

    [Header("Orientación de crucetas y bóvedas")]
    [Tooltip("Giro de las semicrucetas PLANAS (ASC) alrededor de su eje de "
        + "simetría (eje X local, el brazo) para dejar la cara plana horizontal.")]
    public float giroSemicruceta = 90f;
    [Tooltip("Giro de las bóvedas (BH/BF/BT) en sentido antihorario respecto "
        + "al eje perpendicular a su eje de simetría, para alinearlas con el apoyo.")]
    public float giroBoveda = -90f;
    // Quitamos 'parametroCatenaria' estático porque ahora se lee del CSV

    [Header("Control Gemelo Digital (Temperatura)")]
    [Tooltip("Temperatura continua del conductor en grados Celsius.")]
    public float temperaturaVisualizacion = 15f;
    [Tooltip("Muestra tension, flecha y desnivel real de cada fase en la consola.")]
    public bool mostrarDiagnosticoMecanico = true;
    public bool actualizarCablesRapido = false; // Botón para ver el cambio instantáneo

    [Header("Gemelo Digital DLR (Corriente admisible)")]
    [Tooltip("Activa el cálculo de la corriente máxima admisible según IEEE 738.")]
    public bool activarDLR = true;
    [Tooltip("Temperatura ambiente actual (°C).")]
    public float dlrTaC = 30f;
    [Tooltip("Velocidad del viento (m/s).")]
    public float dlrVwMs = 2f;
    [Tooltip("Dirección del viento (grados, desde el Norte).")]
    public float dlrDirVientoDeg = 90f;
    [Tooltip("Altitud media del terreno (m). Se calcula de las cotas si no se cambia.")]
    public float dlrAltitudM = 555f;
    [Tooltip("Latitud (grados, positiva = Norte).")]
    public float dlrLatitudDeg = 37.94f;
    [Tooltip("Acimut de la línea (grados desde el Norte). Se calcula de los apoyos si no se cambia.")]
    public float dlrAzimutLineaDeg = 185f;
    [Tooltip("Fecha del escenario (formato YYYY-MM-DD).")]
    public string dlrFecha = "2025-06-21";
    [Tooltip("Hora solar (12 = mediodía).")]
    public float dlrHoraSolar = 12f;
    [Tooltip("Temperatura máxima admisible del conductor (°C). 50 para cat. no especial, 85 para especial.")]
    public float dlrTsC = 50f;
    [Tooltip("Corriente máxima admisible calculada (A) — solo lectura.")]
    public float dlrCorrienteMaximaA = 0f;
    [Tooltip("Muestra todos los intermedios DLR en la consola.")]
    public bool dlrMostrarDiagnostico = false;
    public bool dlrCalcularAhora = false; // Botón para forzar recálculo

    [Header("Cadenas de Aisladores")]
    [Tooltip("Instala las cadenas: verticales en apoyos de suspensión, y siguiendo la dirección del cable en amarre/anclaje.")]
    public bool mostrarCadenas = true;
    [Tooltip("Prefijo de Resources de los modelos de cadena (FBX). Se completa con '<mm>mm'.")]
    public string rutaModelosCadenas = "ModelosCadenas/Cadena_";
    [Tooltip("Modelo de respaldo si el apoyo no tiene cadena configurada.")]
    public string modeloCadenaPorDefecto = "ModelosCadenas/Cadena_447mm";
    [Tooltip("Longitud de respaldo (m) si no se dispone de la cadena configurada.")]
    public float longitudCadenaPorDefecto = 0.447f;

    [Header("Herramientas")]
    [Tooltip("Reconstruye apoyos, crucetas y cables al entrar en modo Play.")]
    public bool construirAlIniciar = true;
    public bool generarTodoAhora = false;

    [Header("DLR Operativo (meteorología real)")]
    [Tooltip("Servicio que adquiere y valida la meteorología. No realiza el cálculo DLR.")]
    public ServicioMeteorologiaDLR servicioMeteorologia;
    [Tooltip("Si se activa, sobreescribe los campos DLR con la meteorología del JSON automáticamente.")]
    public bool dlrUsarMeteorologiaJSON = true;
    [Tooltip("Permite usar datos OBSOLETOS/FALLBACK solo para demostración. No recomendado para operación.")]
    public bool dlrAceptarDatosNoValidos = false;
    [Header("Estado meteorológico DLR (solo lectura)")]
    public string dlrEstadoMeteorologia = "SIN_DATOS";
    public bool dlrDatosMeteorologicosValidos = false;
    public float dlrAntiguedadMeteorologiaMin = -1f;
    public string dlrMensajeMeteorologia = "";

    private DocumentoFisicaLinea fisicaLinea;
    private Dictionary<int, VanoMecanico> vanosMecanicos =
        new Dictionary<int, VanoMecanico>();
    private Dictionary<string, ModeloCantonFase> modelosCantonFase =
        new Dictionary<string, ModeloCantonFase>();
    private Dictionary<int, ApoyoConfigurado> apoyosConfigurados =
        new Dictionary<int, ApoyoConfigurado>();
    private DatosConductorConfigurado conductorConfigurado;
    private bool mostrarCadenasAnterior = true;
    private bool escenaVerificada = false;
    private Dictionary<int, PuntosCadenasApoyo[]> cadenasApoyo =
        new Dictionary<int, PuntosCadenasApoyo[]>();

    void OnEnable()
    {
        escenaVerificada = false;
    }

    void Awake()
    {
        if (servicioMeteorologia == null)
            servicioMeteorologia = GetComponent<ServicioMeteorologiaDLR>();
        if (servicioMeteorologia != null)
            servicioMeteorologia.Actualizada += AlActualizarMeteorologia;
    }

    void OnDestroy()
    {
        if (servicioMeteorologia != null)
            servicioMeteorologia.Actualizada -= AlActualizarMeteorologia;
    }

    void Start()
    {
        if (Application.isPlaying && construirAlIniciar) {
            ConstruirEscenaCompleta();
        }
    }
    void Update()
    {
        #if UNITY_EDITOR
        // Modo edición: al abrir una escena que ya tenía apoyos guardados pero
        // aún sin cadenas (construida antes de la función de cadenas), las
        // instala automáticamente en el primer frame, sin pulsar nada.
        if (!Application.isPlaying && !escenaVerificada)
        {
            escenaVerificada = true;
            UnityEditor.EditorApplication.delayCall += GarantizarCadenasEnEscena;
        }
        #endif
    }


    void AlActualizarMeteorologia(ServicioMeteorologiaDLR.InstantaneaMeteorologica datos)
    {
        if (!activarDLR || !dlrUsarMeteorologiaJSON || datos == null) return;

        dlrEstadoMeteorologia = datos.estado;
        dlrDatosMeteorologicosValidos = datos.datosValidos;
        dlrAntiguedadMeteorologiaMin = datos.antiguedadMin;
        dlrMensajeMeteorologia = datos.mensaje;

        if (!datos.datosValidos && !dlrAceptarDatosNoValidos) {
            dlrCorrienteMaximaA = 0f;
            Debug.LogWarning(
                $"DLR meteorología {datos.estado}: {datos.mensaje} No se aplicará al cálculo."
            );
            return;
        }

        dlrTaC = datos.temperaturaAmbienteC;
        dlrVwMs = datos.velocidadVientoMs;
        if (datos.direccionVientoDeg >= 0f) dlrDirVientoDeg = datos.direccionVientoDeg;
        if (!string.IsNullOrEmpty(datos.fecha)) dlrFecha = datos.fecha;
        if (datos.altitudM > 0f) dlrAltitudM = datos.altitudM;
        if (datos.latLineaDeg != 0f) dlrLatitudDeg = datos.latLineaDeg;
        if (datos.versionEsquema >= 2) {
            dlrAzimutLineaDeg = datos.azimutLineaDeg;
            dlrTsC = datos.temperaturaLimiteC;
            dlrHoraSolar = datos.horaSolar;
        }

        if (conductorConfigurado != null) CalcularYMostrarDLR();
    }

    void OnValidate() {
        #if UNITY_EDITOR
        if (generarTodoAhora) {
            generarTodoAhora = false;
            UnityEditor.EditorApplication.delayCall += ConstruirEscenaCompleta;
        }
        if (actualizarCablesRapido) {
            actualizarCablesRapido = false;
            UnityEditor.EditorApplication.delayCall += SoloRedibujarCables;
        }
        if (mostrarCadenasAnterior != mostrarCadenas) {
            // El toggle de cadenas actúa al instante: redibuja (instala o quita
            // las cadenas según el estado del interruptor).
            mostrarCadenasAnterior = mostrarCadenas;
            UnityEditor.EditorApplication.delayCall += SoloRedibujarCables;
        }
        if (dlrCalcularAhora) {
            dlrCalcularAhora = false;
            UnityEditor.EditorApplication.delayCall += CalcularYMostrarDLR;
        }
        #endif
    }

    void CalcularYMostrarDLR()
    {
        if (!activarDLR) return;
        CargarConductorConfigurado(); // refresca por si se modificó el JSON externamente
        if (conductorConfigurado == null) {
            Debug.LogError("DLR: no hay conductor configurado con resistencias eléctricas.");
            return;
        }
        if (conductorConfigurado.r_low_ohm_km <= 0.0 || conductorConfigurado.r_high_ohm_km <= 0.0) {
            Debug.LogWarning(
                "DLR: las resistencias eléctricas no están disponibles en conductor_configurado.json. "
                + "Ejecuta principal.py para enriquecer el conductor."
            );
            return;
        }

        MotorDLR.EntradasDLR ent = new MotorDLR.EntradasDLR
        {
            diametro_mm = conductorConfigurado.diametro_mm,
            seccion_mm2 = conductorConfigurado.seccion_mm2,
            r_low_ohm_km = conductorConfigurado.r_low_ohm_km,
            r_high_ohm_km = conductorConfigurado.r_high_ohm_km,
            t_low_C = conductorConfigurado.t_low_C,
            t_high_C = conductorConfigurado.t_high_C,
            emisividad = conductorConfigurado.emisividad,
            absortividad = conductorConfigurado.absortividad,
            ta_C = dlrTaC,
            vw_m_s = dlrVwMs,
            direccion_viento_deg = dlrDirVientoDeg,
            he_m = dlrAltitudM,
            lat_deg = dlrLatitudDeg,
            zl_deg = dlrAzimutLineaDeg,
            fecha = dlrFecha,
            hora_solar = dlrHoraSolar,
            ts_C = dlrTsC
        };

        MotorDLR.ResultadoDLR res = MotorDLR.Calcular(ent);
        if (res.error != null) {
            Debug.LogError("DLR error: " + res.error);
            return;
        }

        dlrCorrienteMaximaA = (float)res.i_max_A;

        Debug.Log(
            $"⚡ DLR: I_max = {res.i_max_A:F2} A   (Ts={dlrTsC:F0} °C, Ta={dlrTaC:F0} °C, "
            + $"viento {dlrVwMs:F1} m/s @ {dlrDirVientoDeg:F0}°, "
            + $"qc={res.qc_W_m:F2}, qr={res.qr_W_m:F2}, qs={res.qs_W_m:F2} W/m)"
        );

        if (dlrMostrarDiagnostico) {
            Debug.Log($"   R(Tavg) = {res.r_tavg_ohm_km:F6} ohm/km, Tfilm = {res.tfilm_C:F1} °C");
            Debug.Log($"   Reynolds = {res.reynolds:F1}, Kangle = {res.kangle:F4}");
            Debug.Log($"   qcn={res.qcn_W_m:F2}, qc1={res.qc1_W_m:F2}, qc2={res.qc2_W_m:F2} W/m");
            Debug.Log($"   Solar: Hc={res.altitud_solar_hc_deg:F2}°, Zc={res.acimut_solar_zc_deg:F2}°, "
                     + $"theta={res.theta_incidencia_deg:F2}°, Qs={res.qs_nivel_mar_W_m2:F1} W/m²");
        }
    }

    [ContextMenu("🌍 Construir Escena Completa")]
    public void ConstruirEscenaCompleta()
    {
        CacheCatalogos.InvalidarDinamicos(); // los listados cacheados se refrescan
        LimpiarEscena();
        CargarFisica(); // Cargamos las tensiones primero
        CargarApoyosConfigurados();
        CargarConductorConfigurado();
        ConfigurarGeografia();
        GenerarApoyosYCables();
        if (dlrUsarMeteorologiaJSON && servicioMeteorologia != null
            && servicioMeteorologia.TieneLectura)
            AlActualizarMeteorologia(servicioMeteorologia.DatosActuales);
        else
            CalcularYMostrarDLR();
    }

    void CargarConductorConfigurado()
    {
        string ruta = Path.Combine(RutasGemelo.RutaAssetsGemelo(), jsonConductorConfigurado);
        if (!File.Exists(ruta)) {
            conductorConfigurado = null;
            Debug.LogError("No se encontró la configuración del conductor: " + ruta);
            return;
        }
        conductorConfigurado =
            JsonUtility.FromJson<DatosConductorConfigurado>(File.ReadAllText(ruta));
        if (conductorConfigurado == null || conductorConfigurado.diametro_m <= 0f) {
            Debug.LogError("La configuración del conductor no contiene un diámetro válido.");
            conductorConfigurado = null;
        }
    }

    void CargarApoyosConfigurados()
    {
        apoyosConfigurados.Clear();
        string ruta = Path.Combine(RutasGemelo.RutaAssetsGemelo(), jsonApoyosConfigurados);
        if (!File.Exists(ruta)) {
            Debug.LogError("No se encontró la configuración de apoyos: " + ruta);
            return;
        }

        DocumentoApoyosConfigurados documento =
            JsonUtility.FromJson<DocumentoApoyosConfigurados>(File.ReadAllText(ruta));
        if (documento == null || documento.apoyos == null) {
            Debug.LogError("El JSON de apoyos configurados no tiene un formato válido.");
            return;
        }

        foreach (ApoyoConfigurado configuracion in documento.apoyos) {
            if (configuracion != null && configuracion.apoyo != null) {
                apoyosConfigurados[configuracion.apoyo.numero] = configuracion;
            }
        }
    }

    GameObject BuscarPrefabArmado(DatosArmadoConfigurado armado)
    {
        EntradaModeloArmado entrada = modelosArmado.FirstOrDefault(
            item => item != null && item.modeloId == armado.modelo_id
        );
        if (entrada != null && entrada.prefab != null) return entrada.prefab;

        if (!string.IsNullOrWhiteSpace(armado.recurso_unity)) {
            return Resources.Load<GameObject>(armado.recurso_unity);
        }
        return null;
    }

    GameObject CargarModulo(DatosArmadoConfigurado armado, string patron)
    {
        string ruta = patron == "A"
            ? armado.recurso_modulo_a
            : armado.recurso_modulo_b;
        return string.IsNullOrWhiteSpace(ruta)
            ? null
            : Resources.Load<GameObject>(ruta);
    }

    string PatronModulo(DatosArmadoConfigurado armado, int indiceDesdeCabeza)
    {
        bool primeroEsA = armado.primer_patron_bajo_cabeza == "A";
        bool usarA = indiceDesdeCabeza % 2 == 0 ? primeroEsA : !primeroEsA;
        return usarA ? "A" : "B";
    }

    GameObject CrearApoyoCompleto(
        ApoyoConfigurado configuracion,
        Vector3 posicion,
        Quaternion rotacion
    )
    {
        DatosArmadoConfigurado armado = configuracion.armado;
        GameObject prefabCabeza = BuscarPrefabArmado(armado);
        GameObject moduloA = CargarModulo(armado, "A");
        GameObject moduloB = CargarModulo(armado, "B");

        if (prefabCabeza == null || moduloA == null || moduloB == null) {
            Debug.LogError(
                $"Faltan recursos de cabeza o cuerpo para {armado.modelo_id}."
            );
            return null;
        }
        if (armado.altura_cabeza_m <= 0f || armado.altura_modulo_m <= 0f) {
            Debug.LogError($"Dimensiones modulares no válidas para {armado.modelo_id}.");
            return null;
        }

        float alturaTotal = configuracion.apoyo.altura_total_m;
        float alturaCuerpo = alturaTotal - armado.altura_cabeza_m;
        if (alturaCuerpo < -0.001f) {
            Debug.LogError(
                $"El apoyo {configuracion.apoyo.numero} mide {alturaTotal} m, "
                + $"menos que su cabeza de {armado.altura_cabeza_m} m."
            );
            return null;
        }
        alturaCuerpo = Mathf.Max(0f, alturaCuerpo);

        GameObject raiz = new GameObject(
            $"Apoyo_{configuracion.apoyo.numero}__{armado.modelo_id}"
        );
        raiz.transform.SetPositionAndRotation(posicion, rotacion);
        raiz.transform.SetParent(this.transform, true);

        bool esBoveda = EsMontajeBoveda(configuracion.montaje);

        if (esBoveda)
        {
            // BOVEDA: la boveda sustituye a la cabeza. Se monta PRIMERO la
            // boveda con su tope en la altura total del apoyo y DESPUES se
            // construye el fuste con modulos normales hasta la BASE de la
            // boveda (su punto mas bajo). Asi el ultimo modulo encaja en la
            // zona inferior del montaje: fuste -> ultimo modulo -> boveda,
            // sin cabeza intermedia, sin hueco y sin solapamientos.
            MontarCrucetasAndel(raiz, configuracion, alturaTotal);
            float yBaseBoveda = ObtenerBaseBoveda(raiz);
            if (yBaseBoveda <= 0f) yBaseBoveda = alturaCuerpo; // sin bóveda: fuste normal
            // Un módulo MÁS encima del resto: el último módulo sube un módulo
            // completo por encima de la base de la bóveda y queda encajado en
            // la zona inferior del montaje.
            ConstruirFuste(raiz, armado, moduloA, moduloB,
                Mathf.Max(0f, yBaseBoveda) + armado.altura_modulo_m);
        }
        else
        {
            ConstruirFuste(raiz, armado, moduloA, moduloB, alturaCuerpo);

            GameObject cabeza = Instantiate(prefabCabeza, raiz.transform, false);
            cabeza.name = "Cabeza";
            cabeza.transform.localPosition = Vector3.up * alturaCuerpo;
            float alturaSuperiorVisual = alturaTotal;
            if (TryObtenerLimitesLocales(raiz, raiz.transform, out Bounds limitesApoyo)) {
                alturaSuperiorVisual = limitesApoyo.max.y;
            }
            MontarCrucetasAndel(raiz, configuracion, alturaSuperiorVisual);
        }
        CrearPuntosConexionConductores(raiz, configuracion);
        return raiz;
    }

    /// <summary>Construye el fuste modular (celdas enteras A/B) hasta la altura
    /// 'alturaFuste': se usan siempre celdas completas y, si la altura no es un
    /// múltiplo exacto del módulo, el sobrante de la celda inferior se entierra
    /// bajo la cota cero, de modo que el TOPE del fuste coincide exactamente
    /// con 'alturaFuste' (la base de la boveda en el caso de los montajes de
    /// boveda). Devuelve el numero de celdas creadas.</summary>
    int ConstruirFuste(GameObject raiz, DatosArmadoConfigurado armado,
                       GameObject moduloA, GameObject moduloB, float alturaFuste)
    {
        int numeroModulos = Mathf.CeilToInt(
            Mathf.Max(0f, alturaFuste - 0.0001f) / armado.altura_modulo_m
        );
        float alturaModulos = numeroModulos * armado.altura_modulo_m;
        float enterramiento = Mathf.Max(0f, alturaModulos - alturaFuste);
        float yActual = -enterramiento;
        int creados = 0;
        for (int indiceInferior = 0; indiceInferior < numeroModulos; indiceInferior++) {
            int indiceDesdeCabeza = numeroModulos - 1 - indiceInferior;
            string patron = PatronModulo(armado, indiceDesdeCabeza);
            GameObject prefabModulo = patron == "A" ? moduloA : moduloB;
            GameObject celda = Instantiate(prefabModulo, raiz.transform, false);
            celda.name = $"Cuerpo_{indiceInferior + 1:000}_{patron}";
            celda.transform.localPosition = Vector3.up * yActual;
            yActual += armado.altura_modulo_m;
            creados++;
        }
        return creados;
    }

    /// <summary>Punto mas bajo de la boveda en coordenadas LOCALES del apoyo
    /// (donde el area lateral de la boveda se ancla): es la altura a la que
    /// debe llegar el ultimo modulo del fuste para encajar sin huecos ni
    /// flotar. Si no hay boveda, devuelve 0.</summary>
    float ObtenerBaseBoveda(GameObject raiz)
    {
        float minY = float.PositiveInfinity;
        foreach (Transform hijo in raiz.transform)
        {
            if (!EsNombreBoveda(hijo.name)) continue;
            var pila = new Stack<Transform>();
            pila.Push(hijo);
            while (pila.Count > 0)
            {
                var t = pila.Pop();
                var r = t.GetComponent<Renderer>();
                if (r != null)
                {
                    Vector3 localMin = raiz.transform.InverseTransformPoint(r.bounds.min);
                    minY = Mathf.Min(minY, localMin.y);
                }
                foreach (Transform sub in t) pila.Push(sub);
            }
        }
        return float.IsPositiveInfinity(minY) ? 0f : minY;
    }

    bool EsNombreBoveda(string nombre)
    {
        if (string.IsNullOrEmpty(nombre)) return false;
        return nombre.StartsWith("BH") || nombre.StartsWith("BF")
            || nombre.StartsWith("BT") || nombre.StartsWith("C_BH")
            || nombre.StartsWith("C_BF") || nombre.StartsWith("C_BT");
    }

    bool Cerca(float valor, float objetivo)
    {
        return Mathf.Abs(valor - objetivo) <= 0.002f;
    }

    bool EsMontajeBoveda(DatosMontajeConfigurado montaje)
    {
        if (montaje == null) return false;
        return montaje.tipo == "BOVEDA_CAPA"
            || montaje.tipo == "BOVEDA_PICO"
            || montaje.tipo == "BOVEDA_TRIANGULO";
    }

    bool RequiereVarianteAltura(string referenciaBase)
    {
        if (string.IsNullOrWhiteSpace(referenciaBase)) return false;
        return referenciaBase.StartsWith("ATC")
            || referenciaBase.StartsWith("BH")
            || referenciaBase.StartsWith("BF")
            || referenciaBase.StartsWith("BT");
    }

    string ResolverReferenciaCompatible(
        string referenciaBase,
        string familiaArmado,
        float alturaLocal,
        float yTop,
        out string error
    )
    {
        error = null;
        if (!RequiereVarianteAltura(referenciaBase)) return referenciaBase;

        int indiceSufijo = referenciaBase.LastIndexOf("_H");
        if (indiceSufijo >= 0) referenciaBase = referenciaBase.Substring(0, indiceSufijo);

        float distanciaDesdeArriba = yTop - alturaLocal;
        if (familiaArmado == "M60") {
            float panel = distanciaDesdeArriba / 0.600f;
            if (distanciaDesdeArriba < -0.002f || !Cerca(panel, Mathf.Round(panel))) {
                error = $"la altura local {alturaLocal:F3} no coincide con un panel M60 H600";
                return null;
            }
            return referenciaBase + "_H600";
        }

        if (familiaArmado == "M50") {
            if (Cerca(distanciaDesdeArriba, 0.000f)) return referenciaBase + "_H750";
            if (Cerca(distanciaDesdeArriba, 0.750f)
                || Cerca(distanciaDesdeArriba, 1.125f)) {
                return referenciaBase + "_H375";
            }
            if (Cerca(distanciaDesdeArriba, 1.500f)
                || Cerca(distanciaDesdeArriba, 2.000f)
                || Cerca(distanciaDesdeArriba, 2.500f)
                || Cerca(distanciaDesdeArriba, 3.000f)) {
                return referenciaBase + "_H500";
            }
            error = $"la altura local {alturaLocal:F3} no coincide con un panel M50 H750/H375/H500";
            return null;
        }

        error = $"la familia {familiaArmado} no admite variantes de acople ANDEL";
        return null;
    }

    bool InstanciarCruceta(
        GameObject raiz,
        ApoyoConfigurado configuracion,
        string referenciaBase,
        float alturaLocal,
        float yTop,
        int lado,
        bool centrada
    )
    {
        string referencia = ResolverReferenciaCompatible(
            referenciaBase,
            configuracion.armado.familia,
            alturaLocal,
            yTop,
            out string errorVariante
        );
        if (referencia == null) {
            Debug.LogError(
                $"Apoyo {configuracion.apoyo.numero}, referencia {referenciaBase}: {errorVariante}."
            );
            return false;
        }

        string nombreRecurso = referencia.Replace("/", "_").Replace("\\", "_");
        string ruta = "ModelosCruceta/" + nombreRecurso;
        GameObject prefab = Resources.Load<GameObject>(ruta);
        if (prefab == null) {
            Debug.LogError(
                $"Apoyo {configuracion.apoyo.numero}: referencia inexistente en prefabs: {referencia} ({ruta})."
            );
            return false;
        }

        GameObject pieza = Instantiate(prefab, raiz.transform, false);
        pieza.name = referencia;
        Quaternion rotacionLado = centrada || lado >= 0
            ? Quaternion.identity
            : Quaternion.Euler(0f, 180f, 0f);
        Quaternion rotacionBase = configuracion.cruceta.es_atirantada
            ? ResolverRotacionAtirantada(pieza, raiz.transform, rotacionLado)
            : rotacionLado;
        // Giro propio de cada familia: las semicrucetas planas quedan con la
        // cara horizontal y las bovedas alineadas con el apoyo (se aplica
        // despues de la orientacion lateral, por eso se multiplica a la derecha).
        pieza.transform.localRotation = rotacionBase * GiroExtra(referencia);
        pieza.transform.localPosition = Vector3.zero;

        // Alineación visual genérica: el punto más alto real del FBX coincide
        // con la cota del nivel. No depende del origen, del catálogo ni de una
        // altura H concreta, por lo que sirve para todas las familias.
        if (TryObtenerLimitesLocales(pieza, raiz.transform, out Bounds limitesPieza)) {
            pieza.transform.localPosition = Vector3.up * (alturaLocal - limitesPieza.max.y);
        } else {
            pieza.transform.localPosition = Vector3.up * alturaLocal;
        }
        return true;
    }

    /// <summary>Giro adicional de cada familia de cruceta (se aplica en el
    /// eje X local, que es el eje longitudinal del brazo):
    ///   - Semicrucetas PLANAS (ASC): 90 grados alrededor de SU EJE DE
    ///     SIMETRIA -> la cara triangular plana pasa a horizontal.
    ///   - Bovedas (BH/BF/BT): 90 grados antihorario alrededor del eje
    ///     perpendicular a su eje de simetria -> quedan alineadas con el
    ///     apoyo y sus conductores pasan por los extremos y el centro.
    /// Ambos valores se pueden ajustar desde el Inspector del GeneradorDeLinea
    /// (giroSemicruceta / giroBoveda) sin recompilar.</summary>
    Quaternion GiroExtra(string referencia)
    {
        bool esBoveda = referencia.StartsWith("BH")
            || referencia.StartsWith("BF")
            || referencia.StartsWith("BT")
            || referencia.StartsWith("C_BH")
            || referencia.StartsWith("C_BF")
            || referencia.StartsWith("C_BT");
        bool esPlana = referencia.StartsWith("ASC")
            || referencia.StartsWith("C_ASC");
        if (esBoveda) return Quaternion.Euler(giroBoveda, 0f, 0f);
        if (esPlana) return Quaternion.Euler(giroSemicruceta, 0f, 0f);
        return Quaternion.identity;
    }

    Quaternion ResolverRotacionAtirantada(
        GameObject pieza,
        Transform referencia,
        Quaternion rotacionLado
    )
    {
        Quaternion mejorRotacion = rotacionLado;
        float mejorPuntuacion = float.PositiveInfinity;

        // Se prueban los cuatro giros posibles alrededor del eje longitudinal.
        // El correcto deja el modelo centrado en profundidad y sitúa la punta
        // en el plano inferior, de modo que la cara triangular plana mira abajo.
        foreach (float giro in new float[] { 0f, 90f, 180f, 270f }) {
            Quaternion candidata = rotacionLado * Quaternion.Euler(giro, 0f, 0f);
            pieza.transform.localRotation = candidata;
            pieza.transform.localPosition = Vector3.zero;

            if (!TryObtenerLimitesLocales(pieza, referencia, out Bounds limites)
                || !TryObtenerAlturaPunta(pieza, referencia, out float alturaPunta)) {
                continue;
            }

            float descentramientoLateral = Mathf.Abs(limites.center.z);
            float puntaSobreBase = Mathf.Abs(alturaPunta - limites.min.y);
            float puntuacion = descentramientoLateral * 20f + puntaSobreBase * 5f;
            if (puntuacion < mejorPuntuacion) {
                mejorPuntuacion = puntuacion;
                mejorRotacion = candidata;
            }
        }
        return mejorRotacion;
    }

    bool TryObtenerAlturaPunta(
        GameObject objeto,
        Transform referencia,
        out float alturaPunta
    )
    {
        List<Vector3> vertices = ObtenerVerticesLocales(objeto, referencia);
        if (vertices.Count == 0) {
            alturaPunta = 0f;
            return false;
        }

        float xMaximo = vertices.Max(vertice => Mathf.Abs(vertice.x));
        List<Vector3> verticesPunta = vertices
            .Where(vertice => Mathf.Abs(vertice.x) >= xMaximo - 0.06f)
            .ToList();
        alturaPunta = verticesPunta.Average(vertice => vertice.y);
        return true;
    }

    bool TryObtenerLimitesLocales(
        GameObject objeto,
        Transform referencia,
        out Bounds limites
    )
    {
        Renderer[] renderers = objeto.GetComponentsInChildren<Renderer>(true);
        if (renderers.Length == 0) {
            limites = new Bounds();
            return false;
        }

        bool inicializado = false;
        limites = new Bounds();
        foreach (Renderer rendererPieza in renderers) {
            Bounds mundo = rendererPieza.bounds;
            Vector3 minimo = mundo.min;
            Vector3 maximo = mundo.max;
            for (int x = 0; x <= 1; x++) {
                for (int y = 0; y <= 1; y++) {
                    for (int z = 0; z <= 1; z++) {
                        Vector3 esquinaMundo = new Vector3(
                            x == 0 ? minimo.x : maximo.x,
                            y == 0 ? minimo.y : maximo.y,
                            z == 0 ? minimo.z : maximo.z
                        );
                        Vector3 esquinaLocal = referencia.InverseTransformPoint(esquinaMundo);
                        if (!inicializado) {
                            limites = new Bounds(esquinaLocal, Vector3.zero);
                            inicializado = true;
                        } else {
                            limites.Encapsulate(esquinaLocal);
                        }
                    }
                }
            }
        }
        return inicializado;
    }

    List<Vector3> ObtenerVerticesLocales(GameObject objeto, Transform referencia)
    {
        List<Vector3> vertices = new List<Vector3>();
        foreach (MeshFilter filtro in objeto.GetComponentsInChildren<MeshFilter>(true)) {
            if (filtro.sharedMesh == null) continue;
            if (!filtro.sharedMesh.isReadable) {
                Debug.LogError(
                    $"El FBX '{filtro.sharedMesh.name}' no tiene Read/Write activado. "
                    + "No se pueden calcular sus puntos de conexión."
                );
                continue;
            }
            foreach (Vector3 vertice in filtro.sharedMesh.vertices) {
                vertices.Add(
                    referencia.InverseTransformPoint(filtro.transform.TransformPoint(vertice))
                );
            }
        }
        return vertices;
    }

    Vector3 ObtenerPuntaExterior(GameObject pieza, Transform referencia)
    {
        List<Vector3> vertices = ObtenerVerticesLocales(pieza, referencia);
        if (vertices.Count == 0) return pieza.transform.localPosition;
        float radioMaximo = vertices.Max(v => new Vector2(v.x, v.z).magnitude);
        List<Vector3> punta = vertices.Where(
            v => new Vector2(v.x, v.z).magnitude >= radioMaximo - 0.06f
        ).ToList();
        return punta.Aggregate(Vector3.zero, (suma, v) => suma + v) / punta.Count;
    }

    List<Vector3> ObtenerTresPuntosDeMontajeCentrado(
        GameObject pieza,
        Transform referencia
    )
    {
        List<Vector3> vertices = ObtenerVerticesLocales(pieza, referencia);
        if (vertices.Count == 0) return new List<Vector3>();
        float rangoX = vertices.Max(v => v.x) - vertices.Min(v => v.x);
        float rangoZ = vertices.Max(v => v.z) - vertices.Min(v => v.z);
        // El eje de los conductores es el de mayor extension, PERO con
        // preferencia por X cuando ambos son comparables: en las bovedas
        // giradas la profundidad (Z) puede superar ligeramente la luz (X),
        // y los conductores van SIEMPRE a los extremos y centro de X.
        bool ejeX = rangoX >= rangoZ * 0.667f;
        System.Func<Vector3, float> coordenada = v => ejeX ? v.x : v.z;
        float minimo = vertices.Min(coordenada);
        float maximo = vertices.Max(coordenada);
        float centro = (minimo + maximo) * 0.5f;
        float toleranciaExtremo = Mathf.Max(0.06f, (maximo - minimo) * 0.025f);
        // Tolerancia central amplia: en las bovedas triangulo los vertices del
        // centro pueden no tocar x=0 exactamente (las alas nacen en la cabeza),
        // pero sus cuatro esquinas simetricas se promedian en el centro real.
        float toleranciaCentro = Mathf.Max(0.1f, (maximo - minimo) * 0.35f);

        Vector3 Promedio(IEnumerable<Vector3> grupo) {
            List<Vector3> lista = grupo.ToList();
            return lista.Aggregate(Vector3.zero, (suma, v) => suma + v) / lista.Count;
        }

        Vector3 izquierda = Promedio(vertices.Where(v => coordenada(v) <= minimo + toleranciaExtremo));
        Vector3 derecha = Promedio(vertices.Where(v => coordenada(v) >= maximo - toleranciaExtremo));
        List<Vector3> centrales = vertices.Where(
            v => Mathf.Abs(coordenada(v) - centro) <= toleranciaCentro
        ).ToList();
        if (centrales.Count == 0)
        {
            // Sin vertices cerca del centro: usar el vertice mas cercano al
            // punto medio (evita el fallo de 'Max' sobre una lista vacia).
            float dMin = vertices.Min(v => Mathf.Abs(coordenada(v) - centro));
            centrales = vertices.Where(
                v => Mathf.Abs(coordenada(v) - centro) <= dMin + 0.001f
            ).ToList();
        }
        float ySuperior = centrales.Max(v => v.y);
        Vector3 central = Promedio(centrales.Where(v => v.y >= ySuperior - 0.06f));
        return new List<Vector3> { izquierda, central, derecha };
    }

    bool EsPuntoFinito(Vector3 punto)
    {
        return !float.IsNaN(punto.x) && !float.IsInfinity(punto.x)
            && !float.IsNaN(punto.y) && !float.IsInfinity(punto.y)
            && !float.IsNaN(punto.z) && !float.IsInfinity(punto.z);
    }

    bool ValidarPuntosConexion(List<Vector3> puntos, int numeroApoyo)
    {
        if (puntos.Count != 3) {
            Debug.LogError(
                $"Apoyo {numeroApoyo}: se obtuvieron {puntos.Count} puntos de "
                + "conexión; se necesitan exactamente tres."
            );
            return false;
        }

        for (int i = 0; i < puntos.Count; i++) {
            if (!EsPuntoFinito(puntos[i])) {
                Debug.LogError(
                    $"Apoyo {numeroApoyo}: PuntoConductor_{i + 1} contiene "
                    + "coordenadas no válidas."
                );
                return false;
            }
            for (int j = i + 1; j < puntos.Count; j++) {
                if (Vector3.Distance(puntos[i], puntos[j]) < 0.05f) {
                    Debug.LogError(
                        $"Apoyo {numeroApoyo}: los puntos de conexión {i + 1} "
                        + $"y {j + 1} coinciden o están demasiado próximos."
                    );
                    return false;
                }
            }
        }
        return true;
    }

    void CrearPuntosConexionConductores(
        GameObject raiz,
        ApoyoConfigurado configuracion
    )
    {
        List<GameObject> piezas = raiz.transform.Cast<Transform>()
            .Where(hijo => hijo.name != "Cabeza" && !hijo.name.StartsWith("Cuerpo_"))
            .Select(hijo => hijo.gameObject)
            .ToList();
        List<Vector3> puntos = new List<Vector3>();

        if (piezas.Count == 1) {
            puntos = ObtenerTresPuntosDeMontajeCentrado(piezas[0], raiz.transform);
        } else {
            List<Vector3> candidatos = piezas
                .Select(pieza => ObtenerPuntaExterior(pieza, raiz.transform))
                .ToList();
            if (candidatos.Count > 3) {
                int signoPreferido = configuracion.montaje.lado_inicial < 0 ? -1 : 1;
                List<Vector3> lado = candidatos.Where(
                    punto => Mathf.Sign(punto.x == 0f ? 1f : punto.x) == signoPreferido
                ).ToList();
                if (lado.Count >= 3) candidatos = lado;
            }
            puntos = candidatos.OrderByDescending(punto => punto.y).Take(3).ToList();
        }

        if (!ValidarPuntosConexion(puntos, configuracion.apoyo.numero)) return;

        for (int fase = 0; fase < 3; fase++) {
            GameObject punto = new GameObject($"PuntoConductor_{fase + 1}");
            punto.transform.SetParent(raiz.transform, false);
            punto.transform.localPosition = puntos[fase];
        }
    }

    void MontarCrucetasAndel(
        GameObject raiz,
        ApoyoConfigurado configuracion,
        float yTop
    )
    {
        if (configuracion.armado == null) {
            return;
        }
        if (configuracion.montaje == null || configuracion.cruceta == null) {
            Debug.LogError($"Apoyo {configuracion.apoyo.numero}: faltan datos de montaje o cruceta.");
            return;
        }

        string tipo = configuracion.montaje.tipo;
        string referencia = configuracion.cruceta.modelo_id;
        int ladoInicial = configuracion.montaje.lado_inicial < 0 ? -1 : 1;
        float d = configuracion.montaje.separacion_vertical_m;
        bool tresNiveles = tipo == "TRESBOLILLO"
            || tipo == "BANDERA"
            || tipo == "DOBLE_CIRCUITO";

        if (string.IsNullOrWhiteSpace(referencia)) {
            Debug.LogError($"Apoyo {configuracion.apoyo.numero}: falta la referencia de cruceta.");
            return;
        }
        if (tresNiveles && (float.IsNaN(d) || float.IsInfinity(d) || d <= 0f)) {
            Debug.LogError(
                $"Apoyo {configuracion.apoyo.numero}, referencia {referencia}: distancia D ausente o no valida."
            );
            return;
        }

        int creadas = 0;
        int esperadas;
        bool atirantada = configuracion.cruceta.es_atirantada;
        float[] niveles = tresNiveles
            ? new float[] { yTop, yTop - d, yTop - 2f * d }
            : new float[] { yTop };

        bool referenciaCompatible =
            (atirantada
                && (tipo == "TRESBOLILLO" || tipo == "BANDERA" || tipo == "DOBLE_CIRCUITO")
                && (referencia.StartsWith("ATC") || referencia.StartsWith("C_ATC-")))
            || (tipo == "PASO_HERRAJE_PUENTE"
                && referencia.StartsWith("ATC"))
            || (!atirantada
                && (tipo == "TRESBOLILLO" || tipo == "BANDERA")
                && (referencia.StartsWith("ASC-") || referencia.StartsWith("C_ASC-")))
            || (!atirantada
                && (tipo == "DOBLE_CIRCUITO" || tipo == "HORIZONTAL")
                && (referencia.StartsWith("ARCX-") || referencia.StartsWith("C_ARC-")))
            || (tipo == "PASO_LATERAL" && referencia.StartsWith("AMCX-"))
            || (tipo == "TRIANGULO_TG" && referencia.StartsWith("TG"))
            || (tipo == "BOVEDA_CAPA"
                && (referencia.StartsWith("BH") || referencia.StartsWith("C_BH")))
            || (tipo == "BOVEDA_PICO"
                && (referencia.StartsWith("BF") || referencia.StartsWith("C_BF")))
            || (tipo == "BOVEDA_TRIANGULO"
                && (referencia.StartsWith("BT") || referencia.StartsWith("C_BT")));
        if (!referenciaCompatible) {
            Debug.LogError(
                $"Apoyo {configuracion.apoyo.numero}: referencia {referencia} incompatible con el montaje {tipo}."
            );
            return;
        }

        if (tipo == "PASO_HERRAJE_PUENTE") {
            esperadas = 3;
            if (InstanciarCruceta(raiz, configuracion, referencia, yTop, yTop, ladoInicial, false)) creadas++;
            if (InstanciarCruceta(raiz, configuracion, referencia, yTop, yTop, -ladoInicial, false)) creadas++;
            if (InstanciarCruceta(
                raiz,
                configuracion,
                "GANCHO_HERRAJE_PUENTE",
                yTop,
                yTop,
                1,
                true
            )) creadas++;
        } else if (tipo == "PASO_LATERAL") {
            esperadas = 1;
            if (InstanciarCruceta(raiz, configuracion, referencia, yTop, yTop, 1, true)) creadas++;
        } else if (tipo == "TRIANGULO_TG") {
            esperadas = 1;
            if (InstanciarCruceta(raiz, configuracion, referencia, yTop, yTop, 1, true)) creadas++;
        } else if (tipo == "TRESBOLILLO") {
            esperadas = 3;
            int[] lados = { ladoInicial, -ladoInicial, ladoInicial };
            for (int i = 0; i < niveles.Length; i++) {
                if (InstanciarCruceta(raiz, configuracion, referencia, niveles[i], yTop, lados[i], false)) creadas++;
            }
        } else if (tipo == "BANDERA") {
            esperadas = 3;
            for (int i = 0; i < niveles.Length; i++) {
                if (InstanciarCruceta(raiz, configuracion, referencia, niveles[i], yTop, ladoInicial, false)) creadas++;
            }
        } else if (tipo == "DOBLE_CIRCUITO" && atirantada) {
            esperadas = 6;
            for (int i = 0; i < niveles.Length; i++) {
                if (InstanciarCruceta(raiz, configuracion, referencia, niveles[i], yTop, ladoInicial, false)) creadas++;
                if (InstanciarCruceta(raiz, configuracion, referencia, niveles[i], yTop, -ladoInicial, false)) creadas++;
            }
        } else if (tipo == "DOBLE_CIRCUITO") {
            esperadas = 3;
            for (int i = 0; i < niveles.Length; i++) {
                if (InstanciarCruceta(raiz, configuracion, referencia, niveles[i], yTop, 1, true)) creadas++;
            }
        } else if (tipo == "HORIZONTAL" && !atirantada) {
            esperadas = 1;
            if (InstanciarCruceta(raiz, configuracion, referencia, yTop, yTop, 1, true)) creadas++;
        } else if (tipo == "BOVEDA_CAPA"
            || tipo == "BOVEDA_PICO"
            || tipo == "BOVEDA_TRIANGULO") {
            esperadas = 1;
            if (InstanciarCruceta(raiz, configuracion, referencia, yTop, yTop, 1, true)) creadas++;
        } else {
            Debug.LogError(
                $"Apoyo {configuracion.apoyo.numero}, referencia {referencia}: tipo de montaje desconocido o incompatible ({tipo})."
            );
            return;
        }

        if (creadas != esperadas) {
            Debug.LogError(
                $"Apoyo {configuracion.apoyo.numero}, referencia {referencia}: se crearon {creadas} de {esperadas} piezas."
            );
        }
    }

    void CargarFisica()
    {
        fisicaLinea = null;
        vanosMecanicos.Clear();
        modelosCantonFase.Clear();
        string ruta = Path.Combine(RutasGemelo.RutaAssetsGemelo(), jsonFisica);
        if (!File.Exists(ruta)) {
            Debug.LogError("No se encontro el modelo mecanico: " + ruta);
            return;
        }

        fisicaLinea = JsonUtility.FromJson<DocumentoFisicaLinea>(File.ReadAllText(ruta));
        if (fisicaLinea == null || fisicaLinea.vanos == null
            || fisicaLinea.propiedades_conductor == null) {
            Debug.LogError("El JSON mecanico no tiene un formato valido.");
            fisicaLinea = null;
            return;
        }
        foreach (VanoMecanico vano in fisicaLinea.vanos) {
            vanosMecanicos[vano.indice] = vano;
        }
        if (fisicaLinea.avisos != null) {
            foreach (string aviso in fisicaLinea.avisos) {
                Debug.LogWarning("Modelo mecanico: " + aviso);
            }
        }
        Debug.Log(
            $"Modelo mecanico cargado: {vanosMecanicos.Count} vanos, "
            + $"hipotesis {fisicaLinea.hipotesis}."
        );
    }

    void ConfigurarGeografia()
    {
        if (terrenoUnity == null) return;
        string rutaInfo = Path.Combine(RutasGemelo.RutaAssetsGemelo(), csvInfoTerreno);
        string rutaRel = Path.Combine(RutasGemelo.RutaAssetsGemelo(), imagenRelieve);
        string rutaTex = Path.Combine(RutasGemelo.RutaAssetsGemelo(), imagenTextura);

        if (!File.Exists(rutaInfo) || !File.Exists(rutaRel)) return;

        string[] lineasInfo = File.ReadAllLines(rutaInfo);
        string[] v = lineasInfo[1].Split(',');
        
        float hMin = float.Parse(v[4], System.Globalization.CultureInfo.InvariantCulture);
        float hMax = float.Parse(v[5], System.Globalization.CultureInfo.InvariantCulture);
        float anchoReal = float.Parse(v[6], System.Globalization.CultureInfo.InvariantCulture);
        float largoReal = float.Parse(v[7], System.Globalization.CultureInfo.InvariantCulture);
        float offsetX = float.Parse(v[8], System.Globalization.CultureInfo.InvariantCulture);
        float offsetZ = float.Parse(v[9], System.Globalization.CultureInfo.InvariantCulture);

        float rangoAltura = hMax - hMin;

        byte[] bytesRel = File.ReadAllBytes(rutaRel);
        Texture2D texRel = new Texture2D(2, 2);
        texRel.LoadImage(bytesRel);
    
        TerrainData tData = terrenoUnity.terrainData;
        tData.heightmapResolution = Mathf.Max(texRel.width, texRel.height);
        tData.size = new Vector3(anchoReal, rangoAltura, largoReal);

        float[,] alturasCuadrada = new float[tData.heightmapResolution, tData.heightmapResolution];

        for (int z = 0; z < texRel.height; z++) {
            for (int x = 0; x < texRel.width; x++) {
                alturasCuadrada[z, x] = texRel.GetPixel(x, z).r;
            }
        }

        for (int z = 0; z < texRel.height; z++) {
            float alturaBordeDcho = texRel.GetPixel(texRel.width - 1, z).r;
            for (int xVacío = texRel.width; xVacío < tData.heightmapResolution; xVacío++) {
                alturasCuadrada[z, xVacío] = alturaBordeDcho;
            }
        }

        for (int x = 0; x < tData.heightmapResolution; x++) {
            float alturaBordeSuperior = texRel.GetPixel(Mathf.Min(x, texRel.width-1), texRel.height - 1).r;
            for (int zVacío = texRel.height; zVacío < tData.heightmapResolution; zVacío++) {
                alturasCuadrada[zVacío, x] = alturaBordeSuperior;
            }
        }

        tData.SetHeights(0, 0, alturasCuadrada);
        
        if (File.Exists(rutaTex)) {
            byte[] bytesTex = File.ReadAllBytes(rutaTex);
            Texture2D texFoto = new Texture2D(2, 2);
            texFoto.LoadImage(bytesTex);
            TerrainLayer capa = new TerrainLayer();
            capa.diffuseTexture = texFoto;
            capa.tileSize = new Vector2(anchoReal, largoReal);
            capa.tileOffset = Vector2.zero;
            tData.terrainLayers = new TerrainLayer[] { capa };
        }

        float normX = offsetX / anchoReal;
        float normZ = offsetZ / largoReal;
        float alturaEnTorre0 = texRel.GetPixelBilinear(normX, normZ).r * rangoAltura;
        terrenoUnity.transform.position = new Vector3(-offsetX, hMin - (hMin + alturaEnTorre0), -offsetZ);
    }

    void GenerarApoyosYCables()
    {
        string ruta = Path.Combine(RutasGemelo.RutaAssetsGemelo(), csvApoyos);
        if (!File.Exists(ruta)) return;

        string[] lineas = File.ReadAllLines(ruta);
        List<GameObject> listaApoyos = new List<GameObject>();

        for (int i = 1; i < lineas.Length; i++) {
            string[] d = lineas[i].Split(',');
            int numeroApoyo = int.Parse(d[0]);
            float xCSV = float.Parse(d[1], System.Globalization.CultureInfo.InvariantCulture);
            float zCSV = float.Parse(d[2], System.Globalization.CultureInfo.InvariantCulture);
            float ang = float.Parse(d[4], System.Globalization.CultureInfo.InvariantCulture);

            Vector3 posMuestreo = new Vector3(xCSV, 0, zCSV);
            float ySuelo = terrenoUnity.SampleHeight(posMuestreo) + terrenoUnity.transform.position.y;
            Vector3 posFinal = new Vector3(xCSV, ySuelo, zCSV);

            if (!apoyosConfigurados.TryGetValue(numeroApoyo, out ApoyoConfigurado configuracion)
                || configuracion.armado == null) {
                Debug.LogError($"El apoyo {numeroApoyo} no tiene armado configurado.");
                continue;
            }

            try {
                GameObject a = CrearApoyoCompleto(
                    configuracion,
                    posFinal,
                    Quaternion.Euler(0, ang, 0)
                );
                if (a != null) listaApoyos.Add(a);
            } catch (System.Exception error) {
                Debug.LogError(
                    $"El apoyo {numeroApoyo} no pudo terminar de montarse: {error.Message}"
                );
            }
        }

        PrepararModelosMecanicos(listaApoyos);
        InstalarCadenas(listaApoyos);
        for (int i = 0; i < listaApoyos.Count - 1; i++) {
            for (int fase = 0; fase < 3; fase++) {
                DibujarCable(listaApoyos[i], listaApoyos[i + 1], i, fase);
            }
        }
        DibujarArcosAmarre(listaApoyos);
    }

    // --- NUEVO REDIBUJADO RÁPIDO ---
    void SoloRedibujarCables()
    {
        CargarFisica(); // Por si has modificado el archivo desde fuera
        CargarConductorConfigurado();
        CargarApoyosConfigurados(); // Necesario para que el toggle de cadenas funcione sin reconstruir
        
        // 1. Borramos solo los objetos que se llamen "Cable" (incluidos los
        //    arcos de amarre de las cadenas)
        foreach (Transform child in transform.Cast<Transform>().ToList()) {
            if (child.name == "Cable" || child.name.StartsWith("Cable_Fase_")
                || child.name.StartsWith("Cable_Arco_Fase_")) {
                DestroyImmediate(child.gameObject);
            }
        }

        // 2. Buscamos los apoyos que ya existen en la escena
        List<GameObject> apoyosEnEscena = new List<GameObject>();
        foreach (Transform child in transform) {
            if (child.name.StartsWith("Apoyo_")) {
                apoyosEnEscena.Add(child.gameObject);
            }
        }
        apoyosEnEscena = apoyosEnEscena
            .OrderBy(apoyo => NumeroDesdeNombreApoyo(apoyo.name))
            .ToList();

        // 3. Borramos las cadenas viejas (cuelgan de cada apoyo) y volvemos a
        //    atar los cables con la nueva temperatura
        foreach (GameObject apoyo in apoyosEnEscena) {
            foreach (Transform child in apoyo.transform.Cast<Transform>().ToList()) {
                if (child.name.StartsWith("Cadena_Fase_")) {
                    DestroyImmediate(child.gameObject);
                }
            }
        }

        PrepararModelosMecanicos(apoyosEnEscena);
        InstalarCadenas(apoyosEnEscena);
        for (int i = 0; i < apoyosEnEscena.Count - 1; i++) {
            for (int fase = 0; fase < 3; fase++) {
                DibujarCable(apoyosEnEscena[i], apoyosEnEscena[i+1], i, fase);
            }
        }
        DibujarArcosAmarre(apoyosEnEscena);
        
        Debug.Log($"🌡️ Cables redibujados para la temperatura: {temperaturaVisualizacion}ºC");
    }

    /// <summary>Redibuja los cables con la temperatura de visualizacion actual.
    /// Lo usa la ventana "Temperatura del conductor" del gemelo digital.</summary>
    public void RedibujarCablesPorTemperatura()
    {
        SoloRedibujarCables();
    }

    int NumeroDesdeNombreApoyo(string nombre)
    {
        // El nombre puede ser "Apoyo_N__modelo_id" (el modelo C1000/C2000...
        // contiene dígitos). Tomamos solo el número del apoyo, el primer bloque.
        if (string.IsNullOrEmpty(nombre)) return int.MaxValue;
        int indiceDobleGuion = nombre.IndexOf("__");
        if (indiceDobleGuion > 0) nombre = nombre.Substring(0, indiceDobleGuion);
        string digitos = new string(nombre.Where(char.IsDigit).ToArray());
        return int.TryParse(digitos, out int numero) ? numero : int.MaxValue;
    }

    string ClaveCantonFase(int cantonId, int fase)
    {
        return $"{cantonId}:{fase}";
    }

    void PrepararModelosMecanicos(List<GameObject> apoyos)
    {
        modelosCantonFase.Clear();
        if (fisicaLinea == null || fisicaLinea.cantones == null
            || fisicaLinea.propiedades_conductor == null) return;

        double peso = fisicaLinea.propiedades_conductor.peso_daN_m;
        foreach (CantonMecanico canton in fisicaLinea.cantones) {
            if (canton == null || canton.vanos == null) continue;
            for (int fase = 0; fase < 3; fase++) {
                double suma1 = 0.0;
                double suma2 = 0.0;
                double suma3 = 0.0;
                bool modeloValido = true;
                double t0 = canton.temperatura_referencia_C;
                double tension0 = canton.tension_referencia_daN;
                if (tension0 <= 0.0) {
                    Debug.LogError($"Canton {canton.id}: tension de referencia no valida.");
                    continue;
                }

                foreach (int numeroVano in canton.vanos) {
                    int indice = numeroVano - 1;
                    if (indice < 0 || indice + 1 >= apoyos.Count
                        || !vanosMecanicos.TryGetValue(numeroVano, out VanoMecanico vano)) {
                        Debug.LogError($"Canton {canton.id}: falta el vano {numeroVano}.");
                        modeloValido = false;
                        continue;
                    }
                    if (System.Math.Abs(vano.temperatura_referencia_C - t0) > 0.01
                        || System.Math.Abs(vano.tension_referencia_daN - tension0) > 0.01) {
                        Debug.LogError(
                            $"Canton {canton.id}, vano {numeroVano}: el estado de "
                            + "referencia no coincide con el estado comun del canton."
                        );
                        modeloValido = false;
                        continue;
                    }
                    Transform puntoA = BuscarPuntoConductor(apoyos[indice], fase);
                    Transform puntoB = BuscarPuntoConductor(apoyos[indice + 1], fase);
                    if (puntoA == null || puntoB == null) {
                        modeloValido = false;
                        continue;
                    }

                    Vector3 pA = puntoA.position;
                    Vector3 pB = puntoB.position;
                    double a = Vector2.Distance(
                        new Vector2(pA.x, pA.z), new Vector2(pB.x, pB.z)
                    );
                    double h = pB.y - pA.y;
                    double b = System.Math.Sqrt(a * a + h * h);
                    if (a <= 0.0 || b <= 0.0) continue;
                    suma1 += b * b * b / (a * a);
                    suma2 += b * b / a;
                    suma3 += a * a * a;
                    double invertida = CalcularTensionDesdeFlecha(
                        vano.flecha_referencia_m, a, b, peso
                    );
                    if (!double.IsNaN(invertida)) {
                        double diferencia = 100.0 * (invertida - tension0) / tension0;
                        if (System.Math.Abs(diferencia) > 10.0) {
                            Debug.LogWarning(
                                $"Canton {canton.id}, vano {numeroVano}, fase {fase + 1}: "
                                + $"T Excel={tension0:F2} daN y T invertida desde F con "
                                + $"anclajes reales={invertida:F2} daN "
                                + $"({diferencia:F1}%). Se conserva T Excel."
                            );
                        }
                    }
                }

                if (!modeloValido || suma1 <= 0.0 || suma2 <= 0.0 || suma3 <= 0.0) {
                    Debug.LogError(
                        $"Canton {canton.id}, fase {fase + 1}: modelo mecanico incompleto."
                    );
                    continue;
                }
                double ar = (suma1 / suma2) * System.Math.Sqrt(suma3 / suma2);
                ModeloCantonFase modelo = new ModeloCantonFase {
                    cantonId = canton.id,
                    fase = fase,
                    vanoRegulacionM = ar,
                    temperaturaReferenciaC = t0,
                    tensionReferenciaDaN = tension0,
                };
                modelosCantonFase[ClaveCantonFase(canton.id, fase)] = modelo;
            }
        }
        Debug.Log(
            $"Modelos mecanicos preparados con anclajes reales: "
            + $"{modelosCantonFase.Count} combinaciones canton/fase."
        );
    }

    double CalcularTensionDesdeFlecha(double flecha, double a, double b, double peso)
    {
        if (flecha <= 0.0 || a <= 0.0 || b <= 0.0 || peso <= 0.0) return double.NaN;
        System.Func<double, double> flechaParaTension = tension =>
            (a * b * peso / (8.0 * tension))
            * (1.0 + (a * a * peso * peso) / (48.0 * tension * tension));
        double inferior = 1e-6;
        double superior = 1.0;
        while (flechaParaTension(superior) > flecha && superior < 1e9) superior *= 2.0;
        if (superior >= 1e9) return double.NaN;
        for (int i = 0; i < 100; i++) {
            double centro = (inferior + superior) * 0.5;
            if (flechaParaTension(centro) > flecha) inferior = centro;
            else superior = centro;
        }
        return (inferior + superior) * 0.5;
    }

    double CalcularTensionFinal(ModeloCantonFase modelo, double temperaturaFinal)
    {
        PropiedadesMecanicasConductor conductor = fisicaLinea.propiedades_conductor;
        double s = conductor.seccion_mm2;
        double e = conductor.modulo_elasticidad_daN_mm2;
        double alfa = conductor.coef_dilatacion_1_C;
        double p = conductor.peso_daN_m;
        double ar = modelo.vanoRegulacionM;
        double t0 = modelo.temperaturaReferenciaC;
        double tension0 = modelo.tensionReferenciaDaN;
        double aCoef = alfa * (temperaturaFinal - t0) * s * e - tension0
            + (ar * ar * p * p * s * e) / (24.0 * tension0 * tension0);
        double bCoef = (ar * ar * p * p * s * e) / 24.0;

        System.Func<double, double> polinomio = tension =>
            tension * tension * tension + aCoef * tension * tension - bCoef;
        double inferior = 0.0;
        double superior = System.Math.Max(1.0, tension0);
        while (polinomio(superior) <= 0.0 && superior < 1e9) superior *= 2.0;
        if (superior >= 1e9) return double.NaN;
        for (int i = 0; i < 120; i++) {
            double centro = (inferior + superior) * 0.5;
            if (polinomio(centro) <= 0.0) inferior = centro;
            else superior = centro;
        }
        return (inferior + superior) * 0.5;
    }

    double CalcularFlecha(double a, double b, double peso, double tension)
    {
        return (a * b * peso / (8.0 * tension))
            * (1.0 + (a * a * peso * peso) / (48.0 * tension * tension));
    }

    // Se añade el "indiceVano" para saber qué fila de física mirar
    Transform BuscarPuntoConductor(GameObject apoyo, int fase)
    {
        return apoyo.transform.Find($"PuntoConductor_{fase + 1}");
    }

    // ---------------------------------------------------------------------
    // Cadenas de aisladores: suspensión vertical y amarre/anclaje tras el cable
    // ---------------------------------------------------------------------
    [ContextMenu("🔗 Reinstalar Cadenas")]
    public void ReinstalarCadenas()
    {
        SoloRedibujarCables();
    }

    // Al abrir la escena en modo edición redibuja cadenas, cables y arcos con
    // la geometría actual (apoyos ya guardados), sin necesidad de pulsar nada.
    void GarantizarCadenasEnEscena()
    {
        if (Application.isPlaying) return;

        bool hayApoyos = false;
        foreach (Transform child in transform)
        {
            if (child.name.StartsWith("Apoyo_")) { hayApoyos = true; break; }
        }
        if (!hayApoyos)
        {
            // La jerarquía aún no está cargada: reintentamos en el próximo frame.
            escenaVerificada = false;
            return;
        }

        SoloRedibujarCables();
    }

    void InstalarCadenas(List<GameObject> apoyos)
    {
        if (!mostrarCadenas || apoyos == null) return;
        cadenasApoyo.Clear();
        int instaladas = 0;

        // 1) Geometría: puntos donde termina cada cadena (por apoyo y fase).
        for (int i = 0; i < apoyos.Count; i++)
        {
            GameObject apoyo = apoyos[i];
            int numero = NumeroDesdeNombreApoyo(apoyo.name);
            if (!apoyosConfigurados.TryGetValue(numero, out ApoyoConfigurado config)) continue;

            DatosCadenaConfigurada cadena = config.cadena;
            bool suspension = cadena != null
                ? cadena.tipo == "SUS"
                : EsTipoSuspension(config.tipo_clave);
            float longitud = cadena != null && cadena.caracteristicas != null
                    && cadena.caracteristicas.longitud_m > 0f
                ? cadena.caracteristicas.longitud_m
                : longitudCadenaPorDefecto;
            if (longitud <= 0f) longitud = longitudCadenaPorDefecto;
            // Tabla de Pascal (N/R) si no viene el número en la configuración.
            int nCadenas = cadena != null && cadena.n_cadenas > 0
                ? cadena.n_cadenas
                : NCadenasTablaPascal(config.tipo_clave, config.coef_seguridad);

            PuntosCadenasApoyo[] porFase = new PuntosCadenasApoyo[3];
            bool alguno = false;

            for (int fase = 0; fase < 3; fase++)
            {
                Transform punto = BuscarPuntoConductor(apoyo, fase);
                if (punto == null) continue;
                Vector3 punta = punto.position;

                PuntosCadenasApoyo pc = new PuntosCadenasApoyo();
                pc.suspension = suspension;

                if (suspension)
                {
                    // Cadena(s) vertical(es) desde la punta de la cruceta hasta
                    // el cable (paralelas si son dobles).
                    Vector3 ancla = punta + Vector3.down * longitud;
                    int n = Mathf.Max(1, nCadenas);
                    Vector3 perp = PerpendicularLinea(apoyos, i, fase);
                    pc.izquierda = new Vector3[n];
                    pc.derecha = new Vector3[n];
                    for (int c = 0; c < n; c++)
                    {
                        float desp = n == 1 ? 0f : (c - (n - 1) / 2f) * 0.07f;
                        Vector3 fin = ancla + perp * desp;
                        pc.izquierda[c] = fin;
                        pc.derecha[c] = fin;
                    }
                }
                else
                {
                    // Amarre/anclaje/final-principio: cadenas hacia los vanos.
                    // En principio/final de línea solo hay UN lado con cable:
                    // todas las cadenas van hacia él (normal -> 1, reforzado
                    // -> 2, ambas siguiendo la dirección real del cable).
                    bool hayIzquierda = i > 0;
                    bool hayDerecha = i < apoyos.Count - 1;
                    int nIzquierda = hayIzquierda
                        ? (hayDerecha ? Mathf.Max(1, nCadenas / 2) : nCadenas) : 0;
                    int nDerecha = hayDerecha
                        ? (hayIzquierda ? Mathf.Max(1, nCadenas / 2) : nCadenas) : 0;

                    if (hayIzquierda)
                    {
                        Vector3 ancla = PuntoAnclaCadena(apoyos, i, fase, false, longitud);
                        Vector3 dir = ancla - punta;
                        if (dir.sqrMagnitude < 0.0001f) dir = Vector3.down; else dir.Normalize();
                        pc.izquierda = ExtenderLado(ancla, dir, nIzquierda);
                    }
                    else
                    {
                        pc.izquierda = new Vector3[0];
                    }
                    if (hayDerecha)
                    {
                        Vector3 ancla = PuntoAnclaCadena(apoyos, i, fase, true, longitud);
                        Vector3 dir = ancla - punta;
                        if (dir.sqrMagnitude < 0.0001f) dir = Vector3.down; else dir.Normalize();
                        pc.derecha = ExtenderLado(ancla, dir, nDerecha);
                    }
                    else
                    {
                        pc.derecha = new Vector3[0];
                    }
                }

                porFase[fase] = pc;
                alguno = true;
            }
            if (alguno) cadenasApoyo[numero] = porFase;
        }

        // 2) Instanciar una cadena por extremo, orientada de la punta al extremo.
        for (int i = 0; i < apoyos.Count; i++)
        {
            GameObject apoyo = apoyos[i];
            int numero = NumeroDesdeNombreApoyo(apoyo.name);
            if (!cadenasApoyo.TryGetValue(numero, out PuntosCadenasApoyo[] porFase)) continue;
            if (!apoyosConfigurados.TryGetValue(numero, out ApoyoConfigurado config)) continue;
            string rutaModelo = RutaModeloCadena(config.cadena);

            for (int fase = 0; fase < 3; fase++)
            {
                PuntosCadenasApoyo pc = porFase[fase];
                if (pc == null) continue;
                Transform punto = BuscarPuntoConductor(apoyo, fase);
                if (punto == null) continue;
                Vector3 punta = punto.position;

                // En suspensión las cadenas son las mismas a ambos lados del
                // apoyo (verticales), así que se instalan solo una vez.
                Vector3[] extremos = pc.suspension
                    ? pc.derecha
                    : pc.izquierda.Concat(pc.derecha).ToArray();
                for (int c = 0; c < extremos.Length; c++)
                {
                    if (!EsPuntoFinito(extremos[c])) continue;
                    InstanciarUnaCadena(apoyo.transform, punta, extremos[c],
                        rutaModelo, numero, fase, c);
                    instaladas++;
                }
            }
        }
        Debug.Log($"🔗 Cadenas de aisladores instaladas: {instaladas}.");
    }
    // Tabla de Pascal: cadenas por fase según tipo de apoyo y coef. de seguridad.
    int NCadenasTablaPascal(string tipoClave, string coefSeguridad)
    {
        if (string.IsNullOrEmpty(tipoClave)) return 1;
        bool reforzada = !string.IsNullOrEmpty(coefSeguridad)
            && (coefSeguridad.StartsWith("R") || coefSeguridad.StartsWith("r"));
        if (EsTipoSuspension(tipoClave)) return reforzada ? 2 : 1;
        if (tipoClave.Contains("final") || tipoClave.Contains("principio"))
            return reforzada ? 2 : 1;
        return reforzada ? 4 : 2; // amarre/anclaje
    }

    string RutaModeloCadena(DatosCadenaConfigurada cadena)
    {
        if (cadena != null && cadena.caracteristicas != null
            && cadena.caracteristicas.longitud_m > 0f)
        {
            return $"{rutaModelosCadenas}{Mathf.RoundToInt(cadena.caracteristicas.longitud_m * 1000f)}mm";
        }
        return modeloCadenaPorDefecto;
    }

    // Punto REAL del cable donde se engancha la cadena del lado pedido
    // (haciaSiguiente = true -> vano i+1; false -> vano i-1). Método de "los
    // dos puntos": caminamos sobre el MISMO perfil de catenaria que dibuja el
    // cable, desde la punta de la cruceta hacia el apoyo vecino, hasta recorrer
    // una distancia ~ 'longitud' (la longitud de la cadena). Así la cadena
    // queda SIEMPRE colineal con el conductor (sus dos extremos están sobre la
    // catenaria) y su extremo final toca físicamente el cable. Sirve igual
    // para amarres/anclajes (dos lados) y para principio/final de línea (un
    // único lado con cable).
    Vector3 PuntoAnclaCadena(List<GameObject> apoyos, int indiceApoyo, int fase,
        bool haciaSiguiente, float longitud)
    {
        Transform punto = BuscarPuntoConductor(apoyos[indiceApoyo], fase);
        if (punto == null) return Vector3.down * longitud;
        Vector3 punta = punto.position;
        Vector3 fallback = punta + Vector3.down * longitud;

        int otroIndice = haciaSiguiente ? indiceApoyo + 1 : indiceApoyo - 1;
        if (otroIndice < 0 || otroIndice >= apoyos.Count) return fallback;
        Transform otroPunto = BuscarPuntoConductor(apoyos[otroIndice], fase);
        if (otroPunto == null)
        {
            // Sin punto vecino de conductor: dirección real hacia el apoyo
            // vecino (nunca se inventa una rotación arbitraria).
            Vector3 d = apoyos[otroIndice].transform.position - punta;
            return punta + (d.sqrMagnitude > 0.0001f ? d.normalized : Vector3.down) * longitud;
        }
        Vector3 otro = otroPunto.position;

        int indiceVano = Mathf.Min(indiceApoyo, otroIndice);
        if (ObtenerDatosCatenaria(indiceVano, punta, otro, fase,
            out double tension, out double peso, out double flecha))
        {
            // Buscar t en [0, 0.5] (cerca de la punta, hacia el vecino) tal que
            // |PuntoCatenaria(punta, otro, t) - punta| ~= longitud. La distancia
            // es monótona creciente, así que basta una bisección.
            double objetivo = longitud;
            float tLo = 0f, tHi = 0.5f;
            for (int it = 0; it < 40; it++)
            {
                float tM = (tLo + tHi) * 0.5f;
                Vector3 pM = PuntoCatenaria(punta, otro, tension, peso, flecha, tM);
                if (Vector3.Distance(pM, punta) < objetivo) tLo = tM; else tHi = tM;
            }
            Vector3 ancla = PuntoCatenaria(punta, otro, tension, peso, flecha, tLo);
            if ((ancla - punta).sqrMagnitude > 0.0001f) return ancla;
            return fallback;
        }

        // Sin física disponible: dirección real hacia el apoyo vecino.
        Vector3 dReal = otro - punta;
        return punta + (dReal.sqrMagnitude > 0.0001f ? dReal.normalized : Vector3.down) * longitud;
    }

    // Para cadenas dobles (n por lado): extremos ligeramente separados en
    // perpendicular a la dirección de la cadena, ambos junto al cable.
    Vector3[] ExtenderLado(Vector3 ancla, Vector3 dir, int nPorLado)
    {
        Vector3[] resultado = new Vector3[nPorLado];
        Vector3 perp = Vector3.Cross(Vector3.up, dir).normalized;
        if (perp.sqrMagnitude < 0.0001f) perp = Vector3.right;
        for (int c = 0; c < nPorLado; c++)
        {
            float desp = nPorLado == 1 ? 0f : (c - (nPorLado - 1) / 2f) * 0.07f;
            resultado[c] = ancla + perp * desp;
        }
        return resultado;
    }

    // Horizontal perpendicular al eje de la línea en un apoyo (separa cadenas
    // dobles de suspensión).
    Vector3 PerpendicularLinea(List<GameObject> apoyos, int indiceApoyo, int fase)
    {
        Transform punto = BuscarPuntoConductor(apoyos[indiceApoyo], fase);
        if (punto == null) return Vector3.right;
        Vector3 eje;
        if (indiceApoyo > 0)
        {
            Transform previo = BuscarPuntoConductor(apoyos[indiceApoyo - 1], fase);
            eje = previo != null ? (punto.position - previo.position) : Vector3.forward;
        }
        else if (indiceApoyo < apoyos.Count - 1)
        {
            Transform siguiente = BuscarPuntoConductor(apoyos[indiceApoyo + 1], fase);
            eje = siguiente != null ? (siguiente.position - punto.position) : Vector3.forward;
        }
        else
        {
            return Vector3.right;
        }
        Vector3 perp = Vector3.Cross(Vector3.up, eje).normalized;
        return perp.sqrMagnitude < 0.0001f ? Vector3.right : perp;
    }

    // Instancia una cadena desde la punta de la cruceta hasta 'fin'.
    void InstanciarUnaCadena(Transform padre, Vector3 punta, Vector3 fin,
        string rutaModelo, int numero, int fase, int indice)
    {
        Vector3 dir = fin - punta;
        if (dir.sqrMagnitude < 0.0001f) return;

        GameObject prefab = Resources.Load<GameObject>(rutaModelo);
        if (prefab == null)
            prefab = Resources.Load<GameObject>(modeloCadenaPorDefecto);

        GameObject cadenaGO;
        if (prefab != null)
        {
            cadenaGO = Instantiate(prefab, padre, false);
            AsegurarMaterialCadena(cadenaGO);
        }
        else
        {
            cadenaGO = CrearCadenaProcedimental(dir.magnitude, padre);
        }
        cadenaGO.name = indice == 0
            ? $"Cadena_Fase_{fase + 1}"
            : $"Cadena_Fase_{fase + 1}_{indice + 1}";

        // La cadena se dibuja SIEMPRE desde la punta de la cruceta hasta el
        // punto del cable ('fin'). Se mide la dirección real de extensión del
        // modelo con la rotación identidad y se orienta para que su extremo
        // inferior caiga justo sobre 'fin': funciona con CUALQUIER convención
        // de ejes del FBX (aunque el modelo quedara girado al importarse).
        cadenaGO.transform.position = punta;
        cadenaGO.transform.rotation = Quaternion.identity;
        Vector3 direccionModelo = DireccionExtensionCadena(cadenaGO, punta);
        cadenaGO.transform.rotation =
            Quaternion.FromToRotation(direccionModelo, dir.normalized);

        if (mostrarDiagnosticoMecanico)
        {
            Debug.Log(
                $"🔗 {cadenaGO.name} (apoyo {numero}, fase {fase + 1}): " +
                $"origen=({punta.x:F2},{punta.y:F2},{punta.z:F2}) " +
                $"fin=({fin.x:F2},{fin.y:F2},{fin.z:F2}) dir=({dir.normalized.x:F3}," +
                $"{dir.normalized.y:F3},{dir.normalized.z:F3})"
            );
        }
    }

    // Mide hacia dónde se extiende realmente el modelo desde su origen (punto
    // de amarre) con la rotación identidad: devuelve la dirección normalizada
    // desde el origen hacia el centro de la geometría.
    Vector3 DireccionExtensionCadena(GameObject cadenaGO, Vector3 origen)
    {
        Renderer[] renderers = cadenaGO.GetComponentsInChildren<Renderer>(true);
        if (renderers.Length == 0) return Vector3.down;
        Bounds b = renderers[0].bounds;
        for (int i = 1; i < renderers.Length; i++) b.Encapsulate(renderers[i].bounds);
        Vector3 dir = b.center - origen;
        if (dir.sqrMagnitude < 0.0001f) return Vector3.down;
        return dir.normalized;
    }

    Vector3 Centroide(Vector3[] puntos)
    {
        Vector3 suma = Vector3.zero;
        for (int i = 0; i < puntos.Length; i++) suma += puntos[i];
        return puntos.Length > 0 ? suma / puntos.Length : Vector3.zero;
    }

    // Garantiza que el modelo FBX tenga material visible (si Unity no lo importó).
    void AsegurarMaterialCadena(GameObject cadena)
    {
        foreach (Renderer r in cadena.GetComponentsInChildren<Renderer>(true))
        {
            if (r.sharedMaterial == null)
            {
                Material mat = new Material(Shader.Find("Sprites/Default"));
                if (mat != null)
                {
                    mat.color = new Color(0.45f, 0.42f, 0.38f);
                    r.sharedMaterial = mat;
                }
            }
        }
    }

    // Cadena de respaldo 100% procedural: si no hay modelo FBX en Resources,
    // dibuja una varilla con discos para que la línea siempre se vea.
    GameObject CrearCadenaProcedimental(float longitud, Transform padre)
    {
        GameObject raiz = new GameObject("CadenaProcedimental");
        raiz.transform.SetParent(padre, false);

        Material mat = new Material(Shader.Find("Sprites/Default"));
        if (mat != null) mat.color = new Color(0.4f, 0.38f, 0.34f);

        GameObject varilla = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        varilla.transform.SetParent(raiz.transform, false);
        varilla.name = "Cuerpo";
        varilla.transform.localPosition = new Vector3(0f, -longitud / 2f, 0f);
        varilla.transform.localScale = new Vector3(0.03f, longitud / 2f, 0.03f);
        if (mat != null) varilla.GetComponent<Renderer>().sharedMaterial = mat;
        QuitarCollidersProcedurales(varilla);

        int nDiscos = Mathf.Max(2, Mathf.RoundToInt(longitud / 0.16f));
        for (int i = 1; i <= nDiscos; i++)
        {
            float t = i / (float)(nDiscos + 1);
            GameObject disco = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            disco.transform.SetParent(raiz.transform, false);
            disco.name = "Disco_" + i;
            disco.transform.localPosition = new Vector3(0f, -longitud * t, 0f);
            disco.transform.localScale = new Vector3(0.09f, 0.018f, 0.09f);
            if (mat != null) disco.GetComponent<Renderer>().sharedMaterial = mat;
            QuitarCollidersProcedurales(disco);
        }
        return raiz;
    }

    void QuitarCollidersProcedurales(GameObject go)
    {
        Collider[] colis = go.GetComponents<Collider>();
        for (int i = 0; i < colis.Length; i++)
        {
            if (Application.isPlaying) Destroy(colis[i]);
            else DestroyImmediate(colis[i]);
        }
    }

    ApoyoConfigurado GetConfigApoyo(GameObject apoyo)
    {
        int numero = NumeroDesdeNombreApoyo(apoyo.name);
        return apoyosConfigurados.TryGetValue(numero, out ApoyoConfigurado config) ? config : null;
    }

    // Suspensión: la cadena cuelga vertical. Amarre/anclaje (y principio/fin de
    // línea): la cadena sigue la dirección del cable.
    bool EsTipoSuspension(string tipoClave)
    {
        if (string.IsNullOrEmpty(tipoClave)) return false;
        return tipoClave.Contains("suspension");
    }

    bool ObtenerDatosCatenaria(int indiceVano, Vector3 pA, Vector3 pB, int fase,
        out double tensionFinal, out double peso, out double flechaMaxima)
    {
        tensionFinal = peso = flechaMaxima = 0.0;
        if (fisicaLinea == null || fisicaLinea.propiedades_conductor == null) return false;
        if (!vanosMecanicos.TryGetValue(indiceVano + 1, out VanoMecanico vano)) return false;
        if (!modelosCantonFase.TryGetValue(
                ClaveCantonFase(vano.canton_id, fase), out ModeloCantonFase modelo)) return false;

        double distH = Vector2.Distance(new Vector2(pA.x, pA.z), new Vector2(pB.x, pB.z));
        double desnivel = pB.y - pA.y;
        double longitudInclinada = System.Math.Sqrt(distH * distH + desnivel * desnivel);
        tensionFinal = CalcularTensionFinal(modelo, temperaturaVisualizacion);
        peso = fisicaLinea.propiedades_conductor.peso_daN_m;
        flechaMaxima = CalcularFlecha(distH, longitudInclinada, peso, tensionFinal);
        return !double.IsNaN(tensionFinal) && !double.IsInfinity(tensionFinal)
            && tensionFinal > 0.0 && !double.IsNaN(flechaMaxima)
            && !double.IsInfinity(flechaMaxima);
    }

    // Punto del perfil de catenaria normalizado entre dos anclajes, con la
    // flecha del centro coincidiendo con flechaMaxima (misma fórmula que el
    // bucle de DibujarCable).
    Vector3 PuntoCatenaria(Vector3 pA, Vector3 pB, double tensionFinal, double peso,
        double flechaMaxima, float t)
    {
        double distH = Vector2.Distance(new Vector2(pA.x, pA.z), new Vector2(pB.x, pB.z));
        double parametroForma = tensionFinal / peso;
        double denominadorForma = System.Math.Cosh(distH / (2.0 * parametroForma)) - 1.0;
        Vector3 p = Vector3.Lerp(pA, pB, t);
        double descenso;
        if (System.Math.Abs(denominadorForma) < 1e-12)
        {
            descenso = flechaMaxima * 4.0 * t * (1.0 - t);
        }
        else
        {
            double xRel = (t - 0.5) * distH;
            double perfil = (System.Math.Cosh(distH / (2.0 * parametroForma))
                - System.Math.Cosh(xRel / parametroForma)) / denominadorForma;
            descenso = flechaMaxima * perfil;
        }
        p.y -= (float)descenso;
        return p;
    }

    // Ancla del cable en el lado derecho del apoyo (extremo de las cadenas
    // hacia el vano siguiente). Si no hay cadenas, devuelve el punto original.
    Vector3 AnclaCableDerecha(int numeroApoyo, int fase, Vector3 fallback)
    {
        if (!mostrarCadenas
            || !cadenasApoyo.TryGetValue(numeroApoyo, out PuntosCadenasApoyo[] porFase))
            return fallback;
        PuntosCadenasApoyo pc = porFase != null && fase >= 0 && fase < porFase.Length
            ? porFase[fase] : null;
        if (pc == null || pc.derecha == null || pc.derecha.Length == 0) return fallback;
        return Centroide(pc.derecha);
    }

    // Ancla del cable en el lado izquierdo del apoyo (hacia el vano anterior).
    Vector3 AnclaCableIzquierda(int numeroApoyo, int fase, Vector3 fallback)
    {
        if (!mostrarCadenas
            || !cadenasApoyo.TryGetValue(numeroApoyo, out PuntosCadenasApoyo[] porFase))
            return fallback;
        PuntosCadenasApoyo pc = porFase != null && fase >= 0 && fase < porFase.Length
            ? porFase[fase] : null;
        if (pc == null || pc.izquierda == null || pc.izquierda.Length == 0) return fallback;
        return Centroide(pc.izquierda);
    }

    // Pequeño arco de conductor que une las cadenas de amarre/anclaje bajo la
    // cruceta: vano anterior -> cadena izq. -> arco -> cadena der. -> vano sig.
    void DibujarArcosAmarre(List<GameObject> apoyos)
    {
        if (!mostrarCadenas || apoyos == null) return;
        for (int i = 0; i < apoyos.Count; i++)
        {
            GameObject apoyo = apoyos[i];
            int numero = NumeroDesdeNombreApoyo(apoyo.name);
            if (!cadenasApoyo.TryGetValue(numero, out PuntosCadenasApoyo[] porFase)) continue;

            ApoyoConfigurado config = GetConfigApoyo(apoyo);
            if (config == null) continue;
            DatosCadenaConfigurada cadena = config.cadena;
            bool suspension = cadena != null
                ? cadena.tipo == "SUS"
                : EsTipoSuspension(config.tipo_clave);
            if (suspension) continue;

            for (int fase = 0; fase < 3; fase++)
            {
                PuntosCadenasApoyo pc = porFase[fase];
                if (pc == null) continue;
                if (pc.izquierda.Length == 0 || pc.derecha.Length == 0) continue;

                Vector3 izq = Centroide(pc.izquierda);
                Vector3 der = Centroide(pc.derecha);
                if (!EsPuntoFinito(izq) || !EsPuntoFinito(der)) continue;

                GameObject go = new GameObject($"Cable_Arco_Fase_{fase + 1}_Apoyo_{numero}");
                go.transform.SetParent(this.transform);
                LineRenderer lr = go.AddComponent<LineRenderer>();

                Material materialLinea;
                if (materialCable != null) {
                    materialLinea = new Material(materialCable);
                } else {
                    materialLinea = new Material(Shader.Find("Sprites/Default"));
                }
                materialLinea.color = colorConductorCable;
                lr.sharedMaterial = materialLinea;
                lr.startColor = Color.white;
                lr.endColor = Color.white;
                float diametroFisico = conductorConfigurado != null
                    ? conductorConfigurado.diametro_m
                    : grosorCable;
                float diametroVisual = diametroFisico * MultiplicadorDiametroVisual;
                lr.startWidth = lr.endWidth = diametroVisual;
                lr.useWorldSpace = true;

                int puntos = 9;
                lr.positionCount = puntos;
                float caida = Mathf.Min(0.45f, Vector3.Distance(izq, der) * 0.25f);
                for (int k = 0; k < puntos; k++)
                {
                    float t = k / (float)(puntos - 1);
                    Vector3 p = Vector3.Lerp(izq, der, t);
                    p.y -= caida * 4f * t * (1f - t);
                    lr.SetPosition(k, p);
                }
            }
        }
    }

    void DibujarCable(GameObject a, GameObject b, int indiceVano, int fase)
    {
        Transform anclajeA = BuscarPuntoConductor(a, fase);
        Transform anclajeB = BuscarPuntoConductor(b, fase);
        if (anclajeA == null || anclajeB == null) {
            Debug.LogError(
                $"Vano {indiceVano + 1}, fase {fase + 1}: faltan puntos de conexión."
            );
            return;
        }

        GameObject go = new GameObject($"Cable_Fase_{fase + 1}_Vano_{indiceVano + 1}");
        go.transform.SetParent(this.transform);
        LineRenderer lr = go.AddComponent<LineRenderer>();

        // Los tres conductores se pintan de rosa fosforito para distinguirlos
        // bien en el gemelo digital. Se copia el material del Inspector (o se
        // crea uno nuevo si no hay) para no modificar el material original.
        // OJO: se configura el material en una variable local y se asigna una
        // sola vez con sharedMaterial. Acceder a lr.material (getter) en modo
        // edición instancia un material y lo filtra en la escena.
        //
        // El color rosa se aplica DIRECTAMENTE en el material, no solo en los
        // vertex colors. Así funciona tanto con shaders que combinan vertex
        // colors (Sprites/Default) como con shaders tipo Standard/URP Lit,
        // que ignoraban startColor/endColor y mostraban el material gris.
        Material materialLinea;
        if (materialCable != null) {
            materialLinea = new Material(materialCable);
        } else {
            materialLinea = new Material(Shader.Find("Sprites/Default"));
        }
        materialLinea.color = colorConductorCable;
        lr.sharedMaterial = materialLinea;
        lr.startColor = Color.white;
        lr.endColor = Color.white;
        float diametroFisico = conductorConfigurado != null
            ? conductorConfigurado.diametro_m
            : grosorCable;
        float diametroVisual = diametroFisico * MultiplicadorDiametroVisual;
        lr.startWidth = lr.endWidth = diametroVisual;
        lr.positionCount = 61;
        lr.useWorldSpace = true;

        Vector3 pA = anclajeA.position;
        Vector3 pB = anclajeB.position;

        if (!vanosMecanicos.TryGetValue(indiceVano + 1, out VanoMecanico vano)
            || !modelosCantonFase.TryGetValue(
                ClaveCantonFase(vano.canton_id, fase), out ModeloCantonFase modelo
            )) {
            Debug.LogError(
                $"Vano {indiceVano + 1}, fase {fase + 1}: no hay modelo mecanico."
            );
            DestroyImmediate(go);
            return;
        }

        double distH = Vector2.Distance(new Vector2(pA.x, pA.z), new Vector2(pB.x, pB.z));
        double desnivel = pB.y - pA.y;
        double longitudInclinada = System.Math.Sqrt(distH * distH + desnivel * desnivel);
        double tensionFinal = CalcularTensionFinal(modelo, temperaturaVisualizacion);
        double peso = fisicaLinea.propiedades_conductor.peso_daN_m;
        double flechaMaxima = CalcularFlecha(
            distH, longitudInclinada, peso, tensionFinal
        );
        if (double.IsNaN(tensionFinal) || double.IsInfinity(tensionFinal)
            || tensionFinal <= 0.0 || double.IsNaN(flechaMaxima)) {
            Debug.LogError(
                $"Vano {indiceVano + 1}, fase {fase + 1}: resultado mecanico invalido."
            );
            DestroyImmediate(go);
            return;
        }
        if (mostrarDiagnosticoMecanico) {
            Debug.Log(
                $"Vano {indiceVano + 1}, fase {fase + 1}, "
                + $"T={temperaturaVisualizacion:F1} C: h real={desnivel:F3} m, "
                + $"Ar={modelo.vanoRegulacionM:F3} m, "
                + $"tension={tensionFinal:F3} daN, flecha={flechaMaxima:F3} m."
            );
        }

        // Los cables cuelgan del extremo inferior de las cadenas: el ancla del
        // lado derecho del apoyo izquierdo y el ancla del lado izquierdo del
        // apoyo derecho (puntos calculados en InstalarCadenas).
        Vector3 pA2 = AnclaCableDerecha(NumeroDesdeNombreApoyo(a.name), fase, pA);
        Vector3 pB2 = AnclaCableIzquierda(NumeroDesdeNombreApoyo(b.name), fase, pB);

        // Perfil de catenaria normalizado: conserva los anclajes y hace que la
        // flecha visible en el centro coincida con la ecuacion del programa Pascal.
        double parametroForma = tensionFinal / peso;
        double denominadorForma = System.Math.Cosh(distH / (2.0 * parametroForma)) - 1.0;

        for (int i = 0; i <= 60; i++) {
            float t = i / 60f;
            Vector3 p = Vector3.Lerp(pA2, pB2, t);
            double descenso;
            if (System.Math.Abs(denominadorForma) < 1e-12) {
                descenso = flechaMaxima * 4.0 * t * (1.0 - t);
            } else {
                double xRel = (t - 0.5) * distH;
                double perfil = (
                    System.Math.Cosh(distH / (2.0 * parametroForma))
                    - System.Math.Cosh(xRel / parametroForma)
                ) / denominadorForma;
                descenso = flechaMaxima * perfil;
            }
            p.y -= (float)descenso;
            lr.SetPosition(i, p);
        }
    }

    void LimpiarEscena() {
        while (transform.childCount > 0) DestroyImmediate(transform.GetChild(0).gameObject);
    }
}
