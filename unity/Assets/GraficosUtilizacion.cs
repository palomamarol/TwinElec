using UnityEngine;
using System;
using System.Collections.Generic;
using System.IO;

/// <summary>
/// GraficosUtilizacion — Grafico de utilizacion (Tema 10) por apoyo en Unity.
/// ========================================================================
/// Lee Assets/graficos_utilizacion.json (generado por Python) y dibuja, para
/// cada apoyo de la linea, el grafico L-N con:
///   - ejes L (semisuma de vanos, eje X) y N (diferencia de tangentes, eje Y)
///   - las rectas de las hipotesis reglamentarias (a*L + b*N + c = 0)
///   - el vano maximo (recta vertical)
///   - la zona utilizable (izquierda y arriba)
///   - el punto real del apoyo y su veredicto (valido / no valido)
///
/// USO: anadir como componente a un GameObject de la escena. Cambiar de apoyo
/// con las flechas izquierda/derecha o las teclas 1..9.
/// GENERAL: no contiene valores de ninguna linea concreta.
/// </summary>
public class GraficosUtilizacion : MonoBehaviour
{
    [Header("Configuracion")]
    public string archivoJson = "Assets/graficos_utilizacion.json";
    public bool mostrarGrafico = false;
    public float escala = 1f;
    [Range(1, 9)] public int apoyoSeleccionado = 1;

    // Datos leidos del JSON
    private List<Dictionary<string, object>> apoyos = new List<Dictionary<string, object>>();
    private Dictionary<string, object> linea = null;
    private bool cargado = false;
    private string error = "";

    void Awake()
    {
        Cargar();
    }

    void Update()
    {
        if (!mostrarGrafico) return;
        if (Input.GetKeyDown(KeyCode.RightArrow)) apoyosSet(apoyoSeleccionado + 1);
        if (Input.GetKeyDown(KeyCode.LeftArrow)) apoyosSet(apoyoSeleccionado - 1);
        for (int k = 1; k <= 9; k++)
            if (Input.GetKeyDown(KeyCode.Alpha0 + k)) apoyoSeleccionado = k;
    }

    void apoyosSet(int n)
    {
        if (n >= 1 && n <= apoyos.Count) apoyoSeleccionado = n;
    }

    void Cargar()
    {
        try
        {
            string json = null;
            if (File.Exists(archivoJson))
                json = File.ReadAllText(archivoJson, System.Text.Encoding.UTF8);
            else
            {
                // Fallback: buscar en la carpeta Assets del proyecto
                string rutaAlt = Path.Combine(RutasGemelo.RutaAssetsGemelo(), "graficos_utilizacion.json");
                if (File.Exists(rutaAlt))
                    json = File.ReadAllText(rutaAlt, System.Text.Encoding.UTF8);
                else
                {
                    error = "No se encontro " + archivoJson + " ni " + rutaAlt;
                    return;
                }
            }
            var doc = Json.Deserialize(json) as Dictionary<string, object>;
            if (doc == null) { error = "JSON invalido"; return; }
            if (doc.ContainsKey("linea")) linea = doc["linea"] as Dictionary<string, object>;
            if (doc.ContainsKey("apoyos") && doc["apoyos"] is List<object> lista)
            {
                apoyos.Clear();
                foreach (var item in lista)
                {
                    var a = item as Dictionary<string, object>;
                    if (a != null) apoyos.Add(a);
                }
                // Orden por numero: el grafico dibujado se selecciona por numero,
                // no por posicion del array (el JSON puede venir desordenado).
                apoyos.Sort((x, y) => ParseNumero(x).CompareTo(ParseNumero(y)));
            }
            cargado = true;
        }
        catch (Exception ex)
        {
            error = "No se pudo leer el JSON: " + ex.Message;
        }
    }

