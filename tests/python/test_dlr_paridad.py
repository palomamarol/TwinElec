import json
import math
import unittest
from pathlib import Path

from dlr import calcular_dlr


RUTA_CASOS = (
    Path(__file__).resolve().parents[2]
    / "unity"
    / "Assets"
    / "Tests"
    / "Data"
    / "casos_dlr_paridad.json"
)


def _entrada_dlr(plana):
    return {
        "conductor": {
            "designacion": "caso_paridad",
            "diametro_mm": plana["diametro_mm"],
            "seccion_mm2": plana["seccion_mm2"],
            "r_low_ohm_km": plana["r_low_ohm_km"],
            "r_high_ohm_km": plana["r_high_ohm_km"],
            "t_low_C": plana["t_low_C"],
            "t_high_C": plana["t_high_C"],
            "emisividad": plana["emisividad"],
            "absortividad": plana["absortividad"],
        },
        "meteorologia": {
            "ta_C": plana["ta_C"],
            "vw_m_s": plana["vw_m_s"],
            "direccion_viento_deg": plana["direccion_viento_deg"],
        },
        "geometria": {
            "he_m": plana["he_m"],
            "lat_deg": plana["lat_deg"],
            "zl_deg": plana["zl_deg"],
        },
        "fecha": plana["fecha"],
        "hora_solar": plana["hora_solar"],
        "limite": {"ts_C": plana["ts_C"]},
    }


class ParidadMotorDLRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with RUTA_CASOS.open(encoding="utf-8") as archivo:
            cls.documento = json.load(archivo)

    def test_casos_compartidos_ieee738(self):
        rel = self.documento["tolerancias"]["relativa"]
        abs_ = self.documento["tolerancias"]["absoluta"]

        for caso in self.documento["casos"]:
            with self.subTest(caso=caso["nombre"]):
                entrada = _entrada_dlr(caso["entrada"])
                if caso.get("espera_error", False):
                    with self.assertRaisesRegex(
                        ValueError, caso["error_esperado"]
                    ):
                        calcular_dlr(entrada, modo="ieee738")
                    continue

                resultado = calcular_dlr(entrada, modo="ieee738")
                obtenidos = dict(resultado["intermedios"])
                obtenidos["i_max_A"] = resultado["resultado"]["i_max_A"]

                for magnitud, esperado in caso["esperado"].items():
                    obtenido = obtenidos[magnitud]
                    self.assertTrue(
                        math.isclose(
                            obtenido,
                            esperado,
                            rel_tol=rel,
                            abs_tol=abs_,
                        ),
                        msg=(
                            f"{caso['nombre']} / {magnitud}: "
                            f"esperado={esperado!r}, obtenido={obtenido!r}"
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
