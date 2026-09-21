import os

import bpy


_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARPETA_SALIDA = os.path.abspath(
    os.path.join(
        _RAIZ,
        "unity",
        "Assets",
        "Resources",
        "ModelosCruceta",
    )
)
CATALOGOS = (
    "CATALOGO_ANDEL",
    "CATALOGO_SERIE_C",
    "CATALOGO_13000",
    "CATALOGO_PRESILLA",
)


def objetos_de_coleccion(coleccion):
    encontrados = list(coleccion.objects)
    for hija in coleccion.children:
        encontrados.extend(objetos_de_coleccion(hija))
    return encontrados


os.makedirs(CARPETA_SALIDA, exist_ok=True)
objetos = {}
for nombre_catalogo in CATALOGOS:
    catalogo = bpy.data.collections.get(nombre_catalogo)
    if catalogo is None:
        raise RuntimeError(f"No se encuentra {nombre_catalogo}")
    for objeto in objetos_de_coleccion(catalogo):
        if objeto.type == "MESH":
            objetos[objeto.name] = objeto

for nombre, objeto in sorted(objetos.items()):
    bpy.ops.object.select_all(action="DESELECT")
    objeto.hide_set(False)
    objeto.hide_viewport = False
    objeto.select_set(True)
    bpy.context.view_layer.objects.active = objeto
    nombre_archivo = nombre.replace("/", "_").replace("\\", "_")
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(CARPETA_SALIDA, f"{nombre_archivo}.fbx"),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        axis_forward="-Z",
        axis_up="Y",
        add_leaf_bones=False,
    )

print(f"Crucetas exportadas para Unity: {len(objetos)}")