    // ====================================================================
    // DIBUJADO DEL GRAFICO (OnGUI)
    // ====================================================================
    void OnGUI()
    {
        if (!mostrarGrafico) return;
        if (!cargado)
        {
            GUI.Label(new Rect(12, 12, 700, 40), "GraficosUtilizacion: " + error);
            return;
        }
        if (apoyos.Count == 0) return;

        int idx = Mathf.Clamp(apoyoSeleccionado - 1, 0, apoyos.Count - 1);
        var apoyo = BuscarApoyo(apoyoSeleccionado);
        if (apoyo == null) apoyo = apoyos[idx];

        float x0 = 60f * escala;
        float y0 = 100f * escala;
        float ancho = 560f * escala;
        float alto = 400f * escala;

        // --- Cabecera: datos de la linea y del apoyo ---
        string cabecera = string.Format("Apoyo #{0}  {1}  ({2})   Zona {3}   Montaje {4}   L={5}  N={6}",
            Obj(apoyo, "numero"), Obj(apoyo, "tipo"), Obj(apoyo, "tipo_texto"),
            Obj(apoyo, "zona"), Obj(apoyo, "montaje"),
            Fmt(ObjNum(apoyo, "punto_real_L"), 2), Fmt(ObjNum(apoyo, "punto_real_N"), 3));
        GUI.Label(new Rect(12, 10, 900, 24), "GRAFICO DE UTILIZACION - Tema 10", Titulo());
        GUI.Label(new Rect(12, 36, 900, 22), cabecera, Normal());
        if (linea != null)
            GUI.Label(new Rect(12, 58, 900, 20),
                string.Format("Conductor {0} | {1} kV | {2} | viento {3} km/h",
                    Obj(linea, "conductor"), Obj(linea, "tension_linea_kv"),
                    Obj(linea, "categoria"), Obj(linea, "viento_kmh")), Pequenio());

        // --- Rango del eje L y rango de N ---
        float lMax = CalcularLMax(apoyo);
        float nMin = -1f, nMax = 1f;

        // --- Fondo del area de dibujo ---
        GUI.color = new Color(0.05f, 0.08f, 0.12f, 0.85f);
        GUI.DrawTexture(new Rect(x0, y0, ancho, alto), Texture2D.whiteTexture);
        GUI.color = Color.white;

        // --- Zona utilizable (relleno) ---
        var zona = ObjList(apoyo, "zona_utilizable");
        if (zona != null && zona.Count > 2)
            DibujarPoligono(zona, x0, y0, ancho, alto, lMax, nMin, nMax,
                new Color(0.25f, 0.7f, 0.35f, 0.28f));

        // --- Rectas ---
        var rectas = ObjDict(apoyo, "rectas");
        if (rectas != null)
        {
            int leyenda = 0;
            foreach (var kv in rectas)
            {
                var r = kv.Value as Dictionary<string, object>;
                if (r == null) continue;
                Color color = ColorParaRecta(kv.Key);
                if ("vertical".Equals(Obj(r, "tipo")))
                {
                    float lv = Conv(Obj(r, "L"));
                    DibujarLinea(MundoAPantalla(lv, nMin, x0, y0, ancho, alto, lMax, nMin, nMax),
                                 MundoAPantalla(lv, nMax, x0, y0, ancho, alto, lMax, nMin, nMax),
                                 2f, color);
                }
                else
                {
                    float a = Conv(Obj(r, "a")), b = Conv(Obj(r, "b")), c = Conv(Obj(r, "c"));
                    Vector2 p1 = MundoAPantalla((-b * nMin - c) / a, nMin, x0, y0, ancho, alto, lMax, nMin, nMax);
                    Vector2 p2 = MundoAPantalla((-b * nMax - c) / a, nMax, x0, y0, ancho, alto, lMax, nMin, nMax);
                    DibujarLinea(p1, p2, 2f, color);
                }
                GUI.Label(new Rect(x0 + ancho + 10, y0 + 8 + 18f * leyenda, 280, 18),
                    "- " + Obj(r, "label"), Pequenio());
                leyenda++;
            }
        }

        // --- Ejes y etiquetas ---
        DibujarLinea(new Vector2(x0, y0 + alto), new Vector2(x0 + ancho, y0 + alto), 3f, Color.white);
        DibujarLinea(new Vector2(x0, y0), new Vector2(x0, y0 + alto), 3f, Color.white);
        GUI.Label(new Rect(x0 + ancho / 2 - 60, y0 + alto + 8, 140, 20), "L (semisuma de vanos, m)", Pequenio());
        GUI.Label(new Rect(x0 - 30, y0 + alto / 2 - 8, 60, 20), "N", Pequenio());
        for (float l = 0; l <= lMax + 0.01f; l += lMax / 5f)
            GUI.Label(new Rect(x0 + l / lMax * ancho - 15, y0 + alto + 22, 40, 16),
                Mathf.RoundToInt(l).ToString(), Pequenio());
        GUI.Label(new Rect(x0 + 4, y0 - 18, 60, 18), "N=" + nMax.ToString("0.0"), Pequenio());
        GUI.Label(new Rect(x0 + 4, y0 + alto - 4, 60, 18), "N=" + nMin.ToString("0.0"), Pequenio());

        // --- Punto real y veredicto ---
        float lReal = Conv(ObjNum(apoyo, "punto_real_L"));
        float nReal = Conv(ObjNum(apoyo, "punto_real_N"));
        Vector2 punto = MundoAPantalla(lReal, nReal, x0, y0, ancho, alto, lMax, nMin, nMax);
        GUI.color = Color.red;
        GUI.DrawTexture(new Rect(punto.x - 4, punto.y - 4, 8, 8), Texture2D.whiteTexture);
        GUI.color = Color.white;
        bool valido = PuntoEnPoligono(lReal, nReal, zona, lMax, nMin, nMax);
        GUIStyle veredicto = new GUIStyle(GUI.skin.label)
        {
            fontStyle = FontStyle.Bold, fontSize = Mathf.RoundToInt(14 * escala)
        };
        veredicto.normal.textColor = valido ? Color.green : Color.red;
        GUI.Label(new Rect(punto.x + 10, punto.y - 8, 240, 20),
            valido ? "APOYO VALIDO" : "APOYO NO VALIDO", veredicto);

        GUI.Label(new Rect(12, y0 + alto + 46, 700, 20),
            "Flechas <- ->: cambiar apoyo | Teclas 1-9: apoyo directo", Pequenio());
    }


