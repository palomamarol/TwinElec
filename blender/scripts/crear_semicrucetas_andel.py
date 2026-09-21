import bpy
from mathutils import Vector


# Catálogo paramétrico simplificado de semicrucetas y crucetas ANDEL.
# Todas las dimensiones se expresan en metros.

ESPESOR_NORMAL = 0.035
ESPESOR_SERIE_90 = 0.045
FONDO_CELOSIA = 0.30
ANCHO_ANCLAJE = 0.45
ANCHO_CARA_ACOPLE = 0.510
ALTURAS_ACOPLE = (
    ("H375", 0.375, "M50"),
    ("H500", 0.500, "M50"),
    ("H600", 0.600, "M60"),
    ("H750", 0.750, "M50"),
)

SEMICRUCETAS_ASC = {
    "ASC-12": 1.250,
    "ASC-15": 1.500,
    "ASC-17": 1.750,
    "ASC-20": 2.000,
}

CRUCETAS_ARCX = {
    "ARCX-12": (1.250, 2.500),
    "ARCX-15": (1.500, 3.000),
    "ARCX-17": (1.750, 3.500),
    "ARCX-20": (2.000, 4.000),
}

CRUCETAS_AMC = {
    "AMCX-12": (1.250, 2.500),
    "AMCX-15": (1.500, 3.000),
    "AMCX-17": (1.750, 3.500),
    "AMCX-20": (2.000, 4.000),
}

GANCHO_HERRAJE_PUENTE = "GANCHO_HERRAJE_PUENTE"

MONTAJES_TRIANGULO_TG = {
    "TG120-AXC": ("TG170", 1.700, 1.250, 1.200),
    "TG250-AXC": ("TG250", 2.500, 1.250, 2.400),
    "TG300-AXC": ("TG300", 3.000, 1.500, 3.000),
    "TG400-AXC": ("TG400", 4.000, 2.000, 3.600),
}

BOVEDAS_CAPA = {
    "BH150-ANC": (1.200, 3.000),
    "BH200-ANC": (1.200, 4.000),
    "BH250-ANC": (1.300, 5.000),
    "BH300-ANC": (1.300, 6.000),
}

BOVEDAS_PICO = {
    "BF150-ANC": (1.200, 2.900),
    "BF200-ANC": (1.200, 3.900),
    "BF250-ANC": (1.200, 4.850),
}

# El catálogo indica b = 90; se interpreta como 900 mm por coherencia
# geométrica con el esquema y con el resto de dimensiones de la tabla.
BOVEDAS_TRIANGULO = {
    "BT150-ANC": (0.900, 3.600),
}

SEMICRUCETAS_ATIRANTADAS = {
    "ATC45-12": (1.250, 45),
    "ATC45-15": (1.500, 45),
    "ATC45-17": (1.750, 45),
    "ATC45-20": (2.000, 45),
    "ATC90-12": (1.250, 90),
    "ATC90-15": (1.500, 90),
    "ATC90-17": (1.750, 90),
    "ATC90-20": (2.000, 90),
}

SERIE_C_SEMICRUCETAS = {
    "ASC-12": 1.250,
    "ASC-15": 1.500,
    "ASC-17": 1.750,
    "ASC-20": 2.000,
    "ASC-22": 2.250,
    "ASC-25": 2.500,
}

SERIE_C_CRUCETAS_RECTAS = {
    "ARC-12": (1.250, 2.500),
    "ARC-15": (1.500, 3.000),
    "ARC-17": (1.750, 3.500),
    "ARC-20": (2.000, 4.000),
}

SERIE_C_ATIRANTADAS = {
    "ATC-12": 1.250,
    "ATC-15": 1.500,
    "ATC-17": 1.750,
    "ATC-20": 2.000,
    "ATC-22": 2.250,
    "ATC-25": 2.500,
}

SERIE_C_BOVEDAS_TRIANGULO = {
    "BT20-ANXC": (1.100, 2.000, 147),
}

SERIE_C_BOVEDAS_CAPA = {
    "BH15-ANXC": (1.200, 1.500, 180),
    "BH20-ANXC": (1.200, 2.000, 200),
    "BH25-ANXC": (1.300, 2.500, 240),
    "BH30-ANXC": (1.300, 3.000, 320),
}

SERIE_C_BOVEDAS_PICO = {
    "BF15-ANXC": (1.200, 1.500, 195),
    "BF20-ANXC": (1.200, 2.000, 220),
    "BF25-ANXC": (1.200, 2.500, 260),
}

CATALOGO_13000_CRUCETAS = {
    "ARGX-13": (1.350, 2.700),
    "ARGX-14": (1.450, 2.900),
    "ARGX-15": (1.500, 3.000),
    "ARGX-17": (1.750, 3.500),
}

PRESILLA_TRESBOLILLO = "TRESBOLILLO"

PRESILLA_RECTAS_MONTAJE_0 = {
    "ARP60-200": (2.000, 1.000),
    "ARP60-220": (2.200, 1.100),
    "ARP60-250": (2.500, 1.250),
    "ARP60-300": (3.000, 1.500),
}

PRESILLA_RECTAS_ARRIOSTRADAS = {
    "70D-150/S": 1.500,
    "70D-200/S": 2.000,
    "70D-250/S": 2.500,
    "70D-300/S": 3.000,
    "70D-350/S": 3.500,
    "70D-375/S": 3.750,
}

PRESILLA_BOVEDAS_PICO = (
    ("BF150-ANXP-P250", "PRESILLA_250", 0.430),
    ("BF150-ANXP-P400_1250", "PRESILLA_400_1250", 0.600),
    (
        "BF150-ANXP-P400_1250_TRENZADOS",
        "PRESILLA_400_1250_TRENZADOS",
        0.600,
    ),
)

assert (
    1
    + len(PRESILLA_RECTAS_MONTAJE_0)
    + len(PRESILLA_RECTAS_ARRIOSTRADAS)
    + len(PRESILLA_BOVEDAS_PICO)
) == 14

assert len(CATALOGO_13000_CRUCETAS) == 4
assert all(
    abs(longitud_total - 2 * semilongitud) < 1e-9
    for semilongitud, longitud_total in CATALOGO_13000_CRUCETAS.values()
)

assert sum(
    len(tabla)
    for tabla in (
        SERIE_C_SEMICRUCETAS,
        SERIE_C_CRUCETAS_RECTAS,
        SERIE_C_ATIRANTADAS,
        SERIE_C_BOVEDAS_TRIANGULO,
        SERIE_C_BOVEDAS_CAPA,
        SERIE_C_BOVEDAS_PICO,
    )
) == 24


def eliminar_catalogo_anterior():
    def eliminar_coleccion_recursiva(coleccion):
        for hija in list(coleccion.children):
            eliminar_coleccion_recursiva(hija)
        for objeto in list(coleccion.objects):
            bpy.data.objects.remove(objeto, do_unlink=True)
        bpy.data.collections.remove(coleccion)

    nombres_objetivo = [
        coleccion.name
        for coleccion in bpy.data.collections
        if coleccion.name == "CATALOGO_ANDEL"
        or coleccion.name.startswith("Andel_")
    ]
    for nombre in nombres_objetivo:
        coleccion = bpy.data.collections.get(nombre)
        if coleccion is not None:
            eliminar_coleccion_recursiva(coleccion)


