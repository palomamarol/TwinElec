import bpy
from mathutils import Vector

# --------------------------------------------------
# PARÁMETROS GENERALES
# --------------------------------------------------

ESPESOR = 0.035     # Barras simplificadas de 35 mm

ANCHO_M50_M60_C = 0.510  # 510 mm
ANCHO_G = 0.908           # 908 mm
ANCHO_PRESILLA_250 = 0.200
ANCHO_PRESILLA_400_1250 = 0.320

ALTURA_M50_M60 = 4.0     # 4 metros
ALTURA_C = 4.2           # 4,2 metros
ALTURA_G = 5.6           # 5,6 metros

MARGEN_SUPERIOR_PRESILLA = 0.030

COLECCIONES_ARMADOS = {
    "M60": "01_M60",
    "M50": "02_M50",
    "C": "03_C",
    "G": "04_G",
    "PRESILLA_250": "05_PRESILLA_250",
    "PRESILLA_400_1250": "06_PRESILLA_400_1250",
    "PRESILLA_400_1250_TRENZADOS": "07_PRESILLA_400_1250_TRENZADOS",
}

COLECCIONES_MODULOS = {
    "C": "01_C",
    "G": "02_G",
    "M50": "03_M50",
    "M60": "04_M60",
    "PRESILLA_250": "05_PRESILLA_250",
    "PRESILLA_400_1250": "06_PRESILLA_400_1250",
    "PRESILLA_400_1250_TRENZADOS": "07_PRESILLA_400_1250_TRENZADOS",
}

ALTURAS_HUECOS_PRESILLA_250 = [
    0.430,
    0.400, 0.400, 0.400, 0.400,
    0.400, 0.400, 0.400, 0.400,
    0.340,
]

ALTURAS_HUECOS_PRESILLA_400_1250 = [
    0.600,
    0.250, 0.250, 0.250, 0.250,
    0.500, 0.500, 0.500, 0.500,
    0.470,
]

ALTURAS_HUECOS_PRESILLA_400_1250_TRENZADOS = [
    0.600, 0.600, 0.600, 0.600, 0.600, 0.600,
    0.470,
]

NIVELES_M60_DESDE_ARRIBA = [
    0.0, 0.60, 1.20, 1.80, 2.40, 3.00, 3.60
]

NIVELES_M50_DESDE_ARRIBA = [
    0.0, 0.75, 1.125, 1.50, 2.00, 2.50, 3.00, 3.60
]

NIVELES_C_DESDE_ARRIBA = [
    0.0, 0.60, 1.20, 1.80, 2.40, 3.00, 3.60, 4.20
]

NIVELES_G_DESDE_ARRIBA = [
    0.0, 0.70, 1.40, 2.10, 2.80, 3.50, 4.20, 4.90, 5.60
]


def niveles_desde_alturas_huecos(alturas_huecos, margen_superior=0.0):
    niveles = [margen_superior]
    acumulado = margen_superior
    for altura_hueco in alturas_huecos:
        acumulado += altura_hueco
        niveles.append(acumulado)
    return niveles


# --------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------

def eliminar_coleccion(nombre):
    coleccion = bpy.data.collections.get(nombre)

    if coleccion:
        for objeto in list(coleccion.objects):
            bpy.data.objects.remove(objeto, do_unlink=True)

        bpy.data.collections.remove(coleccion)


def obtener_o_crear_coleccion(nombre, padre):
    coleccion = bpy.data.collections.get(nombre)
    if coleccion is None:
        coleccion = bpy.data.collections.new(nombre)
    if padre.children.get(nombre) is None:
        padre.children.link(coleccion)
    return coleccion


def desvincular_de_otros_padres(coleccion, padre_correcto):
    posibles_padres = [bpy.context.scene.collection, *bpy.data.collections]
    for posible_padre in posibles_padres:
        if posible_padre == padre_correcto:
            continue
        if posible_padre.children.get(coleccion.name) is not None:
            posible_padre.children.unlink(coleccion)


def organizar_catalogos_crucetas():
    raiz = obtener_o_crear_coleccion(
        "01_CATALOGOS_CRUCETAS",
        bpy.context.scene.collection,
    )
    for nombre in (
        "CATALOGO_ANDEL",
        "CATALOGO_SERIE_C",
        "CATALOGO_13000",
        "CATALOGO_PRESILLA",
    ):
        catalogo = bpy.data.collections.get(nombre)
        if catalogo is None:
            continue
        if raiz.children.get(nombre) is None:
            raiz.children.link(catalogo)
        desvincular_de_otros_padres(catalogo, raiz)


