# -*- coding: utf-8 -*-
"""
empacar_motor.py
================
Empaqueta el motor Python del gemelo en un unico 'motor.exe' con PyInstaller,
de modo que el .exe de Unity NO necesite Python instalado en la maquina final.

Uso:
    py -3 empacar_motor.py

Resultado: motor_dist/motor.exe  (copialo a la carpeta del build de Unity,
junto a la carpeta Datos/).

Requiere:  pip install pyinstaller
"""
import os
import shutil
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR = os.path.dirname(TOOLS_DIR)
REPOSITORY_ROOT = os.path.dirname(os.path.dirname(PYTHON_DIR))


def main():
    # Detecta PyInstaller como MODULO del mismo Python que ejecuta este
    # script (no depende de que el ejecutable 'pyinstaller.exe' este en el
    # PATH, que suele instalarse en la carpeta Scripts del Python).
    import importlib.util
    if importlib.util.find_spec("PyInstaller") is None:
        print("No se encontro PyInstaller en este Python (" + sys.executable + ").")
        print("Instalalo con:")
        print("    py -3 -m pip install pyinstaller")
        return 1

    dist = os.path.join(REPOSITORY_ROOT, "release", "TwinElec")
    work = os.path.join(REPOSITORY_ROOT, "release", ".motor_build")
    os.makedirs(dist, exist_ok=True)
    os.makedirs(work, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "motor",
        "--paths", PYTHON_DIR,
        "--distpath", dist,
        "--workpath", work,
        "--specpath", work,
        "--clean",
        "--noconfirm",
        # Red de seguridad por si PyInstaller no sigue algun import dinamico
        "--hidden-import", "openpyxl",
        "--hidden-import", "docx",
        "--hidden-import", "PIL",
        "--hidden-import", "numpy",
        "--hidden-import", "tifffile",
        "--hidden-import", "imagecodecs",
        "--hidden-import", "pandas",
        os.path.join(PYTHON_DIR, "motor_entrada.py"),
    ]
    print("Ejecutando PyInstaller (puede tardar unos minutos)...")
    subprocess.check_call(cmd)

    salida = os.path.join(dist, "motor.exe")
    if os.path.exists(salida):
        print("\nOK: " + salida)
        print("Pasos siguientes:")
        print("  1) Copia 'motor.exe' a la carpeta donde estara TwinElec.exe.")
        print("  2) Asegurate de que la carpeta 'Datos/' este al lado "
              "(generala con preparar_datos_exportable.py).")
        print("  3) Compila el .exe de Unity (File > Build Settings) con "
              "salida en esa misma carpeta.")
    else:
        print("Fallo la generacion de motor.exe (revisa la salida de "
              "PyInstaller).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