def eliminar_catalogo_serie_c_anterior():
    catalogo = bpy.data.collections.get("CATALOGO_SERIE_C")
    if catalogo is None:
        return

    def eliminar_coleccion_recursiva(coleccion):
        for hija in list(coleccion.children):
            eliminar_coleccion_recursiva(hija)
        for objeto in list(coleccion.objects):
            bpy.data.objects.remove(objeto, do_unlink=True)
        bpy.data.collections.remove(coleccion)

    eliminar_coleccion_recursiva(catalogo)


def eliminar_catalogo_13000_anterior():
    catalogo = bpy.data.collections.get("CATALOGO_13000")
    if catalogo is None:
        return

    def eliminar_coleccion_recursiva(coleccion):
        for hija in list(coleccion.children):
            eliminar_coleccion_recursiva(hija)
        for objeto in list(coleccion.objects):
            bpy.data.objects.remove(objeto, do_unlink=True)
        bpy.data.collections.remove(coleccion)

    eliminar_coleccion_recursiva(catalogo)


def eliminar_catalogo_presilla_anterior():
    catalogo = bpy.data.collections.get("CATALOGO_PRESILLA")
    if catalogo is None:
        return

    def eliminar_coleccion_recursiva(coleccion):
        for hija in list(coleccion.children):
            eliminar_coleccion_recursiva(hija)
        for objeto in list(coleccion.objects):
            bpy.data.objects.remove(objeto, do_unlink=True)
        bpy.data.collections.remove(coleccion)

    eliminar_coleccion_recursiva(catalogo)


def crear_material(nombre, color, metalico=0.75, rugosidad=0.38):
    material = bpy.data.materials.get(nombre)
    if material is None:
        material = bpy.data.materials.new(nombre)
    material.diffuse_color = (*color, 1.0)
    material.metallic = metalico
    material.roughness = rugosidad
    material.use_nodes = True

    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = (*color, 1.0)
        principled.inputs["Metallic"].default_value = metalico
        principled.inputs["Roughness"].default_value = rugosidad

    return material


def nueva_coleccion(nombre, coleccion_padre):
    coleccion = bpy.data.collections.new(nombre)
    coleccion_padre.children.link(coleccion)
    return coleccion


def obtener_raiz_catalogos_crucetas():
    nombre = "01_CATALOGOS_CRUCETAS"
    raiz = bpy.data.collections.get(nombre)
    if raiz is None:
        raiz = bpy.data.collections.new(nombre)
    if bpy.context.scene.collection.children.get(nombre) is None:
        bpy.context.scene.collection.children.link(raiz)
    return raiz


def crear_barra(coleccion, inicio, final, espesor, objetos):
    p1 = Vector(inicio)
    p2 = Vector(final)
    direccion = p2 - p1
    longitud = direccion.length

    if longitud < 0.0001:
        return

    bpy.ops.mesh.primitive_cube_add(size=1, location=(p1 + p2) / 2)
    barra = bpy.context.object
    barra.dimensions = (espesor, espesor, longitud)
    barra.rotation_mode = "QUATERNION"
    barra.rotation_quaternion = direccion.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    coleccion.objects.link(barra)
    for anterior in list(barra.users_collection):
        if anterior != coleccion:
            anterior.objects.unlink(barra)

    objetos.append(barra)


def unir_modelo(objetos, referencia, material, propiedades):
    bpy.ops.object.select_all(action="DESELECT")
    for objeto in objetos:
        objeto.select_set(True)

    bpy.context.view_layer.objects.active = objetos[0]
    bpy.ops.object.join()
    modelo = bpy.context.object
    modelo.name = referencia
    modelo.data.name = f"Malla_{referencia}"
    modelo.data.materials.clear()
    modelo.data.materials.append(material)
    modelo.color = material.diffuse_color

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

    for clave, valor in propiedades.items():
        modelo[clave] = valor

    return modelo


def crear_geometria_semicruceta_plana(
    coleccion,
    objetos,
    longitud_a,
    lado=1,
    incluir_brazos_acople=True,
):
    e = ESPESOR_NORMAL
    media_cara = ANCHO_CARA_ACOPLE / 2
    x_frontal = lado * media_cara
    x_posterior = -lado * media_cara
    x_punta = lado * longitud_a

    if longitud_a <= media_cara:
        raise ValueError("La medida a debe superar la mitad de la cara de acople")

    # La medida a nace en el eje central del armado (x=0). El triángulo solo
    # ocupa desde la cara frontal hasta x=a; detrás de su base continúan dos
    # brazos rectos y paralelos que abrazan toda la anchura del armado.
    if incluir_brazos_acople:
        for y in (-media_cara, media_cara):
            crear_barra(
                coleccion,
                (x_posterior, y, 0),
                (x_frontal, y, 0),
                e,
                objetos,
            )

    crear_barra(
        coleccion,
        (x_frontal, -media_cara, 0),
        (x_punta, 0, 0),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_frontal, media_cara, 0),
        (x_punta, 0, 0),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_frontal, -media_cara, 0),
        (x_frontal, media_cara, 0),
        e,
        objetos,
    )



def crear_semicruceta_plana(
    referencia,
    longitud,
    material,
    coleccion,
    propiedades_extra=None,
):
    objetos = []
    crear_geometria_semicruceta_plana(coleccion, objetos, longitud)
    propiedades = {
        "familia": "ASC",
        "tipo": "semicruceta_plana",
        "longitud_a_m": longitud,
        "referencia_medida_a": "eje_central_armado_a_punta",
        "longitud_brazos_acople_m": ANCHO_CARA_ACOPLE,
        "compatible_con": "M50,M60",
    }
    if propiedades_extra:
        propiedades.update(propiedades_extra)

    return unir_modelo(
        objetos,
        referencia,
        material,
        propiedades,
    )


def crear_cruceta_recta(
    referencia,
    longitud_semicruceta,
    longitud_total,
    material,
    coleccion,
    propiedades_extra,
):
    objetos = []
    semiancho_central = ANCHO_CARA_ACOPLE / 2

    for lado in (-1, 1):
        crear_geometria_semicruceta_plana(
            coleccion,
            objetos,
            longitud_semicruceta,
            lado=lado,
            incluir_brazos_acople=False,
        )

    mitad_profundidad = ANCHO_CARA_ACOPLE / 2
    for y in (-mitad_profundidad, mitad_profundidad):
        crear_barra(
            coleccion,
            (-semiancho_central, y, 0),
            (semiancho_central, y, 0),
            ESPESOR_NORMAL,
            objetos,
        )

    propiedades = {
        "familia": "ARC",
        "tipo": "cruceta_recta",
        "longitud_a_m": longitud_semicruceta,
        "longitud_total_m": longitud_total,
        "referencia_medida_a": "eje_central_armado_a_punta",
    }
    propiedades.update(propiedades_extra)
    return unir_modelo(objetos, referencia, material, propiedades)


