# -*- coding: utf-8 -*-
"""
motor_entrada.py
================
Punto de entrada del motor Python del gemelo empaquetado con PyInstaller
(motor.exe). Reenvia cada subcomando al script correspondiente de la carpeta
Datos/, ejecutandolo como si fuera el script principal:

    motor.exe mover_apoyo              --peticion p.json --resultado r.json
    motor.exe modulos_fuste            --peticion p.json --resultado r.json
    motor.exe cambiar_cruceta          --peticion p.json --resultado r.json
    motor.exe cambiar_tipo_apoyo       --peticion p.json [--catalogo]
    motor.exe cambiar_cadena_conductor --peticion p.json | --catalogo_* | --sincronizar
    motor.exe editar_tension           --peticion p.json | --listado
    motor.exe editar_angulo            --peticion p.json | --listado
    motor.exe generar_doc_utm

La carpeta Datos/ se localiza al lado del propio motor.exe (o mediante la
variable de entorno TWINELEC_DATA_DIR). Dentro de ella, los scripts .py conservan
las mismas rutas relativas que en el editor, asi que nada mas cambia.
"""
import json
import os
import runpy
import sys

from twinelec_paths import data_dir

# Consola UTF-8 también dentro del motor empaquetado. Evita que los mensajes
# con ✓, ⚠ o ❌ fallen en equipos Windows configurados con CP-1252.
for _flujo in (sys.stdout, sys.stderr):
    if hasattr(_flujo, "reconfigure"):
        try:
            _flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Datos = carpeta al lado del motor.exe (o variable de entorno)
DATOS = (os.environ.get("TWINELEC_DATA_DIR")
         or os.environ.get("TWINELEC_DATOS") or "")
if not DATOS:
    if getattr(sys, "frozen", False):
        DATOS = os.path.join(os.path.dirname(sys.executable), "Datos")
    else:
        DATOS = str(data_dir())


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error":
            "Uso: motor.exe <subcomando> [argumentos...]"}))
        return 1

    cmd = sys.argv[1]
    ruta = os.path.join(DATOS, cmd + ".py")
    if not os.path.exists(ruta):
        print(json.dumps({"ok": False, "error":
            "Subcomando desconocido: %s" % cmd}))
        return 1

    # Asegurar que la carpeta Datos este en el path (los scripts se importan
    # entre si) y cargar las dependencias estaticas para el ejecutable.
    if DATOS not in sys.path:
        sys.path.insert(0, DATOS)
    os.environ["TWINELEC_DATA_DIR"] = DATOS
    try:
        import motor_deps  # noqa: F401
    except Exception:
        pass

    # Ejecutar el script como si fuera el principal (usa su bloque __main__)
    sys.argv = [cmd + ".py"] + sys.argv[2:]
    runpy.run_path(ruta, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
