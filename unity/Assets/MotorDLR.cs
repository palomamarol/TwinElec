using System;
using System.IO;
using UnityEngine;

/// <summary>
/// Motor de cálculo DLR (Dynamic Line Rating) basado en IEEE Std 738-2023.
/// Portado a C# desde dlr.py del proyecto TwinElec (Unity Digital Twin).
///
/// Este archivo es un MOTOR DE CÁLCULO PURO Y GENÉRICO: no conoce ninguna línea
/// concreta. Recibe propiedades del conductor, meteorología, geometría y posición,
/// y devuelve la corriente máxima admisible junto con todos los resultados
/// intermedios del balance térmico.
///
/// Balance térmico en régimen estacionario (steady-state):
///     qc + qr = qs + I^2 * R(Tavg)      =>      I = sqrt((qc+qr-qs)/R(Tavg))
///
/// El motor se puede usar tanto desde un MonoBehaviour (ej. GeneradorDeLinea)
/// como desde scripts de editor o testing.
/// </summary>
public static class MotorDLR
{
    // ========================================================================
    // CONSTANTES FÍSICAS Y COEFICIENTES DE LA NORMA
    // ========================================================================
    const double PRESION_ATM_HPA = 1013.25;
    const double BETA_TROPOSFERA = 0.0065;
    const double TB_TROPOSFERA = 288.15;
    const double R_GAS = 8.314;
    const double M_AIRE = 0.0289652;

    // Coeficientes del polinomio Qs (cielo claro) - IEEE 738-2023 Tabla 4
    static readonly double[] COEF_QS_CIELO_CLARO = {
        -42.2391,   // A
         63.8044,   // B
         -1.9220,   // C
         3.46921e-2,// D
        -3.61118e-4,// E
         1.94318e-6,// F
        -4.07608e-9 // G (valor corregido de la norma 2023)
    };

    const double K_SOLAR_B = 1.148e-4;
    const double K_SOLAR_C = -1.108e-8;

    // ========================================================================
    // ESTRUCTURA DE DATOS DE ENTRADA
    // ========================================================================
    public struct EntradasDLR
    {
        public string designacion;
        public double diametro_mm;
        public double seccion_mm2;
        public double r_low_ohm_km;
        public double r_high_ohm_km;
        public double t_low_C;
        public double t_high_C;
        public double emisividad;
        public double absortividad;

        public double ta_C;           // temperatura ambiente (°C)
        public double vw_m_s;         // velocidad del viento (m/s)
        public double direccion_viento_deg; // desde el Norte
        public double phi_deg;        // ángulo entre viento y conductor (calculado)

        public double he_m;           // altitud (m)
        public double lat_deg;        // latitud (grados)
        public double zl_deg;         // acimut línea (grados desde Norte)

        public string fecha;          // "YYYY-MM-DD"
        public double hora_solar;     // hora solar (12 = mediodía)

        public double ts_C;           // temperatura máxima del conductor (°C)
    }

    // ========================================================================
    // ESTRUCTURA DE DATOS DE SALIDA
    // ========================================================================
    public struct ResultadoDLR
    {
        public double r_tavg_ohm_km;
        public double r_tavg_ohm_m;
        public double tfilm_C;
        public double viscosidad_kg_ms;
        public double densidad_aire_kg_m3;
        public double conductividad_kf_W_mC;
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
        public string error; // null si no hubo error
    }

