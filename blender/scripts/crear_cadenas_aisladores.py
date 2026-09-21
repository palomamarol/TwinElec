# -*- coding: utf-8 -*-
"""
crear_cadenas_aisladores.py
===========================
Genera el croquis 3D GENERICO de una cadena de aisladores y lo exporta a
Unity (FBX). Es la base del catalogo 3D de cadenas del gemelo digital.

La cadena se construye colgando VERTICALMENTE desde el punto de amarre
(origen en la parte superior) hacia abajo (-Z en Blender, que Unity mapea a
-Y = abajo). Estructura simplificada (sin herrajes detallados):

    [1] Grillete/herraje superior (pequeno cilindro + anilla)
    [2] Cuerpo de aisladores: campanas de vidrio apiladas (croquis)
        o varilla polimerica con discos si TIPO = "POL"
    [3] Grapa inferior (cilindro)

Parametros por cadena (longitud total en metros):
    nombre, longitud_m, tipo ("VID"/"POL"), n_aisladores, radio_disco

USO:
    "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe" ^
        --background --python BlenderScripts\\crear_cadenas_aisladores.py

Para generar mas cadenas solo hay que anadir entradas a CADENAS_A_GENERAR.
"""
import os

import bpy

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARPETA_SALIDA = os.path.join(
    _RAIZ, "unity", "Assets", "Resources", "ModelosCadenas")

# Cada entrada genera un FBX: {nombre, longitud_m, tipo, n_aisladores}
CADENAS_A_GENERAR = [
    {
        "nombre": "Cadena_20kV_SUS_SIM_VID",
        "longitud_m": 0.45,
        "tipo": "VID",
        "n_aisladores": 3,
        "radio_disco": 0.05,
    },
]

# Reparto de la longitud total
ALTURA_HERRAJE_SUP = 0.04   # grillete superior
ALTURA_GRAPA_INF = 0.06     # grapa inferior
RADIO_VASTAGO = 0.012       # cuello de cada campana / varilla
RADIO_ANILLA = 0.025        # anilla superior


def limpiar_escena():
    """Borra todos los objetos de la escena por defecto."""
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def crear_material(nombre, color, especular=0.2):
    material = bpy.data.materials.new(name=nombre)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        entrada_color = bsdf.inputs.get("Base Color")
        if entrada_color is not None:
            entrada_color.default_value = color
        entrada_rug = bsdf.inputs.get("Roughness")
        if entrada_rug is not None:
            entrada_rug.default_value = 0.4
        for nombre_in in ("Specular", "Specular IOR Level", "Specular IOR"):
            entrada = bsdf.inputs.get(nombre_in)
            if entrada is not None:
                entrada.default_value = especular
                break
    return material


def _anadir_primitiva(tipo, posicion, **kwargs):
    """Anade una primitiva y devuelve el objeto creado."""
    bpy.ops.object.select_all(action="DESELECT")
    if tipo == "cilindro":
        bpy.ops.mesh.primitive_cylinder_add(
            radius=kwargs.get("radio", 0.01), depth=kwargs.get("altura", 0.1),
            location=posicion, vertices=kwargs.get("vertices", 24))
    elif tipo == "cono":
        bpy.ops.mesh.primitive_cone_add(
            radius1=kwargs.get("radio1", 0.01), radius2=kwargs.get("radio2", 0.05),
            depth=kwargs.get("altura", 0.1), location=posicion,
            vertices=kwargs.get("vertices", 24))
    elif tipo == "toro":
        bpy.ops.mesh.primitive_torus_add(
            major_radius=kwargs.get("radio", 0.025),
            minor_radius=kwargs.get("tubo", 0.006),
            location=posicion,
            major_segments=kwargs.get("segmentos", 32),
            minor_segments=kwargs.get("tubos", 12))
    return bpy.context.active_object


def _asignar_material(objeto, material):
    if objeto.data.materials:
        objeto.data.materials[0] = material
    else:
        objeto.data.materials.append(material)


