using UnityEditor;

/// <summary>
/// Mantiene legibles las mallas que usa GeneradorDeLinea para deducir la
/// orientación, los límites y los puntos de conexión de los conductores.
/// También protege los FBX que se incorporen al catálogo en el futuro.
/// </summary>
public class ImportadorModelosLinea : AssetPostprocessor
{
    void OnPreprocessModel()
    {
        string ruta = assetPath.Replace('\\', '/');
        bool esModeloLinea =
            ruta.StartsWith("Assets/Resources/ModelosArmado/")
            || ruta.StartsWith("Assets/Resources/ModelosCruceta/");
        if (!esModeloLinea) return;

        ModelImporter importador = (ModelImporter)assetImporter;
        importador.isReadable = true;
    }
}
