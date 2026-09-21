using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// UiBoton — Aplica a cualquier boton del programa un ColorBlock con realce:
/// al pasar el raton por encima se aclara y al pulsar se oscurece, de modo que
/// el usuario SIEMPRE nota que lo ha pulsado (sensacion de profundidad).
/// </summary>
public static class UiBoton
{
    /// <summary>Aplica el estilo usando como color normal el color actual de la
    /// imagen del boton (targetGraphic). El boton debe tener ya el targetGraphic
    /// asignado.</summary>
    public static void AplicarEstilo(Button boton)
    {
        if (boton == null) return;
        Color baseC = new Color(0.2f, 0.35f, 0.55f, 1f);
        Image imagen = boton.targetGraphic as Image;
        if (imagen != null)
        {
            baseC = imagen.color;
            // El tint del ColorBlock multiplica: con la imagen blanca el bloque
            // controla los colores por completo (normal/hover/press).
            imagen.color = Color.white;
        }
        ColorBlock cb = ColorBlock.defaultColorBlock;
        cb.normalColor = baseC;
        cb.highlightedColor = Color.Lerp(baseC, Color.white, 0.42f);
        cb.pressedColor = Color.Lerp(baseC, Color.black, 0.35f);
        cb.selectedColor = Color.Lerp(baseC, Color.white, 0.42f);
        cb.disabledColor = new Color(0.4f, 0.4f, 0.4f, 0.6f);
        cb.colorMultiplier = 1f;
        cb.fadeDuration = 0.08f;
        boton.colors = cb;
    }
}