    // ========================================================================
    // FUNCIÓN PRINCIPAL
    // ========================================================================
    public static ResultadoDLR Calcular(EntradasDLR e)
    {
        ResultadoDLR r = new ResultadoDLR();

        try
        {
            // --- Validaciones de robustez ---
            if (e.diametro_mm <= 0.0)
            {
                r.error = "El diámetro del conductor debe ser mayor que 0 mm.";
                return r;
            }

            double d0_m = e.diametro_mm / 1000.0;
            double ts_k = e.ts_C + 273.15;
            double ta_k = e.ta_C + 273.15;
            double he_m = e.he_m;

            // --- 1) Presión del aire (ISO 2533) ---
            double p_hpa = PRESION_ATM_HPA * Math.Pow(1.0 - BETA_TROPOSFERA * he_m / TB_TROPOSFERA, 5.2559);

            // --- 2) R(Tavg) ---
            double r_low = e.r_low_ohm_km / 1000.0;
            double r_high = e.r_high_ohm_km / 1000.0;
            double r_tavg_ohm_m = r_low;
            if (e.t_high_C != e.t_low_C)
                r_tavg_ohm_m = ((r_high - r_low) / (e.t_high_C - e.t_low_C)) * (e.ts_C - e.t_low_C) + r_low;
            r.r_tavg_ohm_m = r_tavg_ohm_m;
            r.r_tavg_ohm_km = r_tavg_ohm_m * 1000.0;

            // --- 3) Temperatura de película ---
            double tfilm_C = (e.ts_C + e.ta_C) / 2.0;
            r.tfilm_C = tfilm_C;

            // --- 4) Propiedades del aire ---
            double mu = (1.458e-6 * Math.Pow(tfilm_C + 273.0, 1.5)) / (tfilm_C + 383.4);
            double ro = (1.293 - 1.525e-4 * he_m + 6.379e-9 * he_m * he_m) / (1.0 + 0.00367 * tfilm_C);
            double kf = 2.424e-2 + 7.477e-5 * tfilm_C - 4.407e-9 * tfilm_C * tfilm_C;
            r.viscosidad_kg_ms = mu;
            r.densidad_aire_kg_m3 = ro;
            r.conductividad_kf_W_mC = kf;

            // --- 5) Ángulo viento / conductor (phi) ---
            bool hayViento = e.vw_m_s > 0.0;
            if (hayViento)
            {
                double phi = Math.Abs(e.direccion_viento_deg - e.zl_deg);
                if (phi > 180.0) phi = 360.0 - phi;
                if (phi > 90.0)  phi = 180.0 - phi;
                e.phi_deg = phi;
            }

            // --- 6) Kangle ---
            double kangle = 0.0;
            if (hayViento)
            {
                double phiR = e.phi_deg * Math.PI / 180.0;
                kangle = 1.194 - Math.Cos(phiR) + 0.194 * Math.Cos(2.0 * phiR) + 0.368 * Math.Sin(2.0 * phiR);
            }
            r.kangle = kangle;

            // --- 7) Reynolds ---
            double re = 0.0;
            if (hayViento && mu > 0.0)
                re = d0_m * ro * e.vw_m_s / mu;
            r.reynolds = re;

            // --- 8) Convección natural ---
            double qcn = 0.0;
            if (ts_k > ta_k)
                qcn = 3.645 * Math.Sqrt(ro) * Math.Pow(d0_m, 0.75) * Math.Pow(ts_k - ta_k, 1.25);
            r.qcn_W_m = qcn;

            // --- 9) Convección forzada ---
            double qc1 = 0.0, qc2 = 0.0;
            if (hayViento)
            {
                qc1 = kangle * (1.01 + 1.35 * Math.Pow(re, 0.52)) * kf * (ts_k - ta_k);
                qc2 = kangle * 0.754 * Math.Pow(re, 0.6) * kf * (ts_k - ta_k);
            }
            r.qc1_W_m = qc1;
            r.qc2_W_m = qc2;

            // Convección elegida
            double qc = Math.Max(qcn, Math.Max(qc1, qc2));
            r.qc_W_m = qc;

            // --- 10) Radiación ---
            double qr = 17.8 * d0_m * e.emisividad * (Math.Pow((ts_k / 100.0), 4) - Math.Pow((ta_k / 100.0), 4));
            r.qr_W_m = qr;

            // --- 11) Posición solar ---
            int N = DiaDelAnio(e.fecha);
            double delta = 23.45 * Math.Sin(Math.PI / 180.0 * (360.0 * (284 + N) / 365.0));
            double omega = 15.0 * (e.hora_solar - 12.0);
            r.declinacion_solar_deg = delta;
            r.angulo_horario_deg = omega;

            double latR = e.lat_deg * Math.PI / 180.0;
            double deltaR = delta * Math.PI / 180.0;
            double omegaR = omega * Math.PI / 180.0;

            double hc = Math.Asin(
                Math.Sin(latR) * Math.Sin(deltaR)
                + Math.Cos(latR) * Math.Cos(deltaR) * Math.Cos(omegaR)
            ) * 180.0 / Math.PI;
            r.altitud_solar_hc_deg = hc;

            double denom = Math.Sin(latR) * Math.Cos(omegaR) - Math.Cos(latR) * Math.Tan(deltaR);
            double chi = (Math.Abs(denom) > 1e-12) ? Math.Sin(omegaR) / denom : 0.0;
            double cAz = 0.0;
            if (-180.0 <= omega && omega < 0.0)
                cAz = (chi >= 0.0) ? 0.0 : 180.0;
            else if (0.0 <= omega && omega < 180.0)
                cAz = (chi >= 0.0) ? 180.0 : 360.0;
            double zc = cAz + Math.Atan(chi) * 180.0 / Math.PI;
            r.acimut_solar_zc_deg = zc;

            // --- 12) Qs nivel del mar ---
            double qsMar = PolinomioQs(hc);
            r.qs_nivel_mar_W_m2 = qsMar;

            // --- 13) Corrección por elevación ---
            double kSolar = 1.0 + K_SOLAR_B * he_m + K_SOLAR_C * he_m * he_m;
            double qse = kSolar * qsMar;
            r.k_solar = kSolar;
            r.qse_W_m2 = qse;

            // --- 14) Ganancia solar ---
            double cosTheta = Math.Cos(hc * Math.PI / 180.0) * Math.Cos((zc - e.zl_deg) * Math.PI / 180.0);
            cosTheta = Math.Max(-1.0, Math.Min(1.0, cosTheta));
            double theta = Math.Acos(cosTheta) * 180.0 / Math.PI;
            // Selección conservadora (seno máximo)
            double thetaSel = theta;
            foreach (double cand in new double[] { theta, 180.0 - theta, theta + 360.0, 180.0 - theta + 360.0 })
                if (Math.Abs(cand - 90.0) < Math.Abs(thetaSel - 90.0))
                    thetaSel = cand;
            thetaSel = thetaSel % 360.0;
            r.theta_incidencia_deg = thetaSel;
            double qs = e.absortividad * qse * Math.Sin(thetaSel * Math.PI / 180.0) * d0_m;
            if (qs < 0.0) qs = 0.0;
            r.qs_W_m = qs;

            // --- 15) Corriente máxima ---
            if (r_tavg_ohm_m > 0.0)
            {
                double radicando = (qc + qr - qs) / r_tavg_ohm_m;
                r.radicando_A2 = radicando;
                r.i_max_A = (radicando > 0.0) ? Math.Sqrt(radicando) : 0.0;
            }
            else
            {
                r.i_max_A = 0.0;
            }
        }
        catch (Exception ex)
        {
            r.error = $"ERROR en cálculo DLR: {ex.Message}";
        }

        return r;
    }

