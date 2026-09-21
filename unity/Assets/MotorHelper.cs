using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using System.Text;
using UnityEngine;

/// <summary>
/// MotorHelper — Invocacion centralizada del motor Python del gemelo.
/// ============================================================================
///   * EDITOR: llama a  py <Datos>/<script>.py <argumentos>
///   * BUILD:  llama a  <carpeta del exe>/motor.exe <script> <argumentos>
///             (motor.exe es el motor Python empaquetado con PyInstaller,
///             asi el programa final NO necesita Python instalado).
/// Devuelve la salida estandar (o la de error si no hay salida).
/// </summary>
public static class MotorHelper
{
    static ProcessStartInfo CrearInicio(string script, string argumentos)
    {
        string datos = RutasGemelo.RutaDatos();
        ProcessStartInfo psi = new ProcessStartInfo();
#if UNITY_EDITOR
        psi.FileName = "py";
        psi.Arguments = "\"" + Path.Combine(RutasGemelo.RutaCodigoPython(), script + ".py") + "\" " + argumentos;
#else
        string dirExe = Path.GetDirectoryName(Application.dataPath);
        if (string.IsNullOrEmpty(dirExe)) dirExe = Directory.GetCurrentDirectory();
        psi.FileName = Path.Combine(dirExe, "motor.exe");
        psi.Arguments = "\"" + script + "\" " + argumentos;
#endif
        psi.WorkingDirectory = datos;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        // Python hereda a veces CP-1252 en Windows. El motor imprime símbolos
        // técnicos (✓, ⚠, ❌); sin UTF-8 una advertencia puede convertirse en
        // UnicodeEncodeError y ocultar el resultado real del cálculo.
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        psi.EnvironmentVariables["PYTHONUTF8"] = "1";
        psi.EnvironmentVariables["TWINELEC_DATA_DIR"] = datos;
        psi.EnvironmentVariables["TWINELEC_ASSETS_DIR"] = RutasGemelo.RutaAssetsGemelo();
        psi.EnvironmentVariables["TWINELEC_CATALOGS_DIR"] = RutasGemelo.RutaCatalogos();
        psi.EnvironmentVariables["TWINELEC_BLENDER_SCRIPTS_DIR"] = RutasGemelo.RutaScriptsBlender();
        psi.StandardOutputEncoding = Encoding.UTF8;
        psi.StandardErrorEncoding = Encoding.UTF8;
        return psi;
    }

    /// <summary>Ejecuta un subcomando del motor (p. ej. "mover_apoyo") con sus
    /// argumentos y devuelve la salida capturada (stdout o stderr).</summary>
    public static string EjecutarMotor(string script, string argumentos)
    {
        ProcessStartInfo psi = CrearInicio(script, argumentos);
        try
        {
            Process p = Process.Start(psi);
            string stdout = p.StandardOutput.ReadToEnd();
            p.WaitForExit();
            if (string.IsNullOrWhiteSpace(stdout)) stdout = p.StandardError.ReadToEnd();
            return stdout;
        }
        catch (Exception ex)
        {
            return "{\"ok\": false, \"error\": \"No se pudo invocar al motor: "
                + Json.Esc(ex.Message) + "\"}";
        }
    }

    /// <summary>Version no bloqueante para tareas largas como leer los PNOA.</summary>
    public static IEnumerator EjecutarMotorCoroutine(
        string script, string argumentos, Action<string> alTerminar)
    {
        var stdout = new StringBuilder();
        var stderr = new StringBuilder();
        Process proceso = null;
        try
        {
            proceso = new Process { StartInfo = CrearInicio(script, argumentos) };
            proceso.OutputDataReceived += (_, e) => { if (e.Data != null) stdout.AppendLine(e.Data); };
            proceso.ErrorDataReceived += (_, e) => { if (e.Data != null) stderr.AppendLine(e.Data); };
            proceso.Start();
            proceso.BeginOutputReadLine();
            proceso.BeginErrorReadLine();
        }
        catch (Exception ex)
        {
            alTerminar?.Invoke("No se pudo invocar al motor: " + ex.Message);
            if (proceso != null) proceso.Dispose();
            yield break;
        }

        while (!proceso.HasExited) yield return null;
        // La salida asincrona (BeginOutputReadLine) se drena DESPUES de que el
        // proceso termina. Sin una segunda espera, los comandos rapidos (p. ej.
        // '--catalogo' tarda <1 s) pueden finalizar antes de que se lean sus
        // lineas y devolveriamos stdout vacio -> error de parseo en el caller.
        proceso.WaitForExit();
        proceso.WaitForExit(); // drena la salida asincrona por completo
        string salida = stdout.Length > 0 ? stdout.ToString() : stderr.ToString();
        proceso.Dispose();
        alTerminar?.Invoke(salida);
    }
}