    // ====================================================================
    // Utilidades de datos y dibujo
    // ====================================================================
    static float ObjNum(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave))
        {
            var v = d[clave];
            if (v is double dd) return (float)dd;
            if (v is long ll) return ll;
        }
        return 0f;
    }

    static string Obj(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] != null) return d[clave].ToString();
        return "";
    }

    static int ParseNumero(Dictionary<string, object> d)
    {
        int n;
        if (d != null && int.TryParse(Obj(d, "numero"), out n)) return n;
        return int.MaxValue;
    }

    /// <summary>Devuelve el apoyo cuyo 'numero' es exactamente n (nunca por la
    /// posicion del array, que puede venir desordenada en el JSON).</summary>
    Dictionary<string, object> BuscarApoyo(int n)
    {
        foreach (var item in apoyos)
            if (ParseNumero(item) == n) return item;
        if (n >= 1 && n <= apoyos.Count) return apoyos[n - 1];
        return null;
    }

    static Dictionary<string, object> ObjDict(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] is Dictionary<string, object> dd) return dd;
        return null;
    }

    static float Conv(object o)
    {
        if (o is double d) return (float)d;
        if (o is long l) return l;
        return 0f;
    }

    static List<object> ObjList(Dictionary<string, object> d, string clave)
    {
        if (d != null && d.ContainsKey(clave) && d[clave] is List<object> l) return l;
        return null;
    }

    static string Fmt(float v, int dec)
    {
        return v.ToString("F" + dec, System.Globalization.CultureInfo.InvariantCulture);
    }

    float CalcularLMax(Dictionary<string, object> apoyo)
    {
        float lm = 400f;
        var rectas = ObjDict(apoyo, "rectas");
        if (rectas != null)
        {
            foreach (var kv in rectas)
            {
                var r = kv.Value as Dictionary<string, object>;
                if (r == null) continue;
                if ("vertical".Equals(Obj(r, "tipo")))
                {
                    float lv = Conv(Obj(r, "L"));
                    if (lv > lm) lm = lv;
                }
                else
                {
                    float a = Conv(Obj(r, "a")), b = Conv(Obj(r, "b")), c = Conv(Obj(r, "c"));
                    if (Mathf.Abs(a) < 1e-6f) continue;
                    float l0 = (-c) / a;
                    float l1 = (-b - c) / a;
                    float l2 = (b - c) / a;
                    float m = Mathf.Max(Mathf.Abs(l0), Mathf.Max(Mathf.Abs(l1), Mathf.Abs(l2)));
                    if (m > lm) lm = m;
                }
            }
        }
        return lm * 1.05f + 1f;
    }


    Vector2 MundoAPantalla(float l, float n, float x0, float y0, float ancho, float alto,
                           float lMax, float nMin, float nMax)
    {
        float x = x0 + (l / lMax) * ancho;
        float y = y0 + ((nMax - n) / (nMax - nMin)) * alto;
        return new Vector2(x, y);
    }

    void DibujarLinea(Vector2 a, Vector2 b, float grosor, Color color)
    {
        Vector2 delta = b - a;
        float angulo = Mathf.Atan2(delta.y, delta.x) * Mathf.Rad2Deg;
        float longitud = delta.magnitude;
        if (longitud < 0.01f) return;
        GUIUtility.RotateAroundPivot(angulo, a);
        GUI.color = color;
        GUI.DrawTexture(new Rect(a.x, a.y, longitud, grosor), Texture2D.whiteTexture);
        GUI.color = Color.white;
        GUIUtility.RotateAroundPivot(-angulo, a);
    }


    void DibujarPoligono(List<object> zona, float x0, float y0, float ancho, float alto,
                         float lMax, float nMin, float nMax, Color color)
    {
        int pasosN = 60;
        float dn = (nMax - nMin) / pasosN;
        for (int i = 0; i <= pasosN; i++)
        {
            float n = nMin + dn * i;
            float lInf = -1f, lSup = -1f;
            // Cruce de aristas del poligono con la linea horizontal N=n
            for (int k = 0; k < zona.Count; k++)
            {
                var p1 = zona[k] as List<object>;
                var p2 = zona[(k + 1) % zona.Count] as List<object>;
                if (p1 == null || p2 == null || p1.Count < 2 || p2.Count < 2) continue;
                float n1 = Conv(p1[1]), n2 = Conv(p2[1]);
                if ((n1 <= n && n2 > n) || (n2 <= n && n1 > n))
                {
                    float l1 = Conv(p1[0]), l2 = Conv(p2[0]);
                    float l = l1 + (n - n1) / (n2 - n1) * (l2 - l1);
                    if (lInf < 0f || l < lInf) lInf = l;
                    if (l > lSup) lSup = l;
                }
            }
            if (lInf >= 0f && lSup > lInf)
            {
                Vector2 pa = MundoAPantalla(lInf, n, x0, y0, ancho, alto, lMax, nMin, nMax);
                Vector2 pb = MundoAPantalla(lSup, n, x0, y0, ancho, alto, lMax, nMin, nMax);
                DibujarLinea(pa, pb, 4f, color);
            }
        }
    }

    bool PuntoEnPoligono(float l, float n, List<object> zona, float lMax, float nMin, float nMax)
    {
        if (zona == null || zona.Count < 3) return false;
        bool dentro = false;
        for (int i = 0, j = zona.Count - 1; i < zona.Count; j = i++)
        {
            var pi = zona[i] as List<object>;
            var pj = zona[j] as List<object>;
            if (pi == null || pj == null || pi.Count < 2 || pj.Count < 2) continue;
            float xi = Conv(pi[0]), yi = Conv(pi[1]);
            float xj = Conv(pj[0]), yj = Conv(pj[1]);
            if ((yi > n) != (yj > n) && l < (xj - xi) * (n - yi) / (yj - yi) + xi)
                dentro = !dentro;
        }
        return dentro;
    }

    Color ColorParaRecta(string clave)
    {
        switch (clave)
        {
            case "1a": return Color.cyan;
            case "2a": return new Color(1f, 0.6f, 0.2f);
            case "2a_VH": return new Color(1f, 0.3f, 0.6f);
            case "3a": return Color.yellow;
            case "vano_maximo": return Color.green;
            case "desviacion_cadena": return Color.magenta;
            case "cruceta": return Color.gray;
            default: return Color.white;
        }
    }

    GUIStyle Titulo()
    {
        return new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(16 * escala), fontStyle = FontStyle.Bold };
    }

    GUIStyle Normal()
    {
        return new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(13 * escala) };
    }

    GUIStyle Pequenio()
    {
        return new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(11 * escala) };
    }
}