def crear_geometria_cruceta_completa_modular(
    coleccion,
    objetos,
    longitud_a,
    altura_z=0.0,
    incluir_barras_amc=False,
):
    semiancho_central = ANCHO_CARA_ACOPLE / 2
    mitad_profundidad = ANCHO_ANCLAJE / 2

    for lado in (-1, 1):
        x_raiz = lado * semiancho_central
        x_punta = lado * longitud_a
        crear_barra(
            coleccion,
            (x_raiz, -mitad_profundidad, altura_z),
            (x_punta, 0.0, altura_z),
            ESPESOR_NORMAL,
            objetos,
        )
        crear_barra(
            coleccion,
            (x_raiz, mitad_profundidad, altura_z),
            (x_punta, 0.0, altura_z),
            ESPESOR_NORMAL,
            objetos,
        )
        crear_barra(
            coleccion,
            (x_raiz, -mitad_profundidad, altura_z),
            (x_raiz, mitad_profundidad, altura_z),
            ESPESOR_NORMAL,
            objetos,
        )

        if incluir_barras_amc:
            fraccion = 0.48
            x_interior = x_raiz + (x_punta - x_raiz) * fraccion
            semiancho_interior = mitad_profundidad * (1.0 - fraccion)
            crear_barra(
                coleccion,
                (x_interior, -semiancho_interior, altura_z),
                (x_interior, semiancho_interior, altura_z),
                ESPESOR_NORMAL,
                objetos,
            )

    for y in (-mitad_profundidad, mitad_profundidad):
        crear_barra(
            coleccion,
            (-semiancho_central, y, altura_z),
            (semiancho_central, y, altura_z),
            ESPESOR_NORMAL,
            objetos,
        )


def crear_cruceta_amc(
    referencia,
    longitud_a,
    longitud_total,
    material,
    coleccion,
):
    objetos = []
    crear_geometria_cruceta_completa_modular(
        coleccion,
        objetos,
        longitud_a,
        incluir_barras_amc=True,
    )
    return unir_modelo(
        objetos,
        referencia,
        material,
        {
            "familia": "AMC",
            "tipo": "cruceta_paso_lateral",
            "referencia_catalogo": referencia,
            "a_m": longitud_a,
            "longitud_l_m": longitud_total,
            "niveles_resistencia_compatibles": [1, 2, 3, 4],
            "compatible_con": "M50,M60",
        },
    )


def crear_geometria_gancho_herraje_puente(
    coleccion,
    objetos,
    altura_origen=0.0,
):
    def girar_90_antihorario(punto):
        punto = Vector(punto)
        return Vector((-punto.y, punto.x, punto.z))

    def bezier_cubica(p0, p1, p2, p3, pasos):
        puntos = []
        for indice in range(pasos + 1):
            t = indice / pasos
            u = 1.0 - t
            puntos.append(
                Vector(p0) * (u ** 3)
                + Vector(p1) * (3.0 * u * u * t)
                + Vector(p2) * (3.0 * u * t * t)
                + Vector(p3) * (t ** 3)
            )
        return puntos

    modulo = ANCHO_CARA_ACOPLE
    z0 = altura_origen

    # Perfil del herraje de puente: salida casi horizontal desde el acople,
    # panza exterior redondeada y retorno superior horizontal. Los dos Bezier
    # comparten tangente para evitar el antiguo quiebro en forma de Z.
    tramo_inferior = bezier_cubica(
        (0.0, 0.0, z0),
        (modulo * 0.16, 0.0, z0),
        (modulo * 0.55, 0.0, z0 + modulo * 0.22),
        (modulo * 0.66, 0.0, z0 + modulo * 0.43),
        8,
    )
    tramo_superior = bezier_cubica(
        tramo_inferior[-1],
        (modulo * 0.57, 0.0, z0 + modulo * 0.66),
        (modulo * 0.25, 0.0, z0 + modulo * 1.08),
        (modulo * 0.05, 0.0, z0 + modulo * 1.13),
        10,
    )
    # El plano del gancho se gira 90 grados alrededor de Z para quedar
    # paralelo a la cruceta en los montajes TG. La misma orientación se usa
    # en el modelo independiente del catálogo de herrajes.
    puntos = [
        girar_90_antihorario(punto)
        for punto in tramo_inferior + tramo_superior[1:]
    ]

    for inicio, final in zip(puntos, puntos[1:]):
        crear_barra(
            coleccion,
            inicio,
            final,
            ESPESOR_NORMAL,
            objetos,
        )

    crear_barra(
        coleccion,
        puntos[-1],
        girar_90_antihorario(
            (-modulo * 0.43, 0.0, z0 + modulo * 1.13)
        ),
        ESPESOR_NORMAL,
        objetos,
    )


def crear_gancho_herraje_puente(material, coleccion):
    objetos = []
    crear_geometria_gancho_herraje_puente(coleccion, objetos)
    return unir_modelo(
        objetos,
        GANCHO_HERRAJE_PUENTE,
        material,
        {
            "familia": "ANDEL",
            "tipo": "gancho_herraje_puente",
            "referencia_catalogo": GANCHO_HERRAJE_PUENTE,
            "compatible_con": "M50,M60",
            "punto_acople": "origen",
        },
    )


def crear_montaje_triangulo_tg(
    referencia,
    referencia_tabla,
    separacion_fases_d,
    separacion_eje_a,
    altura_triangulo_b,
    material,
    coleccion,
):
    objetos = []
    crear_geometria_cruceta_completa_modular(
        coleccion,
        objetos,
        separacion_eje_a,
        altura_z=-altura_triangulo_b,
        incluir_barras_amc=False,
    )
    crear_geometria_gancho_herraje_puente(coleccion, objetos)
    return unir_modelo(
        objetos,
        referencia,
        material,
        {
            "familia": "ANDEL",
            "tipo": "triangulo_TG",
            "referencia_tabla": referencia_tabla,
            "separacion_fases_d_m": separacion_fases_d,
            "separacion_eje_a_m": separacion_eje_a,
            "altura_triangulo_b_m": altura_triangulo_b,
            "compatible_con": "M50,M60",
        },
    )


def crear_semicruceta_atirantada(
    referencia,
    longitud,
    serie,
    material,
    altura_acople_m,
    referencia_catalogo,
    armado_compatible,
    coleccion,
    propiedades_extra=None,
):
    objetos = []
    e = ESPESOR_SERIE_90 if serie == 90 else ESPESOR_NORMAL
    # Ejes de las barras coincidentes con los cordones metálicos exteriores
    # del armado; así las piezas se solapan por su cara de contacto.
    mitad = (ANCHO_CARA_ACOPLE - ESPESOR_NORMAL) / 2
    x_cara_acople = mitad
    altura_tirante = altura_acople_m

    # Base completamente paralela al suelo. Nace en la cara exterior del
    # armado, no en su interior, y termina en x=a medido desde el eje central.
    crear_barra(
        coleccion,
        (x_cara_acople, -mitad, 0),
        (longitud, 0, 0),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_cara_acople, mitad, 0),
        (longitud, 0, 0),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_cara_acople, -mitad, 0),
        (x_cara_acople, mitad, 0),
        e,
        objetos,
    )

    # Tirantes superiores unidos a la punta.
    crear_barra(
        coleccion,
        (x_cara_acople, -mitad, altura_tirante),
        (longitud, 0, 0),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_cara_acople, mitad, altura_tirante),
        (longitud, 0, 0),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_cara_acople, -mitad, altura_tirante),
        (x_cara_acople, mitad, altura_tirante),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_cara_acople, -mitad, 0),
        (x_cara_acople, -mitad, altura_tirante),
        e,
        objetos,
    )
    crear_barra(
        coleccion,
        (x_cara_acople, mitad, 0),
        (x_cara_acople, mitad, altura_tirante),
        e,
        objetos,
    )

    propiedades = {
        "familia": f"ATC{serie}",
        "tipo": "semicruceta_atirantada",
        "longitud_a_m": longitud,
        "referencia_medida_a": "eje_central_armado_a_punta",
        "base_paralela_suelo": True,
        "x_cara_acople_m": x_cara_acople,
        "serie": serie,
        "compatible_con": "M50,M60",
        "altura_acople_m": altura_acople_m,
        "armado_compatible": armado_compatible,
        "referencia_catalogo": referencia_catalogo,
    }
    if propiedades_extra:
        propiedades.update(propiedades_extra)

    return unir_modelo(objetos, referencia, material, propiedades)


