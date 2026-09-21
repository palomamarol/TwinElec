using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.EventSystems;

/// <summary>
/// Cámara de inspección adaptable a la geometría generada por TwinElec.
/// Encuadra apoyos y cables sin depender de una línea o coordenadas concretas.
/// </summary>
[RequireComponent(typeof(Camera))]
public class CamaraLinea : MonoBehaviour
{
    [Header("Objetivo")]
    public GeneradorDeLinea generador;
    public bool encuadrarAlIniciar = true;

    [Header("Encuadre")]
    [Range(1.05f, 2f)] public float margenEncuadre = 1.25f;
    [Range(10f, 75f)] public float elevacionInicialDeg = 28f;
    [Tooltip("Zoom minimo: permite acercarse mucho a crucetas, cadenas y apoyos.")]
    public float distanciaMinima = 0.2f;
    [Tooltip("Distancia minima usada solo al encuadrar la vista inicial o pulsar Home.")]
    public float distanciaMinimaEncuadre = 10f;
    [Header("Controles")]
    public bool permitirControles = true;
    public float velocidadOrbita = 0.25f;
    public float velocidadDesplazamiento = 0.002f;
    [Tooltip("Suavizado del zoom (mayor = mas rapido).")]
    public float suavizadoZoom = 10f;
    public float distanciaMaxima = 20000f;
    [Tooltip("La camara no baja de esta altura sobre el terreno (si esta visible).")]
    public float alturaMinimaSobreTerreno = 0.5f;
    [Tooltip("Velocidad del vuelo libre (boton derecho + WASD).")]
    public float velocidadVuelo = 30f;

    // Estado orbital: pivote = centro de giro dinamico
    Vector3 pivot;
    float distancia;
    float distanciaObjetivo;
    float azimutDeg;
    float elevacionDeg = 28f;
    Camera camara;
    Terrain terreno;
    bool tieneEncuadre;
    Bounds limitesEncuadre;

    // Seleccion / foco (tecla F) y visibilidad del terreno
    Transform apoyoFoco;
    bool terrenoVisible = true;

    // Vuelo libre (boton derecho + WASD)
    bool modoVuelo;
    float guinadaVuelo;
    float cabeceoVuelo;

    // Deteccion de doble clic
    float ultimoClicIzq = -999f;
    bool clicArrastrando;

    public bool TerrenoVisible { get { return terrenoVisible; } }

    IEnumerator Start()
    {
        camara = GetComponent<Camera>();
        if (generador == null)
            generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (terreno == null)
            terreno = FindAnyObjectByType<Terrain>();

        // GeneradorDeLinea construye la línea en Start. Esperamos dos frames
        // para medir los Renderer definitivos, incluidos los LineRenderer.
        yield return null;
        yield return new WaitForEndOfFrame();
        if (encuadrarAlIniciar) EncuadrarLinea();
    }