def crear_material():
    nombre = "Acero_Galvanizado"
    material = bpy.data.materials.get(nombre)

    if material is None:
        material = bpy.data.materials.new(nombre)
        material.use_nodes = True

        principled = material.node_tree.nodes.get("Principled BSDF")
        principled.inputs["Base Color"].default_value = (
            0.32, 0.35, 0.38, 1.0
        )
        principled.inputs["Metallic"].default_value = 0.75
        principled.inputs["Roughness"].default_value = 0.38

    return material


def crear_barra(coleccion, punto_1, punto_2):
    inicio = Vector(punto_1)
    final = Vector(punto_2)

    direccion = final - inicio
    longitud = direccion.length
    centro = (inicio + final) / 2

    bpy.ops.mesh.primitive_cube_add(size=1, location=centro)
    barra = bpy.context.object

    barra.dimensions = (ESPESOR, ESPESOR, longitud)
    barra.rotation_mode = "QUATERNION"
    barra.rotation_quaternion = direccion.to_track_quat("Z", "Y")

    bpy.ops.object.transform_apply(
        location=False,
        rotation=True,
        scale=True
    )

    # Trasladar el objeto a su colección
    coleccion.objects.link(barra)

    for coleccion_anterior in list(barra.users_collection):
        if coleccion_anterior != coleccion:
            coleccion_anterior.objects.unlink(barra)

    return barra


def crear_diagonales(
    coleccion,
    objetos,
    mitad,
    z_superior,
    z_inferior,
    invertir
):
    if not invertir:
        diagonales = [
            # Cara frontal
            ((-mitad, -mitad, z_superior),
             ( mitad, -mitad, z_inferior)),

            # Cara posterior
            (( mitad,  mitad, z_superior),
             (-mitad,  mitad, z_inferior)),

            # Cara izquierda
            ((-mitad,  mitad, z_superior),
             (-mitad, -mitad, z_inferior)),

            # Cara derecha
            (( mitad, -mitad, z_superior),
             ( mitad,  mitad, z_inferior)),
        ]

    else:
        diagonales = [
            # Cara frontal
            (( mitad, -mitad, z_superior),
             (-mitad, -mitad, z_inferior)),

            # Cara posterior
            ((-mitad,  mitad, z_superior),
             ( mitad,  mitad, z_inferior)),

            # Cara izquierda
            ((-mitad, -mitad, z_superior),
             (-mitad,  mitad, z_inferior)),

            # Cara derecha
            (( mitad,  mitad, z_superior),
             ( mitad, -mitad, z_inferior)),
        ]

    for inicio, final in diagonales:
        objetos.append(
            crear_barra(coleccion, inicio, final)
        )


def unir_objetos(objetos, nombre, material):
    bpy.ops.object.select_all(action="DESELECT")

    for objeto in objetos:
        objeto.select_set(True)

    bpy.context.view_layer.objects.active = objetos[0]
    bpy.ops.object.join()

    resultado = bpy.context.object
    resultado.name = nombre

    # Un único material para toda la cabeza
    resultado.data.materials.clear()
    resultado.data.materials.append(material)

    for poligono in resultado.data.polygons:
        poligono.material_index = 0

    # El origen queda en la base de la cabeza
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

    return resultado


# --------------------------------------------------
# CREACIÓN DE CADA CABEZA
# --------------------------------------------------

