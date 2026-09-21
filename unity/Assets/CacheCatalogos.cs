using System;
using System.Collections.Generic;

/// <summary>
/// CacheCatalogos — Guarda en memoria las respuestas del motor Python que son
/// catalogos y listados de SOLO LECTURA (tipos de apoyo, cadenas, conductores,
/// listados de angulos y tensiones...). La parte que tarda ~1-3 s al abrir una
/// ventana es el arranque del motor (motor.exe), no el calculo en si. Con este
/// cache, la segunda vez que se abre la ventana es instantanea.
/// </summary>
public static class CacheCatalogos
{
    static readonly Dictionary<string, string> cache =
        new Dictionary<string, string>();

    // Claves estandar usadas por las ventanas
    public const string ClaveTipoApoyo = "catalogo_tipo_apoyo";
    public const string ClaveConductores = "catalogo_conductores";
    public const string ClaveAngulos = "listado_angulos";
    public const string ClaveTensiones = "listado_tensiones";

    /// <summary>
    /// Devuelve el valor cacheado o, si no existe, lo fabrica con 'fabricar'
    /// y lo guarda. Si 'fabricar' es null, solo devuelve lo cacheado (o null).
    /// </summary>
    public static string Obtener(string clave, Func<string> fabricar)
    {
        if (!string.IsNullOrEmpty(clave) && cache.TryGetValue(clave, out string v))
            return v;
        if (fabricar == null) return null;
        string resultado = fabricar();
        if (!string.IsNullOrEmpty(clave) && !string.IsNullOrWhiteSpace(resultado))
            cache[clave] = resultado;
        return resultado;
    }

    /// <summary>Guarda un valor (lo usan la precarga y las ventanas).</summary>
    public static void Precargar(string clave, string valor)
    {
        if (string.IsNullOrEmpty(clave) || string.IsNullOrWhiteSpace(valor)) return;
        cache[clave] = valor;
    }

    /// <summary>Invalida los LISTADOS dependientes del estado de la linea
    /// (angulos, tensiones). Tras aplicar un cambio, deben volver a leerse.</summary>
    public static void InvalidarDinamicos()
    {
        cache.Remove(ClaveAngulos);
        cache.Remove(ClaveTensiones);
    }

    /// <summary>Invalida TODO el cache (al cargar una linea nueva).</summary>
    public static void Limpiar()
    {
        cache.Clear();
    }
}