    void LateUpdate()
    {
        if (!permitirControles) return;
        Mouse raton = Mouse.current;
        Keyboard teclado = Keyboard.current;

        if (teclado != null && teclado.homeKey.wasPressedThisFrame)
        {
            EncuadrarLinea();
            return;
        }
        if (teclado != null && teclado.fKey.wasPressedThisFrame)
        {
            EnfocarSeleccion();
            return;
        }
        if (raton == null) return;

        // Si el puntero esta sobre la interfaz (botones, desplegables...), la
        // rueda o los clics NO deben mover la camara: el scroll de un desplegable
        // solo debe desplazar la lista, nunca hacer zoom ni orbitar el terreno.
        if (EventSystem.current != null && EventSystem.current.IsPointerOverGameObject())
            return;

        Vector2 delta = raton.delta.ReadValue();

        // VUELO LIBRE (opcional): boton derecho + WASD. Al soltar, se vuelve a
        // la orbita alrededor del punto que se estaba mirando.
        bool moverVuelo = teclado != null
            && (teclado.wKey.isPressed || teclado.aKey.isPressed
                || teclado.sKey.isPressed || teclado.dKey.isPressed
                || teclado.spaceKey.isPressed || teclado.leftCtrlKey.isPressed);
        if (raton.rightButton.isPressed && moverVuelo)
        {
            ActualizarVuelo(delta, teclado);
            return;
        }
        if (modoVuelo) TerminarVuelo();

        // DOBLE CLIC: convierte el punto pulsado en el nuevo centro de giro
        // (y selecciona el apoyo para la tecla F si se ha pulsado sobre uno).
        if (raton.leftButton.wasPressedThisFrame)
        {
            if (Time.time - ultimoClicIzq < 0.3f)
            {
                EstablecerPivoteBajoCursor();
                ultimoClicIzq = -999f;
            }
            else
            {
                ultimoClicIzq = Time.time;
            }
        }

        // ORBITA: Alt + boton izquierdo (recomendado) o boton derecho solo
        // (muscle memory de la camara antigua). Al iniciar el arrastre se
        // adopta el punto bajo el cursor SOLO si esta cerca de la profundidad
        // actual, para que girar nunca cambie el tamano de la imagen.
        bool alt = teclado != null
            && (teclado.leftAltKey.isPressed || teclado.rightAltKey.isPressed);
        bool orbitaActiva = (alt && raton.leftButton.isPressed)
            || raton.rightButton.isPressed;
        if (orbitaActiva && !raton.middleButton.isPressed)
        {
            if (!clicArrastrando)
            {
                clicArrastrando = true;
                IntentarPivoteOrbita();
            }
            Orbitar(delta);
        }
        if (!raton.leftButton.isPressed && !raton.rightButton.isPressed)
            clicArrastrando = false;

        // BOTON CENTRAL: desplazamiento PARALELO A LA PANTALLA (horizontal y
        // vertical), proporcional a la distancia. Direccion tipo "agarrar el
        // mundo": arrastrar a la derecha/arriba mueve la escena con el raton.
        if (raton.middleButton.isPressed)
        {
            float escala = 2f * distancia
                * Mathf.Tan(camara.fieldOfView * 0.5f * Mathf.Deg2Rad)
                / Mathf.Max(1f, camara.pixelHeight);
            Vector3 despl = (-transform.right * delta.x - transform.up * delta.y)
                * escala * velocidadDesplazamiento * 500f;
            pivot += despl;
            AplicarOrbita();
        }

        // RUEDA: zoom orbital hacia el centro actual de la vista. Se modifica
        // solo la distancia objetivo para que el suavizado actue de verdad y
        // el movimiento sea predecible incluso muy cerca de un apoyo.
        float rueda = raton.scroll.ReadValue().y;
        if (Mathf.Abs(rueda) > 0.01f)
        {
            float notches = Mathf.Abs(rueda) > 60f ? rueda / 120f : rueda;
            float factor = Mathf.Pow(0.85f, notches);
            factor = Mathf.Clamp(factor, 0.25f, 4f);
            SolicitarZoom(factor);
        }

        // Suavizado continuo hacia el objetivo (solo cuando cambia el zoom).
        if (Mathf.Abs(distancia - distanciaObjetivo) > 0.001f)
        {
            float respuesta = 1f - Mathf.Exp(-suavizadoZoom * Time.deltaTime);
            distancia = Mathf.Lerp(distancia, distanciaObjetivo, respuesta);
            AplicarOrbita();
        }
    }

    /// <summary>Orbita alrededor del pivote con sensibilidad constante.</summary>
    void Orbitar(Vector2 delta)
    {
        azimutDeg += delta.x * velocidadOrbita;
        elevacionDeg = Mathf.Clamp(
            elevacionDeg - delta.y * velocidadOrbita,
            5f,
            85f
        );
        AplicarOrbita();
    }

    // -----------------------------------------------------------------------
    // Zoom orbital y foco
    // -----------------------------------------------------------------------
    void SolicitarZoom(float factor)
    {
        distanciaObjetivo = Mathf.Clamp(
            distanciaObjetivo * factor,
            distanciaMinima,
            distanciaMaxima
        );
    }

