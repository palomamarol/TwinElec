import os

import bpy


MODELOS = (
    "GANCHO_HERRAJE_PUENTE",
    "TG120-AXC",
    "TG250-AXC",
    "TG300-AXC",
    "TG400-AXC",
)


_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
carpeta = os.path.abspath(
    os.path.join(
        _RAIZ,
        "unity",
        "Assets",
        "Resources",
        "ModelosCruceta",
    )
)
os.makedirs(carpeta, exist_ok=True)

for nombre in MODELOS:
    objeto = bpy.data.objects.get(nombre)
    if objeto is None:
        raise RuntimeError(f"No se encuentra el modelo {nombre}")
    bpy.ops.object.select_all(action="DESELECT")
    objeto.hide_set(False)
    objeto.hide_viewport = False
    objeto.select_set(True)
    bpy.context.view_layer.objects.active = objeto
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(carpeta, f"{nombre}.fbx"),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        axis_forward="-Z",
        axis_up="Y",
        add_leaf_bones=False,
    )
    print(f"Herraje exportado: {nombre}")
