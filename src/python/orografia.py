# -*- coding: utf-8 -*-
"""
orografia.py
============
Lee el relieve PNOA (MDT05 LIDAR, GeoTIFF) para la funcion de "mover apoyo":

  - extension(): limites UTM de los PNOA disponibles (para avisar si un
    punto se sale del terreno).
  - cota_en(x, y): elevacion (cota) en un punto UTM (muestreo vecino mas
    proximo, mismo metodo que principal.py).
  - dentro_de_pnoa(x, y): True si el punto cae dentro de la extension.
  - buscar_x_para_cota(y, z): devuelve la X tal que la cota en (x, y) ~ z
    (movimiento con grados X-Z, la Y queda fija).
  - buscar_y_para_cota(x, z): devuelve la Y tal que la cota en (x, y) ~ z
    (movimiento con grados Y-Z, la X queda fija).

GENERAL: funciona para cualquier linea cuyos PNOA_MDT05*.tif esten en la
carpeta del proyecto (o en 'carpeta').
"""
import glob
import os

import numpy as np
import tifffile as tiff

from twinelec_paths import data_dir

RES_MDT = 5.0  # resolucion del MDT05 (metros por pixel)


class Orografia:
    """Acceso al mosaico PNOA MDT05: extension, cota_en y busquedas inversas."""

    def __init__(self, carpeta=None):
        self.carpeta = carpeta or str(data_dir())
        self._tiles = []
        self._extension = None
        self._cargar()

    # ------------------------------------------------------------------
    def _cargar(self):
        archivos = sorted(glob.glob(os.path.join(self.carpeta, "PNOA_MDT05*.tif")))
        if not archivos:
            raise FileNotFoundError(
                "No hay archivos PNOA_MDT05*.tif en '%s'." % self.carpeta)
        for ruta in archivos:
            try:
                with tiff.TiffFile(ruta) as tif:
                    tags = tif.pages[0].tags
                    origin_x = float(tags[33922].value[3])   # ModelTiepoint -> X
                    origin_y = float(tags[33922].value[4])   # ModelTiepoint -> Y
                    arr = np.asarray(tif.asarray(), dtype=np.float32)
                    alto, ancho = arr.shape
                    max_x = origin_x + ancho * RES_MDT
                    min_y = origin_y - alto * RES_MDT
                    self._tiles.append({
                        "ruta": ruta, "origin_x": origin_x, "origin_y": origin_y,
                        "max_x": max_x, "min_y": min_y, "arr": arr,
                    })
            except Exception as e:
                print("  [orografia] aviso: no se pudo leer %s (%s)" % (ruta, e))
        if not self._tiles:
            raise FileNotFoundError(
                "No se pudo leer ningun PNOA_MDT05*.tif en '%s'." % self.carpeta)
        min_x = min(t["origin_x"] for t in self._tiles)
        max_x = max(t["max_x"] for t in self._tiles)
        min_y = min(t["min_y"] for t in self._tiles)
        max_y = max(t["origin_y"] for t in self._tiles)
        self._extension = (min_x, min_y, max_x, max_y)

    # ------------------------------------------------------------------
    @property
    def extension(self):
        """(min_x, min_y, max_x, max_y) en UTM."""
        return self._extension

    def dentro_de_pnoa(self, x, y, margen=0.0):
        min_x, min_y, max_x, max_y = self._extension
        return (min_x - margen <= x <= max_x + margen
                and min_y - margen <= y <= max_y + margen)

    def cota_en(self, x, y):
        """Cota (m) en el punto UTM (x, y). Devuelve None si el punto cae
        fuera de los tiles o en un hueco sin dato (valor 0)."""
        for t in self._tiles:
            if not (t["origin_x"] <= x <= t["max_x"]
                    and t["min_y"] <= y <= t["origin_y"]):
                continue
            col = int(round((x - t["origin_x"]) / RES_MDT))
            row = int(round((t["origin_y"] - y) / RES_MDT))
            if 0 <= row < t["arr"].shape[0] and 0 <= col < t["arr"].shape[1]:
                valor = float(t["arr"][row, col])
                if valor != 0.0:
                    return valor
        return None

    # ------------------------------------------------------------------
    def buscar_x_para_cota(self, y, z, x_actual=None):
        """Devuelve la X (este) del pixel de la fila 'y' cuya cota esta mas
        cerca de 'z'. Si 'x_actual' se da, se elige el mas cercano dentro de
        una banda de 500 m. Devuelve None si no hay candidato util."""
        mejor = None
        mejor_dif = float("inf")
        banda = 500.0 if x_actual is not None else None
        for t in self._tiles:
            if not (t["min_y"] <= y <= t["origin_y"]):
                continue
            row = int(round((t["origin_y"] - y) / RES_MDT))
            if not (0 <= row < t["arr"].shape[0]):
                continue
            fila = t["arr"][row, :]
            for col, valor in enumerate(fila):
                if valor == 0.0:
                    continue
                x_cand = t["origin_x"] + col * RES_MDT
                if banda is not None and abs(x_cand - x_actual) > banda:
                    continue
                dif = abs(float(valor) - z)
                if dif < mejor_dif:
                    mejor_dif = dif
                    mejor = x_cand
        return mejor

    def buscar_y_para_cota(self, x, z, y_actual=None):
        """Devuelve la Y (norte) del pixel de la columna 'x' cuya cota esta
        mas cerca de 'z'. Si 'y_actual' se da, se elige el mas cercano dentro
        de una banda de 500 m. Devuelve None si no hay candidato util."""
        mejor = None
        mejor_dif = float("inf")
        banda = 500.0 if y_actual is not None else None
        for t in self._tiles:
            if not (t["origin_x"] <= x <= t["max_x"]):
                continue
            col = int(round((x - t["origin_x"]) / RES_MDT))
            if not (0 <= col < t["arr"].shape[1]):
                continue
            for row in range(t["arr"].shape[0]):
                valor = float(t["arr"][row, col])
                if valor == 0.0:
                    continue
                y_cand = t["origin_y"] - row * RES_MDT
                if banda is not None and abs(y_cand - y_actual) > banda:
                    continue
                dif = abs(valor - z)
                if dif < mejor_dif:
                    mejor_dif = dif
                    mejor = y_cand
        return mejor


# ---------------------------------------------------------------------------
# Instancia unica (se carga una vez; los PNOA son pesados)
# ---------------------------------------------------------------------------
_OROGRAFIA = None


def orografia(carpeta=None):
    global _OROGRAFIA
    if _OROGRAFIA is None:
        _OROGRAFIA = Orografia(carpeta)
    return _OROGRAFIA


if __name__ == "__main__":
    o = orografia()
    print("Extension PNOA (UTM):", o.extension)
    for px, py in [(499999.0, 4199990.0), (499979.0, 4199903.0)]:
        print("  cota_en(%s, %s) = %s" % (px, py, o.cota_en(px, py)))
    print("  dentro (500000, 4200000):", o.dentro_de_pnoa(500000, 4200000))
    print("  dentro (100000, 100000):", o.dentro_de_pnoa(100000, 100000))
    x_inv = o.buscar_x_para_cota(4199903.0, 558.0)
    print("  buscar_x_para_cota(y=4199903, z=558) ->", x_inv,
          "| cota real:", (o.cota_en(x_inv, 4199903.0) if x_inv else None))
    y_inv = o.buscar_y_para_cota(499979.0, 558.0)
    print("  buscar_y_para_cota(x=499979, z=558) ->", y_inv,
          "| cota real:", (o.cota_en(499979.0, y_inv) if y_inv else None))
