import os

import bpy


NOMBRES_ARMADOS = (
    "Cabeza_C",
    "Cabeza_G",
    "Cabeza_M50",
    "Cabeza_M60",
    "Cabeza_PRESILLA_250",
    "Cabeza_PRESILLA_400_1250",
    "Cabeza_PRESILLA_400_1250_TRENZADOS",
    "Modulo_C_A",
    "Modulo_C_B",
    "Modulo_G_A",
    "Modulo_G_B",
    "Modulo_M50_A",
    "Modulo_M50_B",
    "Modulo_M60_A",
    "Modulo_M60_B",
    "Modulo_PRESILLA_250_A",
    "Modulo_PRESILLA_250_B",
    "Modulo_PRESILLA_400_1250_A",
    "Modulo_PRESILLA_400_1250_B",
    "Modulo_PRESILLA_400_1250_TRENZADOS_A",
    "Modulo_PRESILLA_400_1250_TRENZADOS_B",
)


def exportar_armados(carpeta_salida):
    os.makedirs(carpeta_salida, exist_ok=True)

    for nombre in NOMBRES_ARMADOS:
        objeto = bpy.data.objects.get(nombre)
        if objeto is None:
            print(f"Armado no encontrado: {nombre}")
            continue

        bpy.ops.object.select_all(action="DESELECT")
        objeto.hide_set(False)
        objeto.hide_viewport = False
        objeto.select_set(True)
        bpy.context.view_layer.objects.active = objeto

        bpy.ops.export_scene.fbx(
            filepath=os.path.join(carpeta_salida, f"{nombre}.fbx"),
            use_selection=True,
            object_types={"MESH"},
            apply_unit_scale=True,
            axis_forward="-Z",
            axis_up="Y",
            add_leaf_bones=False,
        )
        print(f"Armado exportado: {nombre}")


if __name__ == "__main__":
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    exportar_armados(
        os.path.join(
                raiz,
                "unity",
                "Assets",
                "Resources",
                "ModelosArmado",
        )
    )
