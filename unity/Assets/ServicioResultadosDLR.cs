using System;
using System.IO;
using UnityEngine;

/// <summary>Adapta los resultados batch de Python a un estado observable para la UI.</summary>
[DisallowMultipleComponent]
public class ServicioResultadosDLR : MonoBehaviour
{
    [Serializable]
    public class InstantaneaResultados
    {
        public int numMunicipios;
        public string municipioCritico = "—";
        public float limiteLineaA = -1f;
        public float iRlatA = -1f;
        [TextArea(3, 10)] public string listaMunicipios = "";
        [TextArea(5, 20)] public string prevision = "";
    }

    [Serializable] private class Franja
    {
        public string fecha;
        public string hora;
        public float ta_C;
        public float vw_m_s;
        public float direccion_viento_deg;
        public float i_max_A;
    }

    [Serializable] private class Prediccion { public Franja[] franjas; }

    [Header("Resultados producidos por Python")]
    public string archivoMunicipios = "meteorologia_por_municipio.json";
    public string archivoRlat = "intensidadreglamento.json";
    public string archivoPrevision = "prediccion_futura.json";
    public bool actualizarPeriodicamente = true;
    [Min(1f)] public float intervaloActualizacionSeg = 60f;

    [SerializeField] private InstantaneaResultados datosActuales =
        new InstantaneaResultados();
    public InstantaneaResultados DatosActuales => datosActuales;
    public event Action<InstantaneaResultados> Actualizada;

    private float temporizador;

    void Awake() => ActualizarAhora();

    void Update()
    {
        if (!actualizarPeriodicamente) return;
        temporizador += Time.deltaTime;
        if (temporizador < Mathf.Max(1f, intervaloActualizacionSeg)) return;
        temporizador = 0f;
        ActualizarAhora();
    }

    [ContextMenu("Actualizar resultados DLR ahora")]
    public void ActualizarAhora()
    {
        InstantaneaResultados nueva = new InstantaneaResultados();
        LeerMunicipios(nueva);
        LeerRlat(nueva);
        LeerPrevision(nueva);
        datosActuales = nueva;
        Actualizada?.Invoke(datosActuales);
    }

    private string Ruta(string nombre) => Path.Combine(RutasGemelo.RutaAssetsGemelo(), nombre);

    private void LeerMunicipios(InstantaneaResultados destino)
    {
        try
        {
            string ruta = Ruta(archivoMunicipios);
            if (!File.Exists(ruta)) return;
            var json = Json.Deserialize(File.ReadAllText(ruta))
                as System.Collections.Generic.Dictionary<string, object>;
            if (json == null) return;
            if (json.TryGetValue("limite_linea_A", out object lim) && lim != null)
                destino.limiteLineaA = Convert.ToSingle(
                    lim, System.Globalization.CultureInfo.InvariantCulture);
            if (json.TryGetValue("limite_detalle", out object det)
                && det is System.Collections.Generic.Dictionary<string, object> detalle)
            {
                if (detalle.TryGetValue("municipio_critico", out object mc))
                    destino.municipioCritico = mc?.ToString() ?? "—";
                if (detalle.TryGetValue("num_municipios", out object nm))
                    destino.numMunicipios = Convert.ToInt32(nm);
            }
            if (json.TryGetValue("municipios", out object mun)
                && mun is System.Collections.Generic.List<object> lista)
            {
                System.Text.StringBuilder texto = new System.Text.StringBuilder();
                foreach (object elemento in lista)
                {
                    var grupo = elemento as System.Collections.Generic.Dictionary<string, object>;
                    if (grupo == null) continue;
                    string nombre = grupo.TryGetValue("nombre", out object n) ? n?.ToString() : "—";
                    string ine = grupo.TryGetValue("codigo_ine", out object c) ? c?.ToString() : "";
                    string apoyos = grupo.TryGetValue("num_apoyos", out object a) ? a?.ToString() : "?";
                    string imax = grupo.TryGetValue("i_max_A", out object i) ? i?.ToString() : "?";
                    texto.AppendLine($"• {nombre} (INE {ine}): {apoyos} apoyos — I_max={imax} A");
                }
                destino.listaMunicipios = texto.ToString();
            }
        }
        catch (Exception ex) { Debug.LogWarning("Resultados DLR (municipios): " + ex.Message); }
    }

    private void LeerRlat(InstantaneaResultados destino)
    {
        try
        {
            string ruta = Ruta(archivoRlat);
            if (!File.Exists(ruta)) return;
            // Se usa Json.Deserialize (parser robusto del proyecto), igual que en
            // municipios: JsonUtility con clases privadas anidadas es fragil.
            var doc = Json.Deserialize(File.ReadAllText(ruta))
                as System.Collections.Generic.Dictionary<string, object>;
            if (doc != null && doc.TryGetValue("resultado", out object rObj)
                && rObj is System.Collections.Generic.Dictionary<string, object> resultado
                && resultado.TryGetValue("intensidad_reglamento_A", out object valor)
                && valor != null)
            {
                destino.iRlatA = Convert.ToSingle(
                    valor, System.Globalization.CultureInfo.InvariantCulture);
            }
        }
        catch (Exception ex) { Debug.LogWarning("Resultados DLR (RLAT): " + ex.Message); }
    }

    private void LeerPrevision(InstantaneaResultados destino)
    {
        try
        {
            string ruta = Ruta(archivoPrevision);
            if (!File.Exists(ruta)) return;
            Prediccion p = JsonUtility.FromJson<Prediccion>(File.ReadAllText(ruta));
            if (p?.franjas == null) return;
            System.Text.StringBuilder texto = new System.Text.StringBuilder();
            int cantidad = Mathf.Min(p.franjas.Length, 12);
            for (int i = 0; i < cantidad; i++)
            {
                Franja f = p.franjas[i];
                string fecha = !string.IsNullOrEmpty(f.fecha) && f.fecha.Length >= 5
                    ? f.fecha.Substring(5) : (f.fecha ?? "—");
                string direccion = f.direccion_viento_deg >= 0f
                    ? $"{f.direccion_viento_deg:0}°" : "—";
                texto.AppendLine($"{fecha} {f.hora}: {f.ta_C:0}°C, {f.vw_m_s:0.#} m/s {direccion} → I_max={f.i_max_A:0} A");
            }
            destino.prevision = texto.ToString();
        }
        catch (Exception ex) { Debug.LogWarning("Resultados DLR (previsión): " + ex.Message); }
    }
}