def perfil_capa(x, mitad, altura_b):
    return altura_b


def perfil_pico(x, mitad, altura_b):
    desnivel = min(0.28, altura_b * 0.22)
    return altura_b - desnivel * abs(x) / mitad


def perfil_triangulo(x, mitad, altura_b):
    semiancho_cabeza = min(0.32, mitad * 0.24)
    altura_extremo = altura_b * 0.28
    if abs(x) <= semiancho_cabeza:
        return altura_b
    fraccion = (abs(x) - semiancho_cabeza) / (mitad - semiancho_cabeza)
    return altura_b + (altura_extremo - altura_b) * fraccion


def crear_tirante_boveda(
    coleccion,
    objetos,
    lado,
    x_apoyo,
    z_apoyo,
    espesor,
    altura_acople_m,
    numero_paneles=3,
):
    """Tirante que se estrecha desde una cara cuadrada hasta una arista."""
    raiz_x = lado * (ANCHO_CARA_ACOPLE / 2)
    media_cara_raiz = ANCHO_CARA_ACOPLE / 2
    media_arista_superior = FONDO_CELOSIA / 2
    z_raiz_inferior = -altura_acople_m
    z_raiz_superior = 0.0

    # Dos caras trianguladas: cuadradas en la unión y convergentes arriba.
    for signo_y in (-1, 1):
        inferiores = []
        superiores = []
        for indice in range(numero_paneles + 1):
            fraccion = indice / numero_paneles
            x = raiz_x + (x_apoyo - raiz_x) * fraccion
            media_profundidad = (
                media_cara_raiz
                + (media_arista_superior - media_cara_raiz) * fraccion
            )
            y = signo_y * media_profundidad
            inferiores.append(
                (x, y, z_raiz_inferior + (z_apoyo - z_raiz_inferior) * fraccion)
            )
            superiores.append(
                (x, y, z_raiz_superior + (z_apoyo - z_raiz_superior) * fraccion)
            )

        for indice in range(numero_paneles):
            li = inferiores[indice]
            ls = inferiores[indice + 1]
            ui = superiores[indice]
            us = superiores[indice + 1]
            crear_barra(coleccion, li, ls, espesor, objetos)
            crear_barra(coleccion, ui, us, espesor, objetos)

            if indice % 2 == 0:
                crear_barra(coleccion, li, us, espesor, objetos)
            else:
                crear_barra(coleccion, ui, ls, espesor, objetos)

        for indice in range(numero_paneles):
            crear_barra(
                coleccion,
                inferiores[indice],
                superiores[indice],
                espesor,
                objetos,
            )

    # Aristas transversales: 0,510 m abajo y 0,300 m en la unión superior.
    for indice in range(numero_paneles + 1):
        fraccion = indice / numero_paneles
        x = raiz_x + (x_apoyo - raiz_x) * fraccion
        media_profundidad = (
            media_cara_raiz
            + (media_arista_superior - media_cara_raiz) * fraccion
        )
        z_inferior = z_raiz_inferior + (z_apoyo - z_raiz_inferior) * fraccion
        z_superior = z_raiz_superior + (z_apoyo - z_raiz_superior) * fraccion
        crear_barra(
            coleccion,
            (x, -media_profundidad, z_inferior),
            (x, media_profundidad, z_inferior),
            espesor,
            objetos,
        )
        if indice < numero_paneles:
            crear_barra(
                coleccion,
                (x, -media_profundidad, z_superior),
                (x, media_profundidad, z_superior),
                espesor,
                objetos,
            )


def crear_viga_superior_celosia(
    coleccion,
    objetos,
    longitud_l,
    altura_b,
    forma,
    espesor,
):
    """Viga superior espacial con paneles triangulados alternos."""
    mitad = longitud_l / 2
    profundidad = FONDO_CELOSIA / 2
    numero_paneles = max(6, int(round(longitud_l / 0.48)))
    if numero_paneles % 2 != 0:
        numero_paneles += 1

    if forma == "capa":
        perfil = perfil_capa
    elif forma == "pico":
        perfil = perfil_pico
    else:
        perfil = perfil_triangulo

    nodos = []
    for indice in range(numero_paneles + 1):
        x = -mitad + longitud_l * indice / numero_paneles
        nodos.append((x, perfil(x, mitad, altura_b)))

    # Dos cordones longitudinales que siguen el perfil de la bóveda.
    for y in (-profundidad, profundidad):
        for p1, p2 in zip(nodos, nodos[1:]):
            crear_barra(
                coleccion,
                (p1[0], y, p1[1]),
                (p2[0], y, p2[1]),
                espesor,
                objetos,
            )

    # Travesaños y diagonales alternas: vistos desde arriba forman triángulos.
    for x, z in nodos:
        crear_barra(
            coleccion,
            (x, -profundidad, z),
            (x, profundidad, z),
            espesor,
            objetos,
        )

    for indice, (p1, p2) in enumerate(zip(nodos, nodos[1:])):
        y_inicio = -profundidad if indice % 2 == 0 else profundidad
        y_final = -y_inicio
        crear_barra(
            coleccion,
            (p1[0], y_inicio, p1[1]),
            (p2[0], y_final, p2[1]),
            espesor,
            objetos,
        )

    return perfil