def crear_cadena(longitud_m, tipo="VID", n_aisladores=3, radio_disco=0.05,
                 unir=True):
    """Construye el croquis 3D de la cadena. Devuelve el objeto raiz.

    El origen queda en el punto de amarre superior; la cadena cuelga hacia
    abajo (-Z en Blender = -Y en Unity). Todo se une en un solo mesh."""
    mat_metal = crear_material("Metal_Herraje", (0.55, 0.55, 0.58, 1.0))
    if tipo == "POL":
        mat_cuerpo = crear_material("Aislador_Polimero", (0.75, 0.78, 0.82, 1.0))
    else:
        mat_cuerpo = crear_material("Aislador_Vidrio", (0.35, 0.55, 0.65, 1.0))

    z = 0.0
    piezas = []

    # ---- Herraje superior (anilla en el tope + grillete) ----
    piezas.append(_anadir_primitiva(
        "toro", (0.0, 0.0, -0.006), radio=RADIO_ANILLA, tubo=0.006))
    _asignar_material(piezas[-1], mat_metal)
    piezas.append(_anadir_primitiva(
        "cilindro", (0.0, 0.0, -(ALTURA_HERRAJE_SUP - 0.012) / 2.0 - 0.012),
        radio=RADIO_VASTAGO, altura=ALTURA_HERRAJE_SUP - 0.012))
    _asignar_material(piezas[-1], mat_metal)
    z -= ALTURA_HERRAJE_SUP

    # ---- Cuerpo de aisladores ----
    altura_cuerpo = longitud_m - ALTURA_HERRAJE_SUP - ALTURA_GRAPA_INF
    if n_aisladores is None:
        # Auto: 1 campana por cada ~0.116 m (misma proporcion que el croquis),
        # de modo que el unico parametro que cambia entre modelos es la longitud.
        n_aisladores = max(1, int(round(altura_cuerpo / 0.116)))
    gaps = (n_aisladores - 1) * 0.008 if n_aisladores > 1 else 0.0
    altura_unidad = (altura_cuerpo - gaps) / max(n_aisladores, 1)
    cuello = altura_unidad * 0.3
    campana = altura_unidad - cuello

    for i in range(n_aisladores):
        if tipo == "POL":
            # Varilla polimerica con discos (salientes) cada unidad
            piezas.append(_anadir_primitiva(
                "cilindro", (0.0, 0.0, z - altura_unidad / 2.0),
                radio=RADIO_VASTAGO, altura=altura_unidad))
            _asignar_material(piezas[-1], mat_cuerpo)
            piezas.append(_anadir_primitiva(
                "cilindro", (0.0, 0.0, z - altura_unidad),
                radio=radio_disco, altura=0.012))
            _asignar_material(piezas[-1], mat_cuerpo)
            z -= altura_unidad
        else:
            # Campana de vidrio: cuello + cuerpo que se abre hacia abajo
            piezas.append(_anadir_primitiva(
                "cilindro", (0.0, 0.0, z - cuello / 2.0),
                radio=RADIO_VASTAGO, altura=cuello))
            _asignar_material(piezas[-1], mat_cuerpo)
            z -= cuello
            piezas.append(_anadir_primitiva(
                "cono", (0.0, 0.0, z - campana / 2.0),
                radio1=RADIO_VASTAGO, radio2=radio_disco, altura=campana))
            _asignar_material(piezas[-1], mat_cuerpo)
            z -= campana
            # pequena separacion entre campanas
            if i < n_aisladores - 1:
                z -= 0.008

    # ---- Grapa inferior ----
    piezas.append(_anadir_primitiva(
        "cilindro", (0.0, 0.0, z - ALTURA_GRAPA_INF / 2.0),
        radio=RADIO_VASTAGO, altura=ALTURA_GRAPA_INF))
    _asignar_material(piezas[-1], mat_metal)
    z -= ALTURA_GRAPA_INF

    # ---- Opcional: mantener las piezas separadas (para editar el diseno) ----
    if not unir:
        nombres = ["Herraje_superior", "Grillete"]
        for i in range(n_aisladores):
            if tipo == "POL":
                nombres += ["Varilla_%d" % (i + 1), "Disco_%d" % (i + 1)]
            else:
                nombres += ["Cuello_%d" % (i + 1), "Campana_%d" % (i + 1)]
        nombres.append("Grapa_inferior")
        for pieza, nombre in zip(piezas, nombres):
            pieza.name = nombre
        return piezas

    # ---- Unir todo en un solo mesh (origen en el punto de amarre) ----
    bpy.ops.object.select_all(action="DESELECT")
    for pieza in piezas:
        pieza.select_set(True)
    bpy.context.view_layer.objects.active = piezas[0]
    bpy.ops.object.join()
    return bpy.context.active_object


def exportar_objeto_como_fbx(objeto, nombre, carpeta=None):
    """Deja el origen en el punto de amarre superior (max z = 0) y exporta el
    objeto como FBX para Unity. Devuelve la ruta del archivo."""
    objeto.name = nombre
    bpy.ops.object.select_all(action="DESELECT")
    objeto.select_set(True)
    bpy.context.view_layer.objects.active = objeto
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    max_z = max(v.co.z for v in objeto.data.vertices)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.transform.translate(value=(0.0, 0.0, -max_z))
    bpy.ops.object.mode_set(mode="OBJECT")
    carpeta = carpeta or CARPETA_SALIDA
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=ruta,
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        axis_forward="-Z",
        axis_up="Y",
        add_leaf_bones=False,
    )
    print("Cadena exportada:", ruta)
    return ruta


def exportar_cadenas():
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    limpiar_escena()
    for configuracion in CADENAS_A_GENERAR:
        objeto = crear_cadena(
            configuracion.get("longitud_m", 0.45),
            tipo=configuracion.get("tipo", "VID"),
            n_aisladores=configuracion.get("n_aisladores", 3),
            radio_disco=configuracion.get("radio_disco", 0.05))
        exportar_objeto_como_fbx(objeto, configuracion["nombre"])
    print("OK: %d cadenas generadas en %s" % (len(CADENAS_A_GENERAR), CARPETA_SALIDA))


if __name__ == "__main__":
    exportar_cadenas()