    // ========================================================================
    // FUNCIONES AUXILIARES
    // ========================================================================
    static double PolinomioQs(double hc)
    {
        double h = hc;
        double resultado = 0.0;
        for (int i = 0; i < COEF_QS_CIELO_CLARO.Length; i++)
            resultado += COEF_QS_CIELO_CLARO[i] * Math.Pow(h, i);
        return resultado;
    }

    static int DiaDelAnio(string fechaStr)
    {
        if (DateTime.TryParseExact(fechaStr, "yyyy-MM-dd",
            System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.None, out DateTime dt))
            return dt.DayOfYear;
        throw new FormatException($"Formato de fecha no reconocido: {fechaStr}");
    }

    // ========================================================================
    // AYUDA PARA CARGAR DESDE JSON (usado por GeneradorDeLinea)
    // ========================================================================
    /// <summary>
    /// Crea las entradas DLR a partir de un Diccionario (JSON parseado).
    /// Los campos de resistencia vienen en conductor_configurado.json si se
    /// generó con principal.py con el enriquecimiento eléctrico.
    /// </summary>
    public static EntradasDLR DesdeConductorConfigurado(
        double diametro_mm, double seccion_mm2,
        double r_low_ohm_km, double r_high_ohm_km,
        double t_low_C, double t_high_C,
        double emisividad, double absortividad,
        double ta_C, double vw_m_s, double direccion_viento_deg,
        double he_m, double lat_deg, double zl_deg,
        string fecha, double hora_solar, double ts_C
    )
    {
        return new EntradasDLR
        {
            diametro_mm = diametro_mm,
            seccion_mm2 = seccion_mm2,
            r_low_ohm_km = r_low_ohm_km,
            r_high_ohm_km = r_high_ohm_km,
            t_low_C = t_low_C,
            t_high_C = t_high_C,
            emisividad = emisividad,
            absortividad = absortividad,
            ta_C = ta_C,
            vw_m_s = vw_m_s,
            direccion_viento_deg = direccion_viento_deg,
            he_m = he_m,
            lat_deg = lat_deg,
            zl_deg = zl_deg,
            fecha = fecha,
            hora_solar = hora_solar,
            ts_C = ts_C
        };
    }
}