def crear_semicerchas_triangulo(
    coleccion,
    objetos,
    longitud_l,
    altura_b,
    espesor,
):
    """Dos alas trianguladas desde caras cuadradas centrales hasta los extremos."""
    mitad = longitud_l / 2
    semiancho_cabeza = 0.510 / 2
    media_cara_raiz = FONDO_CELOSIA / 2
    media_arista_extremo = FONDO_CELOSIA / 2
    numero_paneles = 4

    for lado in (-1, 1):
        x_raiz = lado * semiancho_cabeza
        x_extremo = lado * mitad

        # Cada cara lateral se estrecha tanto en altura como en profundidad.
        for signo_y in (-1, 1):
            inferiores = []
            superiores = []
            for indice in range(numero_paneles + 1):
                fraccion = indice / numero_paneles
                x = x_raiz + (x_extremo - x_raiz) * fraccion
                y = signo_y * (
                    media_cara_raiz
                    + (media_arista_extremo - media_cara_raiz) * fraccion
                )
                # La base de ambas alas permanece horizontal a cota z = 0.
                z_inferior = 0.0
                z_superior = altura_b * (1 - fraccion)
                inferiores.append((x, y, z_inferior))
                superiores.append((x, y, z_superior))

            for indice in range(numero_paneles):
                li = inferiores[indice]
                ls = inferiores[indice + 1]
                ui = superiores[indice]
                us = superiores[indice + 1]

                crear_barra(coleccion, li, ls, espesor, objetos)
                crear_barra(coleccion, ui, us, espesor, objetos)

        # Aristas transversales: cuadradas en la raíz y más estrechas hacia fuera.
        for indice in range(numero_paneles + 1):
            if indice not in (0, numero_paneles):
                continue
            fraccion = indice / numero_paneles
            x = x_raiz + (x_extremo - x_raiz) * fraccion
            media_profundidad = (
                media_cara_raiz
                + (media_arista_extremo - media_cara_raiz) * fraccion
            )
            z_inferior = 0.0
            z_superior = altura_b * (1 - fraccion)
            crear_barra(
                coleccion,
                (x, -media_profundidad, z_inferior),
                (x, media_profundidad, z_inferior),
                espesor,
                objetos,
            )
            if indice < numero_paneles:
                crear_barra(
                    coleccion,
                    (x, -media_profundidad, z_superior),
                    (x, media_profundidad, z_superior),
                    espesor,
                    objetos,
                )

    # Cabeza horizontal corta, alineada con el fondo de la celosía para que
    # los encuentros con las alas no formen piquitos sobresalientes.
    for y in (-media_cara_raiz, media_cara_raiz):
        crear_barra(
            coleccion,
            (-semiancho_cabeza, y, altura_b),
            (semiancho_cabeza, y, altura_b),
            espesor,
            objetos,
        )
    crear_barra(
        coleccion,
        (-semiancho_cabeza, -media_cara_raiz, altura_b),
        (-semiancho_cabeza, media_cara_raiz, altura_b),
        espesor,
        objetos,
    )
    crear_barra(
        coleccion,
        (semiancho_cabeza, -media_cara_raiz, altura_b),
        (semiancho_cabeza, media_cara_raiz, altura_b),
        espesor,
        objetos,
    )

    # Dos parejas paralelas delimitan el hueco central, una barra por cada
    # cara en profundidad y sin cruces ni convergencias.
    for lado in (-1, 1):
        x = lado * semiancho_cabeza
        for y in (-media_cara_raiz, media_cara_raiz):
            crear_barra(
                coleccion,
                (x, y, altura_b),
                (
                    x
                    + lado
                    * (mitad - semiancho_cabeza)
                    / numero_paneles,
                    y,
                    0.0,
                ),
                espesor,
                objetos,
            )

def crear_boveda(
    referencia,
    altura_b,
    longitud_l,
    forma,
    material,
    altura_acople_m,
    referencia_catalogo,
    armado_compatible,
    coleccion,
    propiedades_extra=None,
):
    objetos = []
    e = ESPESOR_NORMAL

    if forma in ("capa", "pico"):
        perfil = crear_viga_superior_celosia(
            coleccion,
            objetos,
            longitud_l,
            altura_b,
            forma,
            e,
        )

        mitad = longitud_l / 2
        x_apoyo = mitad * 0.44
        z_apoyo = perfil(x_apoyo, mitad, altura_b)
        crear_tirante_boveda(
            coleccion,
            objetos,
            -1,
            -x_apoyo,
            z_apoyo,
            e,
            altura_acople_m,
        )
        crear_tirante_boveda(
            coleccion,
            objetos,
            1,
            x_apoyo,
            z_apoyo,
            e,
            altura_acople_m,
        )
    else:
        crear_semicerchas_triangulo(
            coleccion,
            objetos,
            longitud_l,
            altura_b,
            e,
        )

        # Los tirantes parten de las caras inferiores de los últimos bloques
        # de la cabeza y se unen a las alas superiores de la bóveda.
        mitad = longitud_l / 2
        semiancho_cabeza = ANCHO_CARA_ACOPLE / 2
        x_apoyo = semiancho_cabeza + (mitad - semiancho_cabeza) / 2
        z_apoyo = altura_b * (
            1 - (x_apoyo - semiancho_cabeza) / (mitad - semiancho_cabeza)
        )
        crear_tirante_boveda(
            coleccion,
            objetos,
            -1,
            -x_apoyo,
            z_apoyo,
            e,
            altura_acople_m,
            numero_paneles=1,
        )
        crear_tirante_boveda(
            coleccion,
            objetos,
            1,
            x_apoyo,
            z_apoyo,
            e,
            altura_acople_m,
            numero_paneles=1,
        )

    propiedades = {
        "familia": "boveda",
        "tipo": f"boveda_{forma}",
        "altura_b_m": altura_b,
        "longitud_l_m": longitud_l,
        "compatible_con": "M50,M60",
        "altura_acople_m": altura_acople_m,
        "armado_compatible": armado_compatible,
        "referencia_catalogo": referencia_catalogo,
    }

    if forma in ("capa", "pico"):
        propiedades.update(
            {
                "separacion_fases_m": longitud_l / 2,
                "cable_izquierdo_x_m": -longitud_l / 2,
                "cable_central_x_m": 0.0,
                "cable_derecho_x_m": longitud_l / 2,
                "cota_union_superior_z_m": 0.0,
                "cota_cable_central_z_m": altura_b,
            }
        )

    if propiedades_extra:
        propiedades.update(propiedades_extra)

    modelo = unir_modelo(
        objetos,
        referencia,
        material,
        propiedades,
    )

    return modelo


# --------------------------------------------------
# PIEZAS PARA APOYOS DE PRESILLA
# --------------------------------------------------

ANCHO_EXTERIOR_PRESILLA = 0.325
HUECO_INTERIOR_PRESILLA = 0.270
ANCHO_PERFIL_PRESILLA = (
    ANCHO_EXTERIOR_PRESILLA - HUECO_INTERIOR_PRESILLA
) / 2
EJE_CORDON_PRESILLA = (
    HUECO_INTERIOR_PRESILLA + ANCHO_PERFIL_PRESILLA
) / 2


def crear_prisma_presilla(coleccion, centro, dimensiones, objetos):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centro)
    prisma = bpy.context.object
    prisma.dimensions = dimensiones
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    coleccion.objects.link(prisma)
    for anterior in list(prisma.users_collection):
        if anterior != coleccion:
            anterior.objects.unlink(prisma)

    objetos.append(prisma)


def crear_placas_marco_presilla(coleccion, objetos):
    posicion = EJE_CORDON_PRESILLA

    # Marco completo de 0,325 m, con hueco central de 0,270 m.
    for y in (-posicion, posicion):
        crear_prisma_presilla(
            coleccion,
            (0.0, y, 0.0),
            (
                ANCHO_EXTERIOR_PRESILLA,
                ANCHO_PERFIL_PRESILLA,
                ESPESOR_NORMAL,
            ),
            objetos,
        )
    for x in (-posicion, posicion):
        crear_prisma_presilla(
            coleccion,
            (x, 0.0, 0.0),
            (
                ANCHO_PERFIL_PRESILLA,
                ANCHO_EXTERIOR_PRESILLA,
                ESPESOR_NORMAL,
            ),
            objetos,
        )

    # Las cuatro placas quedan centradas sobre los nodos del marco.
    for x in (-posicion, posicion):
        for y in (-posicion, posicion):
            crear_prisma_presilla(
                coleccion,
                (x, y, 0.0),
                (
                    ANCHO_PERFIL_PRESILLA,
                    ANCHO_PERFIL_PRESILLA,
                    ESPESOR_NORMAL,
                ),
                objetos,
            )