def crear_cabeza(
    tipo,
    distancias_desde_arriba,
    ancho,
    altura,
    alturas_huecos=None,
    margen_superior=0.0,
):
    eliminar_coleccion(f"Coleccion_{tipo}")
    nombre_coleccion = COLECCIONES_ARMADOS[tipo]
    eliminar_coleccion(nombre_coleccion)

    raiz_armados = obtener_o_crear_coleccion(
        "02_CATALOGO_ARMADOS",
        bpy.context.scene.collection,
    )
    coleccion = bpy.data.collections.new(nombre_coleccion)
    raiz_armados.children.link(coleccion)

    material = crear_material()
    objetos = []

    # Así el ancho exterior total queda aproximadamente en 510 mm
    mitad = (ancho - ESPESOR) / 2

    # Convertimos distancias desde arriba en coordenadas Z desde la base
    niveles_z = [
        altura - distancia
        for distancia in distancias_desde_arriba
    ]

    # Cuatro montantes verticales
    esquinas = [
        (-mitad, -mitad),
        ( mitad, -mitad),
        ( mitad,  mitad),
        (-mitad,  mitad),
    ]

    for x, y in esquinas:
        objetos.append(
            crear_barra(
                coleccion,
                (x, y, 0),
                (x, y, altura)
            )
        )

    # Marcos horizontales
    for z in niveles_z:
        lados = [
            ((-mitad, -mitad, z), ( mitad, -mitad, z)),
            (( mitad, -mitad, z), ( mitad,  mitad, z)),
            (( mitad,  mitad, z), (-mitad,  mitad, z)),
            ((-mitad,  mitad, z), (-mitad, -mitad, z)),
        ]

        for inicio, final in lados:
            objetos.append(
                crear_barra(coleccion, inicio, final)
            )

    # Diagonales alternadas de cada módulo
    for indice in range(len(niveles_z) - 1):
        crear_diagonales(
            coleccion,
            objetos,
            mitad,
            niveles_z[indice],
            niveles_z[indice + 1],
            invertir=(indice % 2 == 1)
        )

    # Si el último marco no coincide con la base, cerramos el tramo restante.
    if niveles_z[-1] > 0:
        crear_diagonales(
            coleccion,
            objetos,
            mitad,
            niveles_z[-1],
            0,
            invertir=(len(niveles_z) % 2 == 1)
        )

    cabeza = unir_objetos(
        objetos,
        f"Cabeza_{tipo}",
        material
    )

    # Metadatos útiles para la futura biblioteca
    cabeza["tipo_cabeza"] = tipo
    cabeza["altura_m"] = altura
    cabeza["ancho_m"] = ancho
    if alturas_huecos is not None:
        cabeza["alturas_huecos_m"] = ",".join(
            f"{valor:.3f}" for valor in alturas_huecos
        )
        cabeza["margen_superior_m"] = margen_superior

    return cabeza


def crear_modulo_cuerpo(tipo, ancho, altura, invertir):
    """Celda repetible que prolonga hacia abajo una cabeza de armado."""
    nombre = f"Modulo_{tipo}_{'B' if invertir else 'A'}"
    eliminar_coleccion(f"Coleccion_{nombre}")
    raiz_modulos = obtener_o_crear_coleccion(
        "03_CATALOGO_MODULOS",
        bpy.context.scene.collection,
    )
    grupo_familia = obtener_o_crear_coleccion(
        COLECCIONES_MODULOS[tipo],
        raiz_modulos,
    )
    nombre_coleccion = (
        f"{'02' if invertir else '01'}_MODULO_{tipo}_{'B' if invertir else 'A'}"
    )
    eliminar_coleccion(nombre_coleccion)

    coleccion = bpy.data.collections.new(nombre_coleccion)
    grupo_familia.children.link(coleccion)
    material = crear_material()
    objetos = []
    mitad = (ancho - ESPESOR) / 2

    for x, y in (
        (-mitad, -mitad),
        (mitad, -mitad),
        (mitad, mitad),
        (-mitad, mitad),
    ):
        objetos.append(crear_barra(coleccion, (x, y, 0.0), (x, y, altura)))

    for z in (0.0, altura):
        for inicio, final in (
            ((-mitad, -mitad, z), (mitad, -mitad, z)),
            ((mitad, -mitad, z), (mitad, mitad, z)),
            ((mitad, mitad, z), (-mitad, mitad, z)),
            ((-mitad, mitad, z), (-mitad, -mitad, z)),
        ):
            objetos.append(crear_barra(coleccion, inicio, final))

    crear_diagonales(
        coleccion,
        objetos,
        mitad,
        altura,
        0.0,
        invertir,
    )
    modulo = unir_objetos(objetos, nombre, material)
    modulo["tipo"] = "modulo_cuerpo_armado"
    modulo["familia_armado"] = tipo
    modulo["altura_m"] = altura
    modulo["ancho_m"] = ancho
    modulo["patron_diagonal"] = "B" if invertir else "A"
    return modulo


# --------------------------------------------------
# EJECUCIÓN
# --------------------------------------------------

bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.length_unit = "METERS"
bpy.context.scene.unit_settings.scale_length = 1.0