    void EstablecerPivoteBajoCursor()
    {
        Ray rayo = camara.ScreenPointToRay(Mouse.current.position.ReadValue());
        RaycastHit hit;
        if (!RaycastMundo(rayo, out hit)) return;
        pivot = hit.point;
        // Los apoyos no tienen colisionador: se toma el apoyo MÁS CERCANO al
        // punto pulsado (radio 30 m) como foco de la tecla F.
        apoyoFoco = BuscarApoyoCercano(hit.point, 30f);
        SincronizarOrbitaDesdeCamara();
        AplicarOrbita();
    }

    /// <summary>Al iniciar una orbita, adopta el punto bajo el cursor como
    /// centro SOLO si esta cerca de la profundidad actual de la vista. Asi
    /// girar alrededor de lo que se esta mirando no cambia el tamano ni pierde
    /// el objeto (el suelo lejano bajo un apoyo no "encoge" la imagen).</summary>
    void IntentarPivoteOrbita()
    {
        Ray rayo = camara.ScreenPointToRay(Mouse.current.position.ReadValue());
        RaycastHit hit;
        if (!RaycastMundo(rayo, out hit)) return;
        float profundidad = Vector3.Dot(
            hit.point - camara.transform.position, camara.transform.forward);
        if (profundidad < distancia * 0.25f || profundidad > distancia * 4f)
            return;
        pivot = hit.point;
        apoyoFoco = BuscarApoyoCercano(hit.point, 30f);
        SincronizarOrbitaDesdeCamara();
        AplicarOrbita();
    }

    /// <summary>Re-deriva azimut/elevacion/distancia a partir de la posicion y
    /// rotacion ACTUALES de la camara (la camara se queda en su sitio). Se usa
    /// al cambiar el pivote (zoom al cursor, doble clic, Alt+orbitar) para que
    /// el nuevo centro de giro no provoque saltos ni cambios de escala.</summary>
    void SincronizarOrbitaDesdeCamara()
    {
        if (camara == null) return;
        distancia = Mathf.Max(0.01f,
            Vector3.Distance(camara.transform.position, pivot));
        distanciaObjetivo = distancia;
        Vector3 angulos = camara.transform.eulerAngles;
        elevacionDeg = Mathf.Clamp(angulos.x, 5f, 85f);
        azimutDeg = angulos.y;
    }

