using System;
using System.IO;
using UnityEngine;

/// <summary>
/// RutasGemelo — Resolucion centralizada de las rutas del gemelo digital.
/// ============================================================================
/// El programa funciona de dos formas:
///   * EDITOR: los datos de ejemplo viven en data/examples/demo_line, el motor
///             en src/python y los resultados compartidos en unity/Assets.
///   * BUILD (exe): los datos viven en la carpeta "Datos" JUNTO al ejecutable
///              y Unity lee/escribe tambien desde ahi (el motor Python y Unity
///              comparten carpeta). Sin Python instalado: se llama a motor.exe.
///
/// Asi, al exportar el .exe NO hay que recompilar para editar datos: todo lo
/// que cambias en la interfaz se guarda en Datos/ y sobrevive al cierre.
/// </summary>
public static class RutasGemelo
{
    const string ClaveCarpetaActiva = "TwinElec.CarpetaDatosActiva";
    static string carpetaActiva;

    /// <summary>Cambia la linea activa sin recompilar. La seleccion se conserva
    /// para poder mostrarla preseleccionada en el siguiente arranque.</summary>
    public static void ConfigurarRutaDatos(string ruta)
    {
        if (string.IsNullOrWhiteSpace(ruta)) return;
        carpetaActiva = Path.GetFullPath(ruta);
        PlayerPrefs.SetString(ClaveCarpetaActiva, carpetaActiva);
        PlayerPrefs.Save();
    }

    public static string RutaDatosRecordada()
    {
        string ruta = PlayerPrefs.GetString(ClaveCarpetaActiva, "");
        return !string.IsNullOrWhiteSpace(ruta) && Directory.Exists(ruta)
            ? Path.GetFullPath(ruta) : RutaDatosBase();
    }

    /// <summary>Carpeta fija que contiene los scripts/motor del programa.</summary>
    public static string RutaDatosBase()
    {
#if UNITY_EDITOR
        return Path.Combine(RutaRepositorio(), "data", "examples", "demo_line");
#else
        string dirExe = Path.GetDirectoryName(Application.dataPath);
        if (string.IsNullOrEmpty(dirExe)) dirExe = Directory.GetCurrentDirectory();
        return Path.Combine(dirExe, "Datos");
#endif
    }

    public static string RutaRepositorio()
    {
#if UNITY_EDITOR
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
#else
        string dirExe = Path.GetDirectoryName(Application.dataPath);
        return string.IsNullOrEmpty(dirExe) ? Directory.GetCurrentDirectory() : dirExe;
#endif
    }

    public static string RutaCodigoPython()
    {
#if UNITY_EDITOR
        return Path.Combine(RutaRepositorio(), "src", "python");
#else
        return RutaDatosBase();
#endif
    }

    /// <summary>Directorio raiz del gemelo con los datos de trabajo
    /// (Excel, doc UTM, PNOA, catalogos, peticiones y resultados).
    /// Editor -> raiz del proyecto; Build -> <carpeta del exe>/Datos.</summary>
    public static string RutaDatos()
    {
        return string.IsNullOrWhiteSpace(carpetaActiva)
            ? RutaDatosBase() : carpetaActiva;
    }

    /// <summary>Carpeta donde Unity lee/escribe los JSON y CSV del gemelo
    /// (apoyos_configurados.json, fisica_linea.json, coordenadas_linea.csv,
    /// meteorologia_*.json, graficos_utilizacion.json, etc).
    /// Editor -> unity/Assets; Build -> Datos/unity/Assets. Python y Unity
    /// comparten este directorio mediante TWINELEC_ASSETS_DIR.</summary>
    public static string RutaAssetsGemelo()
    {
#if UNITY_EDITOR
        return Application.dataPath;
#else
        return Path.Combine(RutaDatos(), "unity", "Assets");
#endif
    }


    public static string RutaCatalogos()
    {
#if UNITY_EDITOR
        return Path.Combine(RutaRepositorio(), "data", "catalogs");
#else
        return Path.Combine(RutaDatosBase(), "catalogs");
#endif
    }

    public static string RutaScriptsBlender()
    {
#if UNITY_EDITOR
        return Path.Combine(RutaRepositorio(), "blender", "scripts");
#else
        return Path.Combine(RutaDatosBase(), "blender", "scripts");
#endif
    }

    /// <summary>Ruta al grafico de utilizacion PNG de un apoyo.
    /// Editor -> Assets/Resources/graficos_utilizacion; Build -> el mismo
    /// espejo dentro de Datos.</summary>
    public static string RutaGraficos()
    {
        return Path.Combine(RutaAssetsGemelo(), "Resources", "graficos_utilizacion");
    }
}
