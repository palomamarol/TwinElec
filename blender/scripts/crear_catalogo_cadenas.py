# -*- coding: utf-8 -*-
"""
crear_catalogo_cadenas.py
=========================
Genera el CATALOGO 3D de cadenas de aisladores para Unity: un modelo por
cada LONGITUD distinta que existe en catalogo_cadenas_completo.json
(153 longitudes, de 447 mm a 4403 mm).

Se usa SIEMPRE el mismo croquis de campanas de vidrio; el unico parametro
que cambia entre modelos es la LONGITUD (el numero de campanas se ajusta
automaticamente para mantener el mismo tamano de campana).

Salida:
  unity/Assets/Resources/ModelosCadenas/Cadena_<mm>mm.fbx
  blender/models/biblioteca_cadenas.blend  (todos los modelos, uno al lado
                                           del otro, para disenar/ver)

USO:
  "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe" ^
      --background --python BlenderScripts\\crear_catalogo_cadenas.py
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crear_cadenas_aisladores as gen

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA_CATALOGO_JSON = os.path.join(
    _RAIZ, "data", "catalogs", "catalogo_cadenas_completo.json")
RUTA_BIBLIOTECA = os.path.join(
    _RAIZ, "blender", "models", "biblioteca_cadenas.blend")

SEPARACION_BIBLIOTECA_M = 0.25  # distancia entre modelos en la biblioteca


def longitudes_del_catalogo():
    """Longitudes distintas (m) presentes en el catalogo de cadenas."""
    with open(RUTA_CATALOGO_JSON, encoding="utf-8") as archivo:
        catalogo = json.load(archivo)
    longitudes = {
        round(float(c["caracteristicas"]["longitud_m"]), 3)
        for c in catalogo.get("cadenas", [])
        if c.get("caracteristicas", {}).get("longitud_m") is not None
    }
    return sorted(longitudes)


def generar_catalogo():
    longitudes = longitudes_del_catalogo()
    if not longitudes:
        raise RuntimeError("No se encontraron longitudes en %s" % RUTA_CATALOGO_JSON)
    print("Longitudes del catalogo: %d (de %d mm a %d mm)"
          % (len(longitudes), round(longitudes[0] * 1000),
             round(longitudes[-1] * 1000)))

    gen.limpiar_escena()
    generadas = 0
    for i, longitud in enumerate(longitudes):
        objeto = gen.crear_cadena(longitud, tipo="VID", n_aisladores=None,
                                  radio_disco=0.05, unir=True)
        nombre = "Cadena_%dmm" % round(longitud * 1000)
        gen.exportar_objeto_como_fbx(objeto, nombre)
        # Separar los modelos en la biblioteca .blend para poder verlos todos
        objeto.location = (i * SEPARACION_BIBLIOTECA_M, 0.0, 0.0)
        generadas += 1

    bpy.ops.wm.save_as_mainfile(filepath=RUTA_BIBLIOTECA)
    print("OK: %d modelos generados." % generadas)
    print("Biblioteca .blend:", RUTA_BIBLIOTECA)


if __name__ == "__main__":
    generar_catalogo()