def crear_semicruceta_tresbolillo_presilla(
    referencia,
    material,
    coleccion,
):
    objetos = []
    longitud = 1.000

    for y in (-EJE_CORDON_PRESILLA, EJE_CORDON_PRESILLA):
        crear_barra(
            coleccion,
            (EJE_CORDON_PRESILLA, y, 0.0),
            (longitud - ANCHO_PERFIL_PRESILLA / 2, y, 0.0),
            ANCHO_PERFIL_PRESILLA,
            objetos,
        )

    crear_barra(
        coleccion,
        (longitud - ANCHO_PERFIL_PRESILLA / 2, -EJE_CORDON_PRESILLA, 0.0),
        (longitud - ANCHO_PERFIL_PRESILLA / 2, EJE_CORDON_PRESILLA, 0.0),
        ANCHO_PERFIL_PRESILLA,
        objetos,
    )
    crear_placas_marco_presilla(coleccion, objetos)

    return unir_modelo(
        objetos,
        referencia,
        material,
        {
            "catalogo": "PRESILLA",
            "referencia_catalogo": referencia,
            "tipo": "semicruceta_tresbolillo",
            "longitud_m": longitud,
            "montajes_compatibles": (
                "TRESBOLILLO 1.0,TRESBOLILLO 1.5,"
                "TRESBOLILLO 2.0,TRESBOLILLO 2.5"
            ),
            "distancias_primera_tercera_m": [1.0, 1.5, 2.0, 3.0],
            "sistema_acople": "presilla_interior",
        },
    )


def crear_envolvente_recta_presilla(longitud, coleccion, objetos):
    mitad = longitud / 2
    for y in (-EJE_CORDON_PRESILLA, EJE_CORDON_PRESILLA):
        crear_prisma_presilla(
            coleccion,
            (0.0, y, 0.0),
            (longitud, ANCHO_PERFIL_PRESILLA, ESPESOR_NORMAL),
            objetos,
        )

    for x in (
        -mitad + ANCHO_PERFIL_PRESILLA / 2,
        mitad - ANCHO_PERFIL_PRESILLA / 2,
    ):
        crear_prisma_presilla(
            coleccion,
            (x, 0.0, 0.0),
            (
                ANCHO_PERFIL_PRESILLA,
                ANCHO_EXTERIOR_PRESILLA,
                ESPESOR_NORMAL,
            ),
            objetos,
        )


def crear_recta_montaje_0_presilla(
    referencia,
    longitud,
    separacion_fases_m,
    material,
    coleccion,
):
    objetos = []
    crear_envolvente_recta_presilla(longitud, coleccion, objetos)
    return unir_modelo(
        objetos,
        referencia,
        material,
        {
            "catalogo": "PRESILLA",
            "referencia_catalogo": referencia,
            "tipo": "cruceta_recta_montaje_0",
            "longitud_l_m": longitud,
            "separacion_fases_m": separacion_fases_m,
            "sistema_acople": "presilla_interior",
        },
    )


def crear_recta_arriostrada_presilla(
    referencia,
    longitud,
    material,
    coleccion,
):
    objetos = []
    crear_envolvente_recta_presilla(longitud, coleccion, objetos)

    mitad = longitud / 2
    semiancho_marco = ANCHO_EXTERIOR_PRESILLA / 2
    longitud_arriostrada = mitad - semiancho_marco
    numero_paneles = max(1, int(round(longitud_arriostrada / 0.50)))

    for lado in (-1, 1):
        x_central = lado * semiancho_marco
        x_exterior = lado * mitad
        nodos = [
            x_central + (x_exterior - x_central) * indice / numero_paneles
            for indice in range(numero_paneles + 1)
        ]

        for x in nodos[:-1]:
            crear_prisma_presilla(
                coleccion,
                (x, 0.0, 0.0),
                (
                    ANCHO_PERFIL_PRESILLA,
                    ANCHO_EXTERIOR_PRESILLA,
                    ESPESOR_NORMAL,
                ),
                objetos,
            )

        for x_1, x_2 in zip(nodos, nodos[1:]):
            crear_barra(
                coleccion,
                (x_1, -EJE_CORDON_PRESILLA, 0.0),
                (x_2, EJE_CORDON_PRESILLA, 0.0),
                ESPESOR_NORMAL,
                objetos,
            )
            crear_barra(
                coleccion,
                (x_1, EJE_CORDON_PRESILLA, 0.0),
                (x_2, -EJE_CORDON_PRESILLA, 0.0),
                ESPESOR_NORMAL,
                objetos,
            )

    return unir_modelo(
        objetos,
        referencia,
        material,
        {
            "catalogo": "PRESILLA",
            "referencia_catalogo": referencia,
            "tipo": "cruceta_recta_arriostrada",
            "longitud_l_m": longitud,
            "sistema_acople": "presilla_interior",
        },
    )


def crear_boveda_pico_presilla(
    referencia,
    cabeza_presilla_compatible,
    altura_base_lateral,
    material,
    coleccion,
):
    objetos = []
    separacion_fases = 1.500
    altura_b = 1.200
    desnivel_cubierta = 0.200
    altura_extremos = altura_b - desnivel_cubierta

    crear_barra(
        coleccion,
        (-separacion_fases, 0.0, altura_extremos),
        (0.0, 0.0, altura_b),
        ESPESOR_NORMAL,
        objetos,
    )
    crear_barra(
        coleccion,
        (0.0, 0.0, altura_b),
        (separacion_fases, 0.0, altura_extremos),
        ESPESOR_NORMAL,
        objetos,
    )

    # Dos caras laterales cuadradas del marco de presilla. Desde sus cuatro
    # vértices, cada tirante converge hacia una arista bajo cada faldón.
    media_base = EJE_CORDON_PRESILLA
    media_arista_superior = ESPESOR_NORMAL / 2
    for lado in (-1, 1):
        x_base = lado * media_base
        x_superior = lado * separacion_fases / 2
        z_superior = altura_b - (
            desnivel_cubierta * abs(x_superior) / separacion_fases
        )
        base = (
            (x_base, -media_base, -altura_base_lateral),
            (x_base, media_base, -altura_base_lateral),
            (x_base, media_base, 0.0),
            (x_base, -media_base, 0.0),
        )
        superior = (
            (x_superior, -media_arista_superior, z_superior),
            (x_superior, media_arista_superior, z_superior),
        )

        for inicio, fin in zip(base, base[1:] + base[:1]):
            crear_barra(
                coleccion, inicio, fin, ANCHO_PERFIL_PRESILLA, objetos
            )

        crear_barra(
            coleccion, superior[0], superior[1], ESPESOR_NORMAL, objetos
        )
        crear_barra(
            coleccion, base[0], superior[0], ESPESOR_NORMAL, objetos
        )
        crear_barra(
            coleccion, base[3], superior[0], ESPESOR_NORMAL, objetos
        )
        crear_barra(
            coleccion, base[1], superior[1], ESPESOR_NORMAL, objetos
        )
        crear_barra(
            coleccion, base[2], superior[1], ESPESOR_NORMAL, objetos
        )
        crear_barra(
            coleccion, base[0], superior[1], ESPESOR_NORMAL, objetos
        )
        crear_barra(
            coleccion, base[2], superior[0], ESPESOR_NORMAL, objetos
        )

    return unir_modelo(
        objetos,
        referencia,
        material,
        {
            "catalogo": "PRESILLA",
            "referencia_catalogo": referencia,
            "tipo": "boveda_pico_presilla",
            "niveles_resistencia_compatibles": [1, 2, 3, 4],
            "cabeza_presilla_compatible": cabeza_presilla_compatible,
            "altura_base_lateral_m": altura_base_lateral,
            "longitud_l_m": 2 * separacion_fases,
            "separacion_fases_m": separacion_fases,
            "altura_b_m": altura_b,
            "sistema_acople": "presilla_interior",
        },
    )


