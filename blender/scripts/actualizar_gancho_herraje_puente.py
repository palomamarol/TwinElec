import bpy
from mathutils import Vector


NOMBRE = "GANCHO_HERRAJE_PUENTE"
MODULO = 0.510
ESPESOR = 0.035


def bezier(p0, p1, p2, p3, pasos):
    resultado = []
    for indice in range(pasos + 1):
        t = indice / pasos
        u = 1.0 - t
        resultado.append(
            Vector(p0) * u ** 3
            + Vector(p1) * (3.0 * u * u * t)
            + Vector(p2) * (3.0 * u * t * t)
            + Vector(p3) * t ** 3
        )
    return resultado


def barra(inicio, final, coleccion):
    p1, p2 = Vector(inicio), Vector(final)
    direccion = p2 - p1
    bpy.ops.mesh.primitive_cube_add(size=1, location=(p1 + p2) / 2)
    objeto = bpy.context.object
    objeto.dimensions = (ESPESOR, ESPESOR, direccion.length)
    objeto.rotation_mode = "QUATERNION"
    objeto.rotation_quaternion = direccion.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    coleccion.objects.link(objeto)
    for anterior in list(objeto.users_collection):
        if anterior != coleccion:
            anterior.objects.unlink(objeto)
    return objeto


anterior = bpy.data.objects.get(NOMBRE)
if anterior is None:
    raise RuntimeError(f"No se encuentra {NOMBRE} en la biblioteca")

coleccion = anterior.users_collection[0]
materiales = list(anterior.data.materials)
propiedades = {clave: anterior[clave] for clave in anterior.keys()}
matriz = anterior.matrix_world.copy()
bpy.data.objects.remove(anterior, do_unlink=True)

tramo_1 = bezier(
    (0.0, 0.0, 0.0),
    (MODULO * 0.16, 0.0, 0.0),
    (MODULO * 0.55, 0.0, MODULO * 0.22),
    (MODULO * 0.66, 0.0, MODULO * 0.43),
    8,
)
tramo_2 = bezier(
    tramo_1[-1],
    (MODULO * 0.57, 0.0, MODULO * 0.66),
    (MODULO * 0.25, 0.0, MODULO * 1.08),
    (MODULO * 0.05, 0.0, MODULO * 1.13),
    10,
)
puntos = [Vector((-p.y, p.x, p.z)) for p in tramo_1 + tramo_2[1:]]
objetos = [barra(a, b, coleccion) for a, b in zip(puntos, puntos[1:])]
objetos.append(
    barra(puntos[-1], (0.0, -MODULO * 0.43, MODULO * 1.13), coleccion)
)

bpy.ops.object.select_all(action="DESELECT")
for objeto in objetos:
    objeto.select_set(True)
bpy.context.view_layer.objects.active = objetos[0]
bpy.ops.object.join()
nuevo = bpy.context.object
nuevo.name = NOMBRE
nuevo.data.name = f"Malla_{NOMBRE}"
nuevo.matrix_world = matriz
for material in materiales:
    nuevo.data.materials.append(material)
for clave, valor in propiedades.items():
    nuevo[clave] = valor

bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(f"{NOMBRE} actualizado con perfil curvo y guardado.")
