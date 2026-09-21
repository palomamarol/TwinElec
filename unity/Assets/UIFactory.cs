using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

/// <summary>
/// UIFactory — utilidades de UI compartidas para las ventanas del gemelo.
/// CrearDropdown genera un desplegable (Dropdown) completo por codigo:
/// plantilla, viewport con recorte, content, item con checkmark (sprite
/// generado en runtime, el recurso interno Checkmark.psd ya no existe en
/// Unity 6000.x) y etiqueta.
/// IMPORTANTE: el Content NO lleva VerticalLayoutGroup ni ContentSizeFitter.
/// En UGUI 3.x (Unity 6000) el Dropdown posiciona los items MANUALMENTE y
/// ajusta su propia altura; un layout group sobrescribiria esas posiciones y
/// la lista se veria vacia (solo el recuadro oscuro de la plantilla).
/// </summary>
public static class UIFactory
{
    public static Dropdown CrearDropdown(GameObject padre, string nombre, Vector2 ancla,
                                         Vector2 pos, Vector2 tam)
    {
        const float alturaOpcion = 30f;
        const float margenVerticalLista = 5f;

        var go = new GameObject(nombre);
        go.transform.SetParent(padre.transform, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = ancla; rt.anchorMax = ancla; rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = pos;
        rt.sizeDelta = tam;

        var fondo = go.AddComponent<Image>();
        fondo.color = new Color(0.16f, 0.25f, 0.38f, 1f);

        var dd = go.AddComponent<Dropdown>();
        dd.targetGraphic = fondo;

        // Texto del valor seleccionado (caption), con margen izquierdo.
        // (Mismos valores que la plantilla por defecto de Unity.)
        var cap = new GameObject("Label");
        cap.transform.SetParent(go.transform, false);
        var crt = cap.AddComponent<RectTransform>();
        crt.anchorMin = Vector2.zero; crt.anchorMax = Vector2.one;
        crt.offsetMin = new Vector2(10, 6); crt.offsetMax = new Vector2(-25, -7);
        var ctxt = cap.AddComponent<Text>();
        ctxt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        ctxt.fontSize = 14;
        ctxt.alignment = TextAnchor.MiddleLeft;
        ctxt.color = Color.white;
        ctxt.horizontalOverflow = HorizontalWrapMode.Overflow;
        ctxt.verticalOverflow = VerticalWrapMode.Overflow;
        ctxt.raycastTarget = false;

        // Flecha del desplegable
        var flecha = new GameObject("Arrow");
        flecha.transform.SetParent(go.transform, false);
        var frt = flecha.AddComponent<RectTransform>();
        frt.anchorMin = new Vector2(1f, 0.5f); frt.anchorMax = new Vector2(1f, 0.5f);
        frt.pivot = new Vector2(0.5f, 0.5f);
        frt.sizeDelta = new Vector2(16, 16);
        frt.anchoredPosition = new Vector2(-14, 0);
        var ftxt = flecha.AddComponent<Text>();
        ftxt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        ftxt.fontSize = 14;
        ftxt.alignment = TextAnchor.MiddleCenter;
        ftxt.color = new Color(0.8f, 0.85f, 0.95f);
        ftxt.text = "\u25BE";
        ftxt.raycastTarget = false;

        // Plantilla de la lista desplegada (inactiva hasta abrirla)
        var tpl = new GameObject("Template");
        tpl.transform.SetParent(go.transform, false);
        var trt = tpl.AddComponent<RectTransform>();
        trt.anchorMin = new Vector2(0f, 0f); trt.anchorMax = new Vector2(1f, 0f);
        trt.pivot = new Vector2(0.5f, 1f);
        trt.anchoredPosition = new Vector2(0, -4);
        trt.sizeDelta = new Vector2(0, 170);
        tpl.AddComponent<Image>().color = new Color(0.12f, 0.18f, 0.28f, 1f);
        tpl.AddComponent<Canvas>().overrideSorting = true;
        tpl.GetComponent<Canvas>().sortingOrder = 3000;
        tpl.AddComponent<GraphicRaycaster>();
        var tsr = tpl.AddComponent<ScrollRect>();
        tsr.horizontal = false;
        tsr.vertical = true;
        tsr.scrollSensitivity = 20f;
        tsr.movementType = ScrollRect.MovementType.Clamped;

        // Viewport (recorta la lista)
        var vp = new GameObject("Viewport");
        vp.transform.SetParent(tpl.transform, false);
        var vprt = vp.AddComponent<RectTransform>();
        vprt.anchorMin = Vector2.zero; vprt.anchorMax = Vector2.one;
        vprt.offsetMin = Vector2.zero; vprt.offsetMax = Vector2.zero;
        vp.AddComponent<Image>().color = new Color(0.12f, 0.18f, 0.28f, 0.95f);
        vp.AddComponent<RectMask2D>();
        tsr.viewport = vprt;

        // Content (aquí el Dropdown de UGUI 3.x posiciona los items MANUALMENTE
        // y ajusta su propia altura; NO debe llevar VerticalLayoutGroup ni
        // ContentSizeFitter, porque sobrescribirian esas posiciones y dejarian
        // la lista vacia (solo se veria el recuadro oscuro de la plantilla).
        var content = new GameObject("Content");
        content.transform.SetParent(vp.transform, false);
        var crt2 = content.AddComponent<RectTransform>();
        crt2.anchorMin = new Vector2(0f, 1f); crt2.anchorMax = new Vector2(1f, 1f);
        crt2.pivot = new Vector2(0.5f, 1f);
        crt2.anchoredPosition = Vector2.zero;
        // Un RectTransform creado por codigo empieza con sizeDelta = (100, 100).
        // Como Content estira horizontalmente, esos 100 px se sumarian al ancho
        // del Viewport (50 px a cada lado). RectMask2D recortaria entonces los
        // primeros caracteres de todas las opciones. El ancho extra debe ser
        // cero. La altura inicial contiene una fila y margen real arriba/abajo:
        // Dropdown conserva ese margen al calcular la lista completa, de modo
        // que RectMask2D nunca recorta la primera ni la ultima opcion.
        crt2.sizeDelta = new Vector2(
            0f, alturaOpcion + 2f * margenVerticalLista);
        tsr.content = crt2;

        // Item (primera opcion; Unity lo clona para cada opcion).
        // IMPORTANTE: anclado al CENTRO vertical con pivot central, igual que la
        // plantilla por defecto de Unity; el Dropdown de UGUI 3.x calcula y
        // posiciona cada item usando pivot.y = 0.5.
        var item = new GameObject("Item");
        item.transform.SetParent(content.transform, false);
        var irt = item.AddComponent<RectTransform>();
        irt.anchorMin = new Vector2(0f, 0.5f); irt.anchorMax = new Vector2(1f, 0.5f);
        irt.pivot = new Vector2(0.5f, 0.5f);
        irt.sizeDelta = new Vector2(0f, alturaOpcion);
        var iimg = item.AddComponent<Image>();
        iimg.color = new Color(0.18f, 0.28f, 0.42f, 1f);
        var tg = item.AddComponent<Toggle>();
        tg.targetGraphic = iimg;
        tg.isOn = true;

        // Marca de seleccion (checkmark generado en runtime)
        var check = new GameObject("Item Checkmark");
        check.transform.SetParent(item.transform, false);
        var crtCheck = check.AddComponent<RectTransform>();
        crtCheck.anchorMin = new Vector2(0f, 0.5f); crtCheck.anchorMax = new Vector2(0f, 0.5f);
        crtCheck.pivot = new Vector2(0.5f, 0.5f);
        crtCheck.sizeDelta = new Vector2(16, 16);
        crtCheck.anchoredPosition = new Vector2(10, 0);
        var ck = check.AddComponent<Image>();
        ck.sprite = CrearCheckmarkSprite();
        ck.color = Color.white;
        ck.raycastTarget = false;
        ck.enabled = true;
        // Texto de cada opcion (margen izquierdo de 20 px como la plantilla
        // por defecto; nada queda cortado por el borde izquierdo)
        var itxt = new GameObject("Item Label");
        itxt.transform.SetParent(item.transform, false);
        var irt2 = itxt.AddComponent<RectTransform>();
        irt2.anchorMin = Vector2.zero; irt2.anchorMax = Vector2.one;
        irt2.offsetMin = new Vector2(20, 1); irt2.offsetMax = new Vector2(-10, -2);
        var it = itxt.AddComponent<Text>();
        it.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        it.fontSize = 14;
        it.alignment = TextAnchor.MiddleLeft;
        it.color = Color.white;
        it.horizontalOverflow = HorizontalWrapMode.Overflow;
        it.verticalOverflow = VerticalWrapMode.Overflow;
        it.raycastTarget = false;

        tpl.SetActive(false);

        dd.template = trt;
        dd.captionText = ctxt;
        dd.itemText = it;
        dd.itemImage = ck;
        return dd;
    }

    public static Sprite CrearCheckmarkSprite()
    {
        int t = 24;
        var tex = new Texture2D(t, t, TextureFormat.RGBA32, false);
        var pix = new Color32[t * t];
        // Polilinea de la "✓" espejada (mirror horizontal): la parte corta queda
        // a la izquierda y la larga a la derecha -> (5,11) -> (9,7) -> (19,18)
        Vector2 a = new Vector2(5f, 11f), b = new Vector2(9f, 7f), c = new Vector2(19f, 18f);
        for (int y = 0; y < t; y++)
        {
            for (int x = 0; x < t; x++)
            {
                Vector2 p = new Vector2(x + 0.5f, y + 0.5f);
                float d = Mathf.Min(DistanciaPuntoSegmento(p, a, b),
                                    DistanciaPuntoSegmento(p, b, c));
                float alpha = Mathf.Clamp01(1.2f - d);   // grosor ~2 px con borde suave
                if (alpha > 0f)
                    pix[x + y * t] = new Color32(255, 255, 255, (byte)(alpha * 255f));
            }
        }
        tex.SetPixels32(pix);
        tex.Apply();
        tex.hideFlags = HideFlags.HideAndDontSave;
        return Sprite.Create(tex, new Rect(0, 0, t, t), new Vector2(0.5f, 0.5f), 100f);
    }

    static float DistanciaPuntoSegmento(Vector2 p, Vector2 a, Vector2 b)
    {
        Vector2 ab = b - a;
        float largo2 = ab.sqrMagnitude;
        float tProy = largo2 < 1e-6f ? 0f : Mathf.Clamp01(Vector2.Dot(p - a, ab) / largo2);
        Vector2 proy = a + ab * tProy;
        return (p - proy).magnitude;
    }
}
