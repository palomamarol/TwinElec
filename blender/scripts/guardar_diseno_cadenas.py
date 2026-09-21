# -*- coding: utf-8 -*-
"""
guardar_diseno_cadenas.py
=========================
Genera las cadenas de CADENAS_A_GENERAR con las PIEZAS SEPARADAS (cada
campana, herraje y grapa como objeto propio) y guarda el proyecto .blend
en blender/models/ para poder seguir disenandolas a mano en Blender.

USO:
    "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe" ^
        --background --python BlenderScripts\\guardar_diseno_cadenas.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crear_cadenas_aisladores as gen

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARPETA_DISENO = os.path.join(_RAIZ, "blender", "models")


def guardar_disenos():
    os.makedirs(CARPETA_DISENO, exist_ok=True)
    gen.limpiar_escena()
    for configuracion in gen.CADENAS_A_GENERAR:
        piezas = gen.crear_cadena(
            configuracion.get("longitud_m", 0.45),
            tipo=configuracion.get("tipo", "VID"),
            n_aisladores=configuracion.get("n_aisladores", 3),
            radio_disco=configuracion.get("radio_disco", 0.05),
            unir=False)
        print("Piezas de %s: %d" % (configuracion["nombre"], len(piezas)))

    ruta_blend = os.path.join(CARPETA_DISENO,
                              gen.CADENAS_A_GENERAR[0]["nombre"] + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=ruta_blend)
    print("Diseno guardado en:", ruta_blend)


if __name__ == "__main__":
    guardar_disenos()
