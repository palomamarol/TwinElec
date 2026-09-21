# -*- coding: utf-8 -*-
"""
motor_deps.py
=============
Imports ESTATICOS de las dependencias de terceros del motor del gemelo.
Sirve para que PyInstaller detecte y empaquete todas las librerias que los
subcomandos importan en tiempo de ejecucion (runpy), que de otra forma se
perderian en el .exe.
"""
import openpyxl          # noqa: F401  (lectura/escritura de Excel)
import docx              # noqa: F401  (documento UTM en Word)
import PIL               # noqa: F401  (PNG de los graficos)
import numpy             # noqa: F401  (terreno / orografia)
import tifffile          # noqa: F401  (PNOA MDT05)
import imagecodecs       # noqa: F401  (decodifica los PNOA de imagen, compresion JPEG)
import pandas            # noqa: F401  (principal.py - importacion)
import requests          # noqa: F401  (clima.py - APIs AEMET/SiAR)
import shapefile         # noqa: F401  (clima.py - municipios INSPIRE)