organizar_catalogos_crucetas()

cabeza_m60 = crear_cabeza(
    "M60",
    NIVELES_M60_DESDE_ARRIBA,
    ANCHO_M50_M60_C,
    ALTURA_M50_M60
)

cabeza_m50 = crear_cabeza(
    "M50",
    NIVELES_M50_DESDE_ARRIBA,
    ANCHO_M50_M60_C,
    ALTURA_M50_M60
)

cabeza_c = crear_cabeza(
    "C",
    NIVELES_C_DESDE_ARRIBA,
    ANCHO_M50_M60_C,
    ALTURA_C
)

cabeza_g = crear_cabeza(
    "G",
    NIVELES_G_DESDE_ARRIBA,
    ANCHO_G,
    ALTURA_G
)

cabeza_presilla_250 = crear_cabeza(
    "PRESILLA_250",
    niveles_desde_alturas_huecos(
        ALTURAS_HUECOS_PRESILLA_250,
        MARGEN_SUPERIOR_PRESILLA,
    ),
    ANCHO_PRESILLA_250,
    MARGEN_SUPERIOR_PRESILLA + sum(ALTURAS_HUECOS_PRESILLA_250),
    ALTURAS_HUECOS_PRESILLA_250,
    MARGEN_SUPERIOR_PRESILLA,
)

cabeza_presilla_400_1250 = crear_cabeza(
    "PRESILLA_400_1250",
    niveles_desde_alturas_huecos(
        ALTURAS_HUECOS_PRESILLA_400_1250,
        MARGEN_SUPERIOR_PRESILLA,
    ),
    ANCHO_PRESILLA_400_1250,
    MARGEN_SUPERIOR_PRESILLA + sum(ALTURAS_HUECOS_PRESILLA_400_1250),
    ALTURAS_HUECOS_PRESILLA_400_1250,
    MARGEN_SUPERIOR_PRESILLA,
)

cabeza_presilla_400_1250_trenzados = crear_cabeza(
    "PRESILLA_400_1250_TRENZADOS",
    niveles_desde_alturas_huecos(
        ALTURAS_HUECOS_PRESILLA_400_1250_TRENZADOS,
        MARGEN_SUPERIOR_PRESILLA,
    ),
    ANCHO_PRESILLA_400_1250,
    MARGEN_SUPERIOR_PRESILLA
    + sum(ALTURAS_HUECOS_PRESILLA_400_1250_TRENZADOS),
    ALTURAS_HUECOS_PRESILLA_400_1250_TRENZADOS,
    MARGEN_SUPERIOR_PRESILLA,
)

MODULOS_CUERPO = (
    ("C", ANCHO_M50_M60_C, 0.600),
    ("G", ANCHO_G, 0.700),
    ("M50", ANCHO_M50_M60_C, 0.400),
    ("M60", ANCHO_M50_M60_C, 0.400),
    ("PRESILLA_250", ANCHO_PRESILLA_250, 0.340),
    ("PRESILLA_400_1250", ANCHO_PRESILLA_400_1250, 0.470),
    (
        "PRESILLA_400_1250_TRENZADOS",
        ANCHO_PRESILLA_400_1250,
        0.470,
    ),
)

modulos_cuerpo = []
for tipo, ancho, altura_modulo in MODULOS_CUERPO:
    modulos_cuerpo.append(
        crear_modulo_cuerpo(tipo, ancho, altura_modulo, invertir=False)
    )
    modulos_cuerpo.append(
        crear_modulo_cuerpo(tipo, ancho, altura_modulo, invertir=True)
    )

# Los cuatro armados ocupan el mismo lugar para conservar el origen en la base.
# Ocultamos inicialmente todos salvo M60 para evitar que se superpongan.
cabeza_m50.hide_set(True)
cabeza_c.hide_set(True)
cabeza_g.hide_set(True)
cabeza_presilla_250.hide_set(True)
cabeza_presilla_400_1250.hide_set(True)
cabeza_presilla_400_1250_trenzados.hide_set(True)
for modulo in modulos_cuerpo:
    modulo.hide_set(True)

bpy.ops.object.select_all(action="DESELECT")
cabeza_m60.hide_set(False)
cabeza_m60.select_set(True)
bpy.context.view_layer.objects.active = cabeza_m60

print("Armados C, G, M50, M60 y cabezas de presilla creados correctamente.")