def crear_catalogo():
    eliminar_catalogo_anterior()

    acero = crear_material(
        "Acero_Galvanizado_Andel",
        (0.96, 0.97, 0.98),
        0.02,
        0.55,
    )
    acero_90 = crear_material(
        "Acero_Galvanizado_Andel_S90",
        (0.92, 0.94, 0.96),
        0.03,
        0.52,
    )
    modelos = []
    catalogo = nueva_coleccion("CATALOGO_ANDEL", obtener_raiz_catalogos_crucetas())

    coleccion_asc = nueva_coleccion("01_SEMICRUCETAS_ASC", catalogo)
    for referencia, longitud in SEMICRUCETAS_ASC.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_asc)
        modelos.append(
            crear_semicruceta_plana(
                referencia,
                longitud,
                acero,
                coleccion_referencia,
            )
        )

    coleccion_arcx = nueva_coleccion("02_CRUCETAS_ARCX", catalogo)
    for referencia, (longitud_a, longitud_total) in CRUCETAS_ARCX.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_arcx)
        modelos.append(
            crear_cruceta_recta(
                referencia,
                longitud_a,
                longitud_total,
                acero,
                coleccion_referencia,
                {
                    "familia": "ARCX",
                    "referencia_catalogo": referencia,
                    "a_m": longitud_a,
                    "longitud_l_m": longitud_total,
                    "niveles_resistencia_compatibles": [1, 2, 3, 4],
                    "compatible_con": "M50,M60",
                },
            )
        )

    coleccion_amc = nueva_coleccion(
        "03_CRUCETAS_AMC_PASO_LATERAL", catalogo
    )
    for referencia, (longitud_a, longitud_total) in CRUCETAS_AMC.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_amc)
        modelos.append(
            crear_cruceta_amc(
                referencia,
                longitud_a,
                longitud_total,
                acero,
                coleccion_referencia,
            )
        )

    coleccion_herrajes = nueva_coleccion("04_HERRAJES_PUENTE", catalogo)
    coleccion_gancho = nueva_coleccion(
        GANCHO_HERRAJE_PUENTE, coleccion_herrajes
    )
    modelos.append(crear_gancho_herraje_puente(acero, coleccion_gancho))

    coleccion_tg = nueva_coleccion("05_MONTAJES_TRIANGULO_TG", catalogo)
    for referencia, datos in MONTAJES_TRIANGULO_TG.items():
        referencia_tabla, separacion_d, separacion_a, altura_b = datos
        coleccion_referencia = nueva_coleccion(referencia, coleccion_tg)
        modelos.append(
            crear_montaje_triangulo_tg(
                referencia,
                referencia_tabla,
                separacion_d,
                separacion_a,
                altura_b,
                acero,
                coleccion_referencia,
            )
        )

    coleccion_bovedas = nueva_coleccion("06_BOVEDAS", catalogo)
    coleccion_bh = nueva_coleccion("01_CAPA_BH", coleccion_bovedas)
    for referencia, (altura, longitud) in BOVEDAS_CAPA.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_bh)
        for sufijo, altura_acople_m, armado_compatible in ALTURAS_ACOPLE:
            coleccion_altura = nueva_coleccion(sufijo, coleccion_referencia)
            modelos.append(
                crear_boveda(
                    f"{referencia}_{sufijo}",
                    altura,
                    longitud,
                    "capa",
                    acero,
                    altura_acople_m,
                    referencia,
                    armado_compatible,
                    coleccion_altura,
                )
            )

    coleccion_bf = nueva_coleccion("02_PICO_BF", coleccion_bovedas)
    for referencia, (altura, longitud) in BOVEDAS_PICO.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_bf)
        for sufijo, altura_acople_m, armado_compatible in ALTURAS_ACOPLE:
            coleccion_altura = nueva_coleccion(sufijo, coleccion_referencia)
            modelos.append(
                crear_boveda(
                    f"{referencia}_{sufijo}",
                    altura,
                    longitud,
                    "pico",
                    acero,
                    altura_acople_m,
                    referencia,
                    armado_compatible,
                    coleccion_altura,
                )
            )

    coleccion_bt = nueva_coleccion("03_TRIANGULO_BT", coleccion_bovedas)
    for referencia, (altura, longitud) in BOVEDAS_TRIANGULO.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_bt)
        for sufijo, altura_acople_m, armado_compatible in ALTURAS_ACOPLE:
            coleccion_altura = nueva_coleccion(sufijo, coleccion_referencia)
            modelos.append(
                crear_boveda(
                    f"{referencia}_{sufijo}",
                    altura,
                    longitud,
                    "triangulo",
                    acero,
                    altura_acople_m,
                    referencia,
                    armado_compatible,
                    coleccion_altura,
                )
            )

    coleccion_atirantadas = nueva_coleccion("07_ATIRANTADAS", catalogo)
    for serie in (45, 90):
        coleccion_serie = nueva_coleccion(f"ATC{serie}", coleccion_atirantadas)
        material = acero_90 if serie == 90 else acero
        for referencia, (longitud, serie_referencia) in SEMICRUCETAS_ATIRANTADAS.items():
            if serie_referencia != serie:
                continue
            coleccion_referencia = nueva_coleccion(referencia, coleccion_serie)
            for sufijo, altura_acople_m, armado_compatible in ALTURAS_ACOPLE:
                coleccion_altura = nueva_coleccion(sufijo, coleccion_referencia)
                modelos.append(
                    crear_semicruceta_atirantada(
                        f"{referencia}_{sufijo}",
                        longitud,
                        serie,
                        material,
                        altura_acople_m,
                        referencia,
                        armado_compatible,
                        coleccion_altura,
                    )
                )

    # Todas comparten origen para facilitar el montaje posterior en Unity.
    # Dejamos una visible para inspección y ocultamos las demás.
    for modelo in modelos:
        modelo.hide_set(True)

    assert len(modelos) == 81, "CATALOGO_ANDEL debe contener exactamente 81 modelos"

    modelos[0].hide_set(False)
    modelos[0].select_set(True)
    bpy.context.view_layer.objects.active = modelos[0]

    # En modo sólido Blender usa gris por defecto; forzamos el color material
    # para que el acabado claro se vea también en la vista de trabajo.
    if bpy.context.screen is not None:
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.color_type = "MATERIAL"

    print(f"Catálogo ANDEL creado correctamente: {len(modelos)} modelos independientes.")


