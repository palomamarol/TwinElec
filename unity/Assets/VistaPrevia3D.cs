using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// VistaPrevia3D — Renderiza un modelo FBX del catalogo (Assets/Resources/
/// ModelosCruceta) en un RawImage de la interfaz, como un "selector de
/// personaje" de videojuego: al pinchar una gama/detalle (o una semicruceta),
/// la pieza 3D aparece a la derecha de la ventana.
///
/// Cada ventana crea su propia instancia (camara + RenderTexture + modelo).
/// El modelo se dibuja en una capa propia (8) y se oculta de la camara
/// principal para no aparecer en la escena de la linea.
/// </summary>
public class VistaPrevia3D
{
    const int CAPA_PREVIEW = 8;

    public RenderTexture textura;
    Camera camara;
    GameObject contenedor;
    GameObject modelo;

    public VistaPrevia3D(RawImage imagenDestino, string nombre, int ancho, int alto)
    {
        textura = new RenderTexture(Mathf.Max(64, ancho), Mathf.Max(64, alto), 24);
        textura.Create();
        imagenDestino.texture = textura;
        imagenDestino.color = Color.white;

        var go = new GameObject(nombre);
        camara = go.AddComponent<Camera>();
        camara.targetTexture = textura;
        camara.clearFlags = CameraClearFlags.SolidColor;
        camara.backgroundColor = new Color(0.055f, 0.075f, 0.12f);
        camara.cullingMask = 1 << CAPA_PREVIEW;
        camara.orthographic = true;
        camara.depth = 99;
        camara.enabled = false;
        camara.transform.position = new Vector3(0, 0, -12f);
        camara.transform.rotation = Quaternion.identity;

        AsegurarCamaraPrincipal();
    }

    /// <summary>La camara principal no debe dibujar los modelos de la vista
    /// previa (se excluye la capa 8). Se re-aplica cada vez por robustez.</summary>
    void AsegurarCamaraPrincipal()
    {
        Camera principal = Camera.main;
        if (principal != null)
            principal.cullingMask &= ~(1 << CAPA_PREVIEW);
    }

    /// <summary>
    /// Resuelve el nombre de recurso real en ModelosCruceta/ a partir de una
    /// referencia base del catalogo (ASC-12, C_ASC-12, ATC45-12, BH15-ANXC...).
    /// Prueba el nombre directo, el prefijo C_ (Serie C) y las variantes de
    /// altura _H de las semicrucetas atirantadas ANDEL.
    /// </summary>
    public static string ResolverRecurso(string nombreBase)
    {
        if (string.IsNullOrWhiteSpace(nombreBase)) return null;
        string nombre = nombreBase.Trim();
        if (Resources.Load<GameObject>("ModelosCruceta/" + nombre) != null)
            return nombre;
        string cPrefijo = nombre.StartsWith("C_") ? nombre : "C_" + nombre;
        if (Resources.Load<GameObject>("ModelosCruceta/" + cPrefijo) != null)
            return cPrefijo;
        foreach (string suf in new[] { "_H750", "_H600", "_H500", "_H375" })
        {
            if (Resources.Load<GameObject>("ModelosCruceta/" + nombre + suf) != null)
                return nombre + suf;
            if (Resources.Load<GameObject>("ModelosCruceta/" + cPrefijo + suf) != null)
                return cPrefijo + suf;
        }
        return null;
    }

    /// <summary>Muestra el modelo de la referencia indicada. Con 'vistaPlanta'
    /// = true la camara se coloca ARRIBA del modelo (vista en planta), ideal
    /// para apreciar la forma triangular de las semicrucetas planas.</summary>
    public void Mostrar(string nombreBase, bool vistaPlanta = false)
    {
        LimpiarModelo();
        string recurso = ResolverRecurso(nombreBase);
        if (recurso == null)
        {
            if (camara != null) camara.enabled = false;
            return;
        }
        GameObject prefab = Resources.Load<GameObject>("ModelosCruceta/" + recurso);
        if (prefab == null)
        {
            if (camara != null) camara.enabled = false;
            return;
        }
        contenedor = new GameObject("Preview3D_" + recurso);
        contenedor.transform.position = Vector3.zero;
        // En planta el modelo queda alineado con los ejes (recto, paralelo al
        // marco inferior o derecho del panel); en 3/4 se inclina 30 grados.
        contenedor.transform.rotation = vistaPlanta
            ? Quaternion.identity
            : Quaternion.Euler(0f, -30f, 0f);
        modelo = Object.Instantiate(prefab, contenedor.transform, false);
        AsignarCapa(contenedor.transform, CAPA_PREVIEW);
        DesactivarColisionadores(contenedor.transform);
        AsegurarCamaraPrincipal();
        if (camara != null) camara.enabled = true;
        Encuadrar(vistaPlanta);
    }

    void Encuadrar(bool vistaPlanta = false)
    {
        if (modelo == null || camara == null || textura == null) return;
        Renderer[] renderers = modelo.GetComponentsInChildren<Renderer>();
        if (renderers.Length == 0) return;
        Bounds limites = renderers[0].bounds;
        for (int i = 1; i < renderers.Length; i++)
            limites.Encapsulate(renderers[i].bounds);
        // En planta la "altura" de la vista es el eje Z; en perfil es el Y.
        float aspecto = (float)textura.width / textura.height;
        float anchoVista = limites.size.x;
        float altoVista = vistaPlanta ? limites.size.z : limites.size.y;
        float necesario = Mathf.Max(altoVista, anchoVista / aspecto);
        camara.orthographicSize = Mathf.Max(necesario * 0.68f, 0.5f);
        Vector3 centro = limites.center;
        float distancia = Mathf.Max(12f, necesario * 3f);
        if (vistaPlanta)
        {
            camara.transform.position = new Vector3(centro.x, centro.y + distancia, centro.z);
            camara.transform.rotation = Quaternion.LookRotation(
                centro - camara.transform.position, Vector3.forward);
        }
        else
        {
            camara.transform.position = new Vector3(centro.x, centro.y, centro.z - distancia);
            camara.transform.rotation = Quaternion.LookRotation(
                centro - camara.transform.position, Vector3.up);
        }
    }

    /// <summary>Oculta el modelo y detiene la camara (ventana cerrada).</summary>
    public void Ocultar()
    {
        LimpiarModelo();
        if (camara != null) camara.enabled = false;
    }

    /// <summary>Libera camara y textura (ya no se usara mas).</summary>
    public void Liberar()
    {
        Ocultar();
        if (camara != null) Object.Destroy(camara.gameObject);
        if (textura != null) textura.Release();
    }

    void LimpiarModelo()
    {
        if (contenedor != null)
        {
            Object.Destroy(contenedor);
            contenedor = null;
            modelo = null;
        }
    }

    void AsignarCapa(Transform t, int capa)
    {
        t.gameObject.layer = capa;
        foreach (Transform hijo in t)
            AsignarCapa(hijo, capa);
    }

    void DesactivarColisionadores(Transform t)
    {
        var col = t.GetComponent<Collider>();
        if (col != null) col.enabled = false;
        foreach (Transform hijo in t)
            DesactivarColisionadores(hijo);
    }
}
