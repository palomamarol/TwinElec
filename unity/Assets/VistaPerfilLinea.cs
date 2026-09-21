using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// VistaPerfilLinea — Pestaña "Vista perfil" del gemelo digital: muestra la
/// linea en 2D (perfil) en TIEMPO REAL.
/// ============================================================================
/// El perfil aplana la linea concatenando los vanos 1-2, 2-3, 3-4... uno a
/// continuacion del otro (como si NO hubiese apoyos de angulo). El eje X es la
/// distancia horizontal acumulada y el eje Y la cota, con una exageracion
/// vertical para que se aprecien flechas y alturas. Se dibuja cada frame:
///   - La orografia real (Terrain de Unity) bajo la linea.
///   - Cada torre como una linea vertical (suelo -> cabeza).
///   - Los conductores EXACTAMENTE como estan colgados en la escena 3D (la
///     misma catenaria con su flecha segun la temperatura actual).
/// Como se lee de la escena viva cada LateUpdate, SIEMPRE refleja los cambios
/// de Unity: temperatura (longitud/flecha de los cables), altura de apoyos,
/// angulos, cruce, etc. No es una imagen estatica: es una camara en vivo.
/// </summary>
public class VistaPerfilLinea : MonoBehaviour
{
    const int CapaPerfil = 8;
    const int MuestrasPorVano = 16;

    [Tooltip("Exageracion vertical del perfil (x1 = cota real).")]
    public float exageracionVertical = 6f;

    Camera camara;
    RenderTexture textura;
    RawImage imagen;
    Text textoVacio;
    GameObject raiz;
    GeneradorDeLinea generadorCache;

    readonly List<LineRenderer> poolCables = new List<LineRenderer>();
    readonly List<LineRenderer> poolTorres = new List<LineRenderer>();
    readonly List<TextMesh> poolEtiquetas = new List<TextMesh>();
    LineRenderer lineaTerreno;

    readonly Dictionary<string, AlturaCache> cacheAlturas =
        new Dictionary<string, AlturaCache>();
    Vector3[] posicionesCable = new Vector3[64];

    struct AlturaCache { public int childCount; public float topY; }
    struct CableInfo { public int fase; public LineRenderer lr; }

    bool activa;
    bool camaraPrincipalAjustada;

    // -----------------------------------------------------------------------
    // Ciclo de vida
    // -----------------------------------------------------------------------
    public void Activar(RawImage destino, Text vacio)
    {
        imagen = destino;
        textoVacio = vacio;
        activa = true;
        AjustarCamaraPrincipal();
        if (camara == null) CrearCamara();
        if (textura == null) CrearTextura();
        if (raiz == null) CrearGeometria();
        camara.enabled = true;
        camara.targetTexture = textura;
        if (raiz != null) raiz.SetActive(true);
        if (imagen != null)
        {
            imagen.texture = textura;
            imagen.gameObject.SetActive(true);
        }
    }

    public void Desactivar()
    {
        activa = false;
        if (camara != null) camara.enabled = false;
        if (raiz != null) raiz.SetActive(false);
        if (imagen != null) imagen.gameObject.SetActive(false);
        if (textoVacio != null) textoVacio.gameObject.SetActive(true);
    }

    /// <summary>Exporta la vista perfil ACTUAL (con los ultimos cambios de la
    /// escena: temperaturas, alturas, coordenadas...) como PNG en 'ruta'. Se
    /// renderiza la camara del perfil una vez aunque la pestana no este abierta,
    /// y despues se restaura el estado anterior.</summary>
    public void CapturarPNG(string ruta)
    {
        bool estabaActiva = activa;
        if (!estabaActiva)
        {
            activa = true;
            AjustarCamaraPrincipal();
            if (camara == null) CrearCamara();
            if (textura == null) CrearTextura();
            if (raiz == null) CrearGeometria();
            camara.enabled = true;
            camara.targetTexture = textura;
            raiz.SetActive(true);
        }
        try { Rebuild(); }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogWarning("VistaPerfil exportar: " + ex.Message);
        }
        camara.Render();

