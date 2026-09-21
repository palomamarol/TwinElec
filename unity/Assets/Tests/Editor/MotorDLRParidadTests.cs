using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEngine;

public class MotorDLRParidadTests
{
    [Serializable]
    class Tolerancias
    {
        public double relativa;
        public double absoluta;
    }

    [Serializable]
    public class Entrada
    {
        public double diametro_mm;
        public double seccion_mm2;
        public double r_low_ohm_km;
        public double r_high_ohm_km;
        public double t_low_C;
        public double t_high_C;
        public double emisividad;
        public double absortividad;
        public double ta_C;
        public double vw_m_s;
        public double direccion_viento_deg;
        public double he_m;
        public double lat_deg;
        public double zl_deg;
        public string fecha;
        public double hora_solar;
        public double ts_C;
    }

    [Serializable]
    public class Esperado
    {
        public double r_tavg_ohm_km;
        public double tfilm_C;
        public double viscosidad_kg_ms;
        public double densidad_aire_reynolds_kg_m3;
        public double conductividad_termica_kf_W_mC;
        public double reynolds;
        public double kangle;
        public double qcn_W_m;
        public double qc1_W_m;
        public double qc2_W_m;
        public double qc_W_m;
        public double qr_W_m;
        public double declinacion_solar_deg;
        public double angulo_horario_deg;
        public double altitud_solar_hc_deg;
        public double acimut_solar_zc_deg;
        public double theta_incidencia_deg;
        public double qs_nivel_mar_W_m2;
        public double k_solar;
        public double qse_W_m2;
        public double qs_W_m;
        public double radicando_A2;
        public double i_max_A;
    }

    [Serializable]
    public class Caso
    {
        public string nombre;
        public bool espera_error;
        public string error_esperado;
        public Entrada entrada;
        public Esperado esperado;
    }

    [Serializable]
    class DocumentoCasos
    {
        public int version_esquema;
        public Tolerancias tolerancias;
        public Caso[] casos;
    }

    static DocumentoCasos CargarDocumento()
    {
        string ruta = Path.Combine(
            Application.dataPath,
            "Tests",
            "Data",
            "casos_dlr_paridad.json"
        );
        if (!File.Exists(ruta))
            throw new FileNotFoundException("No existe el archivo común de casos DLR.", ruta);

        DocumentoCasos documento =
            JsonUtility.FromJson<DocumentoCasos>(File.ReadAllText(ruta));
        if (documento == null || documento.casos == null || documento.tolerancias == null)
            throw new InvalidDataException("El archivo común de casos DLR no es válido.");
        return documento;
    }

    static IEnumerable CasosCompartidos()
    {
        DocumentoCasos documento = CargarDocumento();
        foreach (Caso caso in documento.casos) {
            yield return new TestCaseData(
                caso,
                documento.tolerancias.relativa,
                documento.tolerancias.absoluta
            ).SetName($"MotorDLR_{caso.nombre}");
        }
    }

    [TestCaseSource(nameof(CasosCompartidos))]
    public void MotorCSharpCoincideConCasoCompartido(
        Caso caso,
        double toleranciaRelativa,
        double toleranciaAbsoluta
    )
    {
        MotorDLR.EntradasDLR entrada = CrearEntrada(caso.entrada);
        MotorDLR.ResultadoDLR resultado = MotorDLR.Calcular(entrada);

        if (caso.espera_error) {
            Assert.That(resultado.error, Is.EqualTo(caso.error_esperado));
            return;
        }

        Assert.That(resultado.error, Is.Null, $"{caso.nombre}: {resultado.error}");
        List<string> fallos = new List<string>();
        Esperado e = caso.esperado;

        Comparar(fallos, "r_tavg_ohm_km", e.r_tavg_ohm_km, resultado.r_tavg_ohm_km, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "tfilm_C", e.tfilm_C, resultado.tfilm_C, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "viscosidad_kg_ms", e.viscosidad_kg_ms, resultado.viscosidad_kg_ms, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "densidad_aire_reynolds_kg_m3", e.densidad_aire_reynolds_kg_m3, resultado.densidad_aire_kg_m3, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "conductividad_termica_kf_W_mC", e.conductividad_termica_kf_W_mC, resultado.conductividad_kf_W_mC, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "reynolds", e.reynolds, resultado.reynolds, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "kangle", e.kangle, resultado.kangle, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qcn_W_m", e.qcn_W_m, resultado.qcn_W_m, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qc1_W_m", e.qc1_W_m, resultado.qc1_W_m, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qc2_W_m", e.qc2_W_m, resultado.qc2_W_m, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qc_W_m", e.qc_W_m, resultado.qc_W_m, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qr_W_m", e.qr_W_m, resultado.qr_W_m, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "declinacion_solar_deg", e.declinacion_solar_deg, resultado.declinacion_solar_deg, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "angulo_horario_deg", e.angulo_horario_deg, resultado.angulo_horario_deg, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "altitud_solar_hc_deg", e.altitud_solar_hc_deg, resultado.altitud_solar_hc_deg, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "acimut_solar_zc_deg", e.acimut_solar_zc_deg, resultado.acimut_solar_zc_deg, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "theta_incidencia_deg", e.theta_incidencia_deg, resultado.theta_incidencia_deg, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qs_nivel_mar_W_m2", e.qs_nivel_mar_W_m2, resultado.qs_nivel_mar_W_m2, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "k_solar", e.k_solar, resultado.k_solar, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qse_W_m2", e.qse_W_m2, resultado.qse_W_m2, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "qs_W_m", e.qs_W_m, resultado.qs_W_m, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "radicando_A2", e.radicando_A2, resultado.radicando_A2, toleranciaRelativa, toleranciaAbsoluta);
        Comparar(fallos, "i_max_A", e.i_max_A, resultado.i_max_A, toleranciaRelativa, toleranciaAbsoluta);

        Assert.That(fallos, Is.Empty, string.Join("\n", fallos));
    }

    static MotorDLR.EntradasDLR CrearEntrada(Entrada e)
    {
        return new MotorDLR.EntradasDLR
        {
            diametro_mm = e.diametro_mm,
            seccion_mm2 = e.seccion_mm2,
            r_low_ohm_km = e.r_low_ohm_km,
            r_high_ohm_km = e.r_high_ohm_km,
            t_low_C = e.t_low_C,
            t_high_C = e.t_high_C,
            emisividad = e.emisividad,
            absortividad = e.absortividad,
            ta_C = e.ta_C,
            vw_m_s = e.vw_m_s,
            direccion_viento_deg = e.direccion_viento_deg,
            he_m = e.he_m,
            lat_deg = e.lat_deg,
            zl_deg = e.zl_deg,
            fecha = e.fecha,
            hora_solar = e.hora_solar,
            ts_C = e.ts_C
        };
    }

    static void Comparar(
        List<string> fallos,
        string magnitud,
        double esperado,
        double obtenido,
        double toleranciaRelativa,
        double toleranciaAbsoluta
    )
    {
        double tolerancia = Math.Max(
            toleranciaAbsoluta,
            Math.Abs(esperado) * toleranciaRelativa
        );
        if (double.IsNaN(obtenido) || double.IsInfinity(obtenido)
            || Math.Abs(obtenido - esperado) > tolerancia) {
            fallos.Add(
                $"{magnitud}: esperado={esperado:R}, obtenido={obtenido:R}, "
                + $"tolerancia={tolerancia:R}"
            );
        }
    }
}