def crear_catalogo_serie_c(material):
    eliminar_catalogo_serie_c_anterior()
    catalogo = nueva_coleccion(
        "CATALOGO_SERIE_C", obtener_raiz_catalogos_crucetas()
    )
    modelos = []

    propiedades_comunes = {
        "serie": "C",
        "normativa": "UNE-EN 207017",
        "altura_acople_m": 0.600,
    }

    coleccion_asc = nueva_coleccion("01_SEMICRUCETAS_ASC", catalogo)
    for referencia, longitud in SERIE_C_SEMICRUCETAS.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_asc)
        propiedades = {
            **propiedades_comunes,
            "referencia_catalogo": referencia,
            "a_m": longitud,
        }
        modelos.append(
            crear_semicruceta_plana(
                f"C_{referencia}",
                longitud,
                material,
                coleccion_referencia,
                propiedades,
            )
        )

    coleccion_arc = nueva_coleccion("02_CRUCETAS_RECTAS_ARC", catalogo)
    for referencia, (longitud, longitud_total) in SERIE_C_CRUCETAS_RECTAS.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_arc)
        propiedades = {
            **propiedades_comunes,
            "referencia_catalogo": referencia,
            "a_m": longitud,
            "longitud_m": longitud_total,
        }
        modelos.append(
            crear_cruceta_recta(
                f"C_{referencia}",
                longitud,
                longitud_total,
                material,
                coleccion_referencia,
                propiedades,
            )
        )

    coleccion_atc = nueva_coleccion("03_ATIRANTADAS_ATC", catalogo)
    for referencia, longitud in SERIE_C_ATIRANTADAS.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_atc)
        propiedades = {
            **propiedades_comunes,
            "familia": "ATC",
            "referencia_catalogo": referencia,
            "a_m": longitud,
        }
        modelos.append(
            crear_semicruceta_atirantada(
                f"C_{referencia}",
                longitud,
                45,
                material,
                0.600,
                referencia,
                "Serie C",
                coleccion_referencia,
                propiedades,
            )
        )

    coleccion_bovedas = nueva_coleccion("04_BOVEDAS", catalogo)
    familias_boveda = (
        (
            "01_TRIANGULO_BT",
            "triangulo",
            SERIE_C_BOVEDAS_TRIANGULO,
        ),
        ("02_CAPA_BH", "capa", SERIE_C_BOVEDAS_CAPA),
        ("03_PICO_BF", "pico", SERIE_C_BOVEDAS_PICO),
    )
    for nombre_familia, forma, referencias in familias_boveda:
        coleccion_familia = nueva_coleccion(nombre_familia, coleccion_bovedas)
        for referencia, (altura_b, d_m, peso_kg) in referencias.items():
            coleccion_referencia = nueva_coleccion(referencia, coleccion_familia)
            propiedades = {
                **propiedades_comunes,
                "referencia_catalogo": referencia,
                "b_m": altura_b,
                "d_m": d_m,
                "longitud_l_m": d_m,
                "peso_kg": peso_kg,
            }
            modelos.append(
                crear_boveda(
                    f"C_{referencia}",
                    altura_b,
                    d_m,
                    forma,
                    material,
                    0.600,
                    referencia,
                    "Serie C",
                    coleccion_referencia,
                    propiedades,
                )
            )

    assert len(modelos) == 24, "La Serie C debe contener exactamente 24 modelos"
    for modelo in modelos:
        modelo.hide_set(True)

    print("Catálogo Serie C creado correctamente: 24 modelos independientes.")


def crear_catalogo_13000(material):
    eliminar_catalogo_13000_anterior()
    catalogo = nueva_coleccion("CATALOGO_13000", obtener_raiz_catalogos_crucetas())
    coleccion_argx = nueva_coleccion("01_CRUCETAS_ARGX", catalogo)
    modelos = []

    for referencia, (semilongitud, longitud_total) in CATALOGO_13000_CRUCETAS.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_argx)
        modelos.append(
            crear_cruceta_recta(
                f"CAT13000_{referencia}",
                semilongitud,
                longitud_total,
                material,
                coleccion_referencia,
                {
                    "catalogo": "13000",
                    "referencia_catalogo": referencia,
                    "tipo": "cruceta_recta",
                    "a_m": semilongitud,
                    "longitud_l_m": longitud_total,
                },
            )
        )

    assert len(modelos) == 4, "CATALOGO_13000 debe contener exactamente 4 modelos"
    for modelo in modelos:
        modelo.hide_set(True)

    print("Catálogo 13000 creado correctamente: 4 modelos independientes.")


def crear_catalogo_presilla(material):
    eliminar_catalogo_presilla_anterior()
    catalogo = nueva_coleccion(
        "CATALOGO_PRESILLA", obtener_raiz_catalogos_crucetas()
    )
    modelos = []

    coleccion_tresbolillo = nueva_coleccion("01_SEMICRUCETAS_TRESBOLILLO", catalogo)
    coleccion_referencia = nueva_coleccion(
        PRESILLA_TRESBOLILLO, coleccion_tresbolillo
    )
    modelos.append(
        crear_semicruceta_tresbolillo_presilla(
            PRESILLA_TRESBOLILLO, material, coleccion_referencia
        )
    )

    coleccion_montaje_0 = nueva_coleccion("02_RECTAS_MONTAJE_0", catalogo)
    for referencia, (longitud, separacion_fases) in PRESILLA_RECTAS_MONTAJE_0.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_montaje_0)
        modelos.append(
            crear_recta_montaje_0_presilla(
                referencia, longitud, separacion_fases, material, coleccion_referencia
            )
        )

    coleccion_arriostradas = nueva_coleccion("03_RECTAS_ARRIOSTRADAS", catalogo)
    for referencia, longitud in PRESILLA_RECTAS_ARRIOSTRADAS.items():
        coleccion_referencia = nueva_coleccion(referencia, coleccion_arriostradas)
        modelos.append(
            crear_recta_arriostrada_presilla(
                referencia, longitud, material, coleccion_referencia
            )
        )

    coleccion_bovedas = nueva_coleccion("04_BOVEDAS_PICO", catalogo)
    for referencia, cabeza_compatible, altura_base in PRESILLA_BOVEDAS_PICO:
        coleccion_referencia = nueva_coleccion(referencia, coleccion_bovedas)
        modelos.append(
            crear_boveda_pico_presilla(
                referencia,
                cabeza_compatible,
                altura_base,
                material,
                coleccion_referencia,
            )
        )

    assert len(modelos) == 14, "CATALOGO_PRESILLA debe contener exactamente 14 modelos"
    for modelo in modelos:
        modelo.hide_set(True)

    print("Catálogo PRESILLA creado correctamente: 14 modelos independientes.")


bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.length_unit = "METERS"
bpy.context.scene.unit_settings.scale_length = 1.0

crear_catalogo()
crear_catalogo_serie_c(bpy.data.materials["Acero_Galvanizado_Andel"])
crear_catalogo_13000(bpy.data.materials["Acero_Galvanizado_Andel"])
crear_catalogo_presilla(bpy.data.materials["Acero_Galvanizado_Andel"])