    Transform BuscarApoyoCercano(Vector3 punto, float radio)
    {
        if (generador == null)
            generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador == null) return null;
        Transform mejor = null;
        float mejorCuad = radio * radio;
        foreach (Transform hijo in generador.transform)
        {
            if (hijo == null || !hijo.name.StartsWith("Apoyo_")) continue;
            float d = (hijo.position - punto).sqrMagnitude;
            if (d < mejorCuad)
            {
                mejorCuad = d;
                mejor = hijo;
            }
        }
        return mejor;
    }

    /// <summary>F: enfoca el apoyo seleccionado (doble clic sobre el); si no
    /// hay ninguno, encuadra toda la linea.</summary>
    void EnfocarSeleccion()
    {
        if (apoyoFoco == null)
        {
            EncuadrarLinea();
            return;
        }
        Renderer[] renderers = apoyoFoco.GetComponentsInChildren<Renderer>(true);
        Bounds limites = new Bounds(apoyoFoco.position, Vector3.one);
        foreach (Renderer r in renderers)
            if (r.enabled) limites.Encapsulate(r.bounds);
        pivot = limites.center;
        float tam = Mathf.Max(1f, limites.extents.magnitude);
        distancia = Mathf.Max(distanciaMinima, tam * 4f);
        distanciaObjetivo = distancia;
        AplicarOrbita();
    }

    bool RaycastMundo(Ray rayo, out RaycastHit hit)
    {
        return Physics.Raycast(rayo, out hit, Mathf.Infinity);
    }

    // -----------------------------------------------------------------------
    // Vuelo libre (boton derecho + WASD)
    // -----------------------------------------------------------------------
    void ActualizarVuelo(Vector2 delta, Keyboard teclado)
    {
        if (!modoVuelo)
        {
            modoVuelo = true;
            guinadaVuelo = transform.eulerAngles.y;
            cabeceoVuelo = transform.eulerAngles.x;
        }
        guinadaVuelo += delta.x * 0.15f;
        cabeceoVuelo = Mathf.Clamp(cabeceoVuelo - delta.y * 0.15f, -89f, 89f);
        transform.rotation = Quaternion.Euler(cabeceoVuelo, guinadaVuelo, 0f);

        // Velocidad adaptativa: lenta cerca, rapida lejos.
        float velocidad = Mathf.Max(5f, distancia) * velocidadVuelo * 0.1f;
        Vector3 movimiento = Vector3.zero;
        if (teclado != null)
        {
            if (teclado.wKey.isPressed) movimiento += transform.forward;
            if (teclado.sKey.isPressed) movimiento -= transform.forward;
            if (teclado.dKey.isPressed) movimiento += transform.right;
            if (teclado.aKey.isPressed) movimiento -= transform.right;
            if (teclado.spaceKey.isPressed) movimiento += Vector3.up;
            if (teclado.leftCtrlKey.isPressed) movimiento -= Vector3.up;
        }
        if (movimiento.sqrMagnitude > 0.001f)
            transform.position += movimiento.normalized * velocidad * Time.deltaTime;
    }

    void TerminarVuelo()
    {
        modoVuelo = false;
        // El pivote pasa a ser el punto que se estaba mirando.
        pivot = transform.position + transform.forward * distancia;
        Vector3 dir = (transform.position - pivot).normalized;
        // Misma convencion de angulos que EncuadrarLinea: azimut = atan2(-dir.x, -dir.z).
        elevacionDeg = Mathf.Clamp(
            Mathf.Asin(Mathf.Clamp(dir.y, -1f, 1f)) * Mathf.Rad2Deg, -85f, 85f);
        azimutDeg = Mathf.Atan2(-dir.x, -dir.z) * Mathf.Rad2Deg;
        AplicarOrbita();
    }

    // -----------------------------------------------------------------------
    // Terreno: ocultar/mostrar para ver la linea "flotando"
    // -----------------------------------------------------------------------
    /// <summary>Oculta o muestra el terreno y la elevacion. Devuelve true si
    /// el terreno queda VISIBLE.</summary>
    public bool AlternarTerreno()
    {
        if (terreno == null) terreno = FindAnyObjectByType<Terrain>();
        if (terreno == null) return terrenoVisible;
        terrenoVisible = !terrenoVisible;
        if (terreno.gameObject != null)
            terreno.gameObject.SetActive(terrenoVisible);
        return terrenoVisible;
    }


    [ContextMenu("Encuadrar línea completa")]
    public void EncuadrarLinea()
    {
        if (camara == null) camara = GetComponent<Camera>();
        if (generador == null)
            generador = FindAnyObjectByType<GeneradorDeLinea>();
        if (generador == null || !TryObtenerLimites(out Bounds limites)) {
            Debug.LogWarning("Cámara: no hay una línea generada que encuadrar.");
            return;
        }

        limitesEncuadre = limites;
        pivot = limites.center;
        Vector3 direccionLinea = ObtenerDireccionLinea();
        Vector3 lateral = Vector3.Cross(Vector3.up, direccionLinea).normalized;
        if (lateral.sqrMagnitude < 0.5f) lateral = Vector3.right;

        float elevacionRad = elevacionInicialDeg * Mathf.Deg2Rad;
        Vector3 direccionDesdeObjetivo = (
            lateral * Mathf.Cos(elevacionRad)
            + Vector3.up * Mathf.Sin(elevacionRad)
        ).normalized;
        elevacionDeg = Mathf.Asin(direccionDesdeObjetivo.y) * Mathf.Rad2Deg;
        azimutDeg = Mathf.Atan2(
            -direccionDesdeObjetivo.x,
            -direccionDesdeObjetivo.z
        ) * Mathf.Rad2Deg;

        Quaternion rotacion = Quaternion.LookRotation(-direccionDesdeObjetivo, Vector3.up);
        distancia = CalcularDistanciaEncuadre(limites, rotacion) * margenEncuadre;
        distancia = Mathf.Clamp(distancia, distanciaMinima, distanciaMaxima);
        distanciaObjetivo = distancia;
        tieneEncuadre = true;
        AplicarOrbita();
    }

    bool TryObtenerLimites(out Bounds limites)
    {
        Renderer[] renderers = generador.GetComponentsInChildren<Renderer>(true);
        bool inicializado = false;
        limites = new Bounds();
        foreach (Renderer rendererLinea in renderers) {
            if (!rendererLinea.enabled) continue;
            if (!inicializado) {
                limites = rendererLinea.bounds;
                inicializado = true;
            } else {
                limites.Encapsulate(rendererLinea.bounds);
            }
        }
        return inicializado;
    }

    Vector3 ObtenerDireccionLinea()
    {
        List<Transform> apoyos = generador.transform.Cast<Transform>()
            .Where(hijo => hijo.name.StartsWith("Apoyo_"))
            .ToList();
        if (apoyos.Count >= 2) {
            Vector3 direccion = apoyos[apoyos.Count - 1].position - apoyos[0].position;
            direccion.y = 0f;
            if (direccion.sqrMagnitude > 0.01f) return direccion.normalized;
        }
        return Vector3.forward;
    }

    float CalcularDistanciaEncuadre(Bounds limites, Quaternion rotacion)
    {
        float aspecto = Mathf.Max(0.1f, camara.aspect);
        float tangenteVertical = Mathf.Tan(camara.fieldOfView * 0.5f * Mathf.Deg2Rad);
        float tangenteHorizontal = tangenteVertical * aspecto;
        Quaternion inversa = Quaternion.Inverse(rotacion);
        float requerida = Mathf.Max(distanciaMinima, distanciaMinimaEncuadre);

        foreach (Vector3 esquina in ObtenerEsquinas(limites)) {
            Vector3 local = inversa * (esquina - pivot);
            requerida = Mathf.Max(requerida, Mathf.Abs(local.x) / tangenteHorizontal - local.z);
            requerida = Mathf.Max(requerida, Mathf.Abs(local.y) / tangenteVertical - local.z);
        }
        return requerida;
    }

    IEnumerable<Vector3> ObtenerEsquinas(Bounds limites)
    {
        for (int x = -1; x <= 1; x += 2)
            for (int y = -1; y <= 1; y += 2)
                for (int z = -1; z <= 1; z += 2)
                    yield return limites.center + Vector3.Scale(
                        limites.extents,
                        new Vector3(x, y, z)
                    );
    }

    void AplicarOrbita()
    {
        Quaternion orbita = Quaternion.Euler(elevacionDeg, azimutDeg, 0f);
        transform.position = pivot + orbita * Vector3.back * distancia;
        // No atravesar el terreno (si esta visible): mantiene la camara arriba.
        if (terreno != null && terreno.gameObject.activeInHierarchy)
        {
            float suelo = terreno.SampleHeight(transform.position)
                + terreno.transform.position.y;
            float minY = suelo + alturaMinimaSobreTerreno;
            if (transform.position.y < minY)
            {
                transform.position += Vector3.up * (minY - transform.position.y);
                distancia = Vector3.Distance(transform.position, pivot);
                distanciaObjetivo = distancia;
            }
        }
        transform.rotation = Quaternion.LookRotation(pivot - transform.position, Vector3.up);
        if (tieneEncuadre) AjustarPlanosRecorte(limitesEncuadre);
    }

    void AjustarPlanosRecorte(Bounds limites)
    {
        // Distancia de la camara al centro de la linea (posicion REAL, no la
        // distancia orbital: el dolly avanza la camara sin cambiar el pivote).
        float distCentro = Vector3.Distance(camara.transform.position, limites.center);
        float radio = Mathf.Max(1f, limites.extents.magnitude);
        // Lejano: cubre toda la linea desde donde este la camara.
        camara.farClipPlane = Mathf.Max(1000f, distCentro + radio * 2f);
        // Cercano: pequeno para el zoom muy cercano, pero con una proporcion
        // segura (~4000:1) para no perder precision en el terreno lejano y que
        // NO desaparezca parte de la escena al acercarse.
        camara.nearClipPlane = Mathf.Clamp(camara.farClipPlane / 4000f, 0.05f, 50f);
    }
}