        RenderTexture anterior = RenderTexture.active;
        RenderTexture.active = textura;
        var tex = new Texture2D(textura.width, textura.height,
            TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, textura.width, textura.height), 0, 0);
        RenderTexture.active = anterior;
        tex.Apply();
        byte[] bytes = tex.EncodeToPNG();
        File.WriteAllBytes(ruta, bytes);
        Destroy(tex);

        if (!estabaActiva)
        {
            activa = false;
            camara.enabled = false;
            raiz.SetActive(false);
        }
    }

    void OnDestroy()
    {
        if (textura != null)
        {
            textura.Release();
            Destroy(textura);
            textura = null;
        }
    }

    void LateUpdate()
    {
        if (!activa) return;
        try { Rebuild(); }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogWarning("VistaPerfil: " + ex.Message);
        }
    }

    // -----------------------------------------------------------------------
    // Montaje
    // -----------------------------------------------------------------------
    void AjustarCamaraPrincipal()
    {
        if (camaraPrincipalAjustada) return;
        var camaraLinea = FindAnyObjectByType<CamaraLinea>();
        if (camaraLinea == null) return;
        var cam = camaraLinea.GetComponent<Camera>();
        if (cam == null) return;
        // La geometria 2D del perfil vive en la capa 8: la camara 3D no la pinta.
        cam.cullingMask &= ~(1 << CapaPerfil);
        camaraPrincipalAjustada = true;
    }

    void CrearCamara()
    {
        var go = new GameObject("CamaraPerfil");
        go.transform.SetParent(transform, false);
        camara = go.AddComponent<Camera>();
        camara.orthographic = true;
        camara.clearFlags = CameraClearFlags.SolidColor;
        camara.backgroundColor = new Color(0.028f, 0.042f, 0.06f, 1f);
        camara.cullingMask = 1 << CapaPerfil;
        camara.nearClipPlane = 0.3f;
        camara.farClipPlane = 5000f;
        camara.allowHDR = false;
        camara.allowMSAA = false;
        camara.enabled = false;
    }

    void CrearTextura()
    {
        textura = new RenderTexture(1280, 720, 24);
        textura.name = "RenderTextureVistaPerfil";
        textura.Create();
    }

    void CrearGeometria()
    {
        raiz = new GameObject("GeometriaPerfil");
        raiz.transform.SetParent(transform, false);
        raiz.layer = CapaPerfil;
        lineaTerreno = CrearLinea("TerrenoPerfil",
            new Color(0.52f, 0.6f, 0.48f, 1f), 1.4f);
    }

    LineRenderer CrearLinea(string nombre, Color color, float grosor)
    {
        var go = new GameObject(nombre);
        go.transform.SetParent(raiz.transform, false);
        go.layer = CapaPerfil;
        var lr = go.AddComponent<LineRenderer>();
        var mat = new Material(Shader.Find("Sprites/Default"));
        mat.color = color;
        lr.sharedMaterial = mat;
        lr.startColor = Color.white;
        lr.endColor = Color.white;
        lr.startWidth = grosor;
        lr.endWidth = grosor;
        lr.useWorldSpace = true;
        lr.loop = false;
        return lr;
    }


    // -----------------------------------------------------------------------
    // Rebuild en tiempo real desde la escena
    // -----------------------------------------------------------------------
    void Rebuild()
    {
        if (generadorCache == null)
            generadorCache = FindAnyObjectByType<GeneradorDeLinea>();
        var generador = generadorCache;
        if (generador == null || generador.terrenoUnity == null)
        {
            MostrarVacio("La línea aún no está construida en la escena 3D.");
            return;
        }
        Terrain terreno = generador.terrenoUnity;

        // Torres ordenadas por numero real del apoyo
        List<Transform> torres = new List<Transform>();
        foreach (Transform hijo in generador.transform)
            if (hijo.name.StartsWith("Apoyo_")) torres.Add(hijo);
        torres.Sort((a, b) => NumeroApoyo(a.name).CompareTo(NumeroApoyo(b.name)));
        if (torres.Count < 2)
        {
            MostrarVacio("La línea aún no está construida en la escena 3D.");
            return;
        }

        // Cables por vano (solo los de conductor, no los arcos de amarre)
        Dictionary<int, List<CableInfo>> porVano =
            new Dictionary<int, List<CableInfo>>();
        foreach (Transform hijo in generador.transform)
        {
            if (!hijo.name.StartsWith("Cable_Fase_")) continue;
            if (!TryParseVanoFase(hijo.name, out int vano, out int fase)) continue;
            var lr = hijo.GetComponent<LineRenderer>();
            if (lr == null) continue;
            if (!porVano.TryGetValue(vano, out var lista))
                porVano[vano] = lista = new List<CableInfo>();
            lista.Add(new CableInfo { fase = fase, lr = lr });
        }

        int numVanos = torres.Count - 1;
        Vector3[] baseTorre = new Vector3[torres.Count];
        for (int i = 0; i < torres.Count; i++) baseTorre[i] = torres[i].position;

        // Distancia horizontal de cada vano (la da el cable colgado en 3D)
        float[] distVano = new float[numVanos];
        for (int v = 0; v < numVanos; v++)
        {
            float d = Vector2.Distance(
                new Vector2(baseTorre[v].x, baseTorre[v].z),
                new Vector2(baseTorre[v + 1].x, baseTorre[v + 1].z));
            if (porVano.TryGetValue(v + 1, out var lista) && lista.Count > 0)
            {
                var lr = lista[0].lr;
                int n = lr.positionCount;
                if (n >= 2)
                {
                    if (n > posicionesCable.Length)
                        posicionesCable = new Vector3[n];
                    lr.GetPositions(posicionesCable);
                    Vector3 p0 = posicionesCable[0];
                    Vector3 p1 = posicionesCable[n - 1];
                    d = Vector2.Distance(
                        new Vector2(p0.x, p0.z), new Vector2(p1.x, p1.z));
                }
            }
            distVano[v] = Mathf.Max(1f, d);
        }

        // X acumulada de cada torre en el perfil (planos concatenados)
        float[] xTorre = new float[torres.Count];
        for (int i = 1; i < torres.Count; i++)
            xTorre[i] = xTorre[i - 1] + distVano[i - 1];

        bool primero = true;
        Bounds bb = new Bounds();
        void Incluir(Vector3 p)
        {
            if (primero) { bb = new Bounds(p, Vector3.zero); primero = false; }
            else bb.Encapsulate(p);
        }


        // ---- Conductores: misma catenaria de la escena, aplanada ----
        int cableIdx = 0;
        foreach (var kv in porVano)
        {
            int indice = Mathf.Clamp(kv.Key - 1, 0, numVanos - 1);
            float x0 = xTorre[indice];
            float d = distVano[indice];
            foreach (var info in kv.Value.OrderBy(c => c.fase))
            {
                var lr = info.lr;
                int n = lr.positionCount;
                if (n < 2) continue;
                if (n > posicionesCable.Length) posicionesCable = new Vector3[n];
                lr.GetPositions(posicionesCable);
                LineRenderer linea = ObtenerLinea(
                    poolCables, cableIdx, ColorParaFase(info.fase));
                linea.positionCount = n;
                for (int j = 0; j < n; j++)
                {
                    float t = j / (float)(n - 1);
                    Vector3 p = posicionesCable[j];
                    Vector3 q = new Vector3(
                        x0 + t * d, p.y * exageracionVertical, 0f);
                    linea.SetPosition(j, q);
                    Incluir(q);
                }
                cableIdx++;
            }
        }
        OcultarDesde(poolCables, cableIdx);

        // ---- Torres: linea vertical suelo -> cabeza ----
        for (int i = 0; i < torres.Count; i++)
        {
            float baseY = baseTorre[i].y;
            float top = ObtenerAlturaTop(torres[i]);
            LineRenderer linea = ObtenerLinea(
                poolTorres, i, new Color(0.78f, 0.84f, 0.92f, 1f));
            linea.positionCount = 2;
            linea.SetPosition(0,
                new Vector3(xTorre[i], baseY * exageracionVertical, 0f));
            linea.SetPosition(1,
                new Vector3(xTorre[i], top * exageracionVertical, 0f));
            Incluir(new Vector3(xTorre[i], baseY * exageracionVertical, 0f));
            Incluir(new Vector3(xTorre[i], top * exageracionVertical, 0f));

            TextMesh etiqueta = ObtenerEtiqueta(i);
            etiqueta.text = NumeroApoyo(torres[i].name).ToString();
            etiqueta.transform.position = new Vector3(
                xTorre[i], top * exageracionVertical + 14f, 0f);
        }
        OcultarDesde(poolTorres, torres.Count);
        OcultarEtiquetasDesde(torres.Count);

        // ---- Orografia bajo la linea ----
        int muestras = numVanos * MuestrasPorVano;
        Vector3[] pts = new Vector3[muestras + 1];
        int idx = 0;
        for (int v = 0; v < numVanos; v++)
        {
            for (int k = 0; k < MuestrasPorVano; k++)
            {
                float t = k / (float)MuestrasPorVano;
                Vector3 pos = Vector3.Lerp(baseTorre[v], baseTorre[v + 1], t);
                float y = terreno.SampleHeight(pos) + terreno.transform.position.y;
                pts[idx++] = new Vector3(
                    xTorre[v] + t * distVano[v], y * exageracionVertical, 0f);
            }
        }
        {
            Vector3 posUltima = baseTorre[numVanos];
            float yUltima = terreno.SampleHeight(posUltima)
                + terreno.transform.position.y;
            pts[idx] = new Vector3(
                xTorre[numVanos], yUltima * exageracionVertical, 0f);
        }
        lineaTerreno.positionCount = idx + 1;
        for (int i = 0; i <= idx; i++) lineaTerreno.SetPosition(i, pts[i]);

        if (primero)
        {
            MostrarVacio("No hay geometría que dibujar (construye la línea).");
            return;
        }
        if (textoVacio != null) textoVacio.gameObject.SetActive(false);

        // ---- Encuadre automatico (cubrir toda la linea con margen) ----
        float margen = 60f;
        float aspect = textura != null
            ? (float)textura.width / (float)textura.height : 16f / 9f;
        float ancho = (bb.size.x * 0.5f + margen) / aspect;
        float alto = bb.size.y * 0.5f + margen;
        camara.orthographicSize = Mathf.Max(ancho, alto, 20f);
        camara.transform.position =
            new Vector3(bb.center.x, bb.center.y, -600f);
        camara.transform.rotation = Quaternion.identity;

        // Etiquetas a escala de la vista (se mantienen legibles al encuadrar)
        float tamEtiqueta = camara.orthographicSize * 0.012f;
        foreach (TextMesh et in poolEtiquetas)
            if (et != null) et.characterSize = tamEtiqueta;
    }

    void MostrarVacio(string mensaje)
    {
        if (textoVacio != null)
        {
            textoVacio.text = mensaje;
            textoVacio.gameObject.SetActive(true);
        }
    }


    // -----------------------------------------------------------------------
    // Altura real de cada torre (sigue los cambios de modulos del fuste)
    // -----------------------------------------------------------------------
    float ObtenerAlturaTop(Transform apoyo)
    {
        if (cacheAlturas.TryGetValue(apoyo.name, out AlturaCache c)
            && c.childCount == apoyo.childCount)
            return c.topY;

        float maxY = float.MinValue;
        var pila = new Stack<Transform>();
        pila.Push(apoyo);
        while (pila.Count > 0)
        {
            var t = pila.Pop();
            var r = t.GetComponent<Renderer>();
            if (r != null) maxY = Mathf.Max(maxY, r.bounds.max.y);
            foreach (Transform hijo in t) pila.Push(hijo);
        }
        if (maxY <= float.MinValue + 1f) maxY = apoyo.position.y + 20f;

        cacheAlturas[apoyo.name] = new AlturaCache
        {
            childCount = apoyo.childCount,
            topY = maxY,
        };
        return maxY;
    }

    // -----------------------------------------------------------------------
    // Pools de geometria
    // -----------------------------------------------------------------------
    LineRenderer ObtenerLinea(List<LineRenderer> pool, int indice, Color color)
    {
        while (pool.Count <= indice)
            pool.Add(CrearLinea("LineaPerfil_" + pool.Count, color, 1f));
        var lr = pool[indice];
        lr.gameObject.SetActive(true);
        lr.sharedMaterial.color = color;
        return lr;
    }

    void OcultarDesde(List<LineRenderer> pool, int desde)
    {
        for (int i = desde; i < pool.Count; i++)
            if (pool[i] != null) pool[i].gameObject.SetActive(false);
    }

    TextMesh ObtenerEtiqueta(int indice)
    {
        while (poolEtiquetas.Count <= indice)
        {
            var go = new GameObject("EtiquetaPerfil_" + poolEtiquetas.Count);
            go.transform.SetParent(raiz.transform, false);
            go.layer = CapaPerfil;
            var tm = go.AddComponent<TextMesh>();
            tm.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            tm.fontSize = 48;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = new Color(1f, 0.85f, 0.4f);
            tm.characterSize = 1f;
            poolEtiquetas.Add(tm);
        }
        var et = poolEtiquetas[indice];
        et.gameObject.SetActive(true);
        return et;
    }

    void OcultarEtiquetasDesde(int desde)
    {
        for (int i = desde; i < poolEtiquetas.Count; i++)
            if (poolEtiquetas[i] != null) poolEtiquetas[i].gameObject.SetActive(false);
    }

    // -----------------------------------------------------------------------
    // Utilidades
    // -----------------------------------------------------------------------
    Color ColorParaFase(int fase)
    {
        switch (Mathf.Abs(fase) % 3)
        {
            case 0: return new Color(0.4f, 0.82f, 1f);   // fase 1 -> azul
            case 1: return new Color(1f, 0.6f, 0.35f);    // fase 2 -> naranja
            default: return new Color(0.5f, 1f, 0.6f);    // fase 3 -> verde
        }
    }

    int NumeroApoyo(string nombre)
    {
        // "Apoyo_5__C_ATC-..." -> 5
        string[] partes = nombre.Split('_');
        if (partes.Length >= 2 && int.TryParse(partes[1], out int n)) return n;
        return 0;
    }

    bool TryParseVanoFase(string nombre, out int vano, out int fase)
    {
        vano = fase = 0;
        // "Cable_Fase_3_Vano_5"
        string[] partes = nombre.Split('_');
        if (partes.Length < 5) return false;
        if (partes[0] != "Cable" || partes[1] != "Fase" || partes[3] != "Vano")
            return false;
        return int.TryParse(partes[2], out fase)
            && int.TryParse(partes[4], out vano);
    }
}

