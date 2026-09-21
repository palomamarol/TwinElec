import json
import os
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import clima


class EntradasMeteorologicasAemetTests(unittest.TestCase):
    def test_publicacion_json_atomica_deja_documento_completo(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = os.path.join(directorio, "meteorologia.json")
            documento = {"version_esquema": 3, "meteorologia": {"ta_C": 21.5}}

            clima._publicar_json_atomico(ruta, documento)

            with open(ruta, encoding="utf-8") as f:
                self.assertEqual(json.load(f), documento)
            self.assertEqual(os.listdir(directorio), ["meteorologia.json"])

    def test_observacion_prioriza_ta_frente_a_tamax(self):
        registro = {"ta": 21.5, "tamax": 34.0}

        self.assertEqual(clima._temperatura_aire_aemet(registro), 21.5)

    def test_observacion_usa_tamax_solo_si_falta_ta(self):
        registro = {"tamax": 34.0}

        self.assertEqual(clima._temperatura_aire_aemet(registro), 34.0)

    def test_aemet_convierte_fint_utc_a_hora_local_madrid(self):
        """AEMET publica fint en UTC; debe guardarse convertido a Europe/Madrid."""
        class _Resp:
            status_code = 200

            def __init__(self, datos):
                self._datos = datos

            def json(self):
                return self._datos

        observaciones = [{
            "fint": "2026-08-14T11:00:00+0000",
            "ta": "35.6",
            "vv": "1.1",
            "dv": "120",
        }]
        respuestas = {
            "Observaci": _Resp({"datos": "http://datos"}),
            "Descarga": _Resp(observaciones),
        }
        original = clima._get_api_seguro
        original_key = clima.API_KEY_AEMET

        def fake(url, contexto="", **kwargs):
            for clave, resp in respuestas.items():
                if clave in contexto:
                    return resp
            raise AssertionError(f"contexto inesperado: {contexto}")

        clima._get_api_seguro = fake
        clima.API_KEY_AEMET = "test-placeholder-not-a-real-key"
        try:
            resultado = clima.consultar_aemet("TEST")
        finally:
            clima._get_api_seguro = original
            clima.API_KEY_AEMET = original_key

        self.assertEqual(resultado["fecha"], "2026/08/14")
        self.assertEqual(resultado["hora_local"], "13:00")
        self.assertEqual(resultado["fecha_observacion"], "2026-08-14T13:00+02:00")

    def test_convierte_km_h_a_m_s(self):
        self.assertAlmostEqual(clima._km_h_a_m_s(36.0), 10.0)

    def test_prediccion_entrega_viento_en_m_s_al_motor(self):
        prediccion = [{
            "prediccion": {
                "dia": [{
                    "fecha": "2026-08-13T00:00:00",
                    "temperatura": [{"periodo": "12", "value": 30}],
                    "vientoAndRachaMax": [{
                        "periodo": "12",
                        "velocidad": [36],
                        "direccion": ["O"],
                    }],
                }],
            },
        }]
        conductor = {
            "designacion": "prueba",
            "diametro_mm": 9.45,
            "seccion_mm2": 54.6,
            "r_low_ohm_km": 0.6101,
            "r_high_ohm_km": 0.6106,
            "t_low_C": 25.0,
            "t_high_C": 70.0,
            "t_limite_C": 50.0,
        }
        geometria = {
            "lat_deg": 38.05,
            "lon_deg": -3.47,
            "he_m": 555.0,
            "zl_deg": 185.0,
        }

        franjas = clima.procesar_prediccion(
            prediccion,
            geometria,
            conductor=conductor,
        )

        self.assertEqual(len(franjas), 1)
        self.assertAlmostEqual(franjas[0]["vw_m_s"], 10.0)
        self.assertEqual(franjas[0]["direccion_viento_deg"], 270)
        self.assertIsNotNone(franjas[0]["i_max_A"])

    def test_hora_solar_aparente_demo_verano(self):
        hora = clima.hora_solar_aparente(
            "2026-08-05", "21:00", -3.0
        )

        self.assertAlmostEqual(hora, 18.7, delta=0.15)

    def test_configuracion_deriva_geometria_y_limite_comunes(self):
        apoyos = [
            {"x": 500000.00, "y": 4200000.00, "cota": 560.56},
            {"x": 499999.00, "y": 4199990.00, "cota": 560.00},
            {"x": 499979.00, "y": 4199903.00, "cota": 556.57},
            {"x": 499929.00, "y": 4199772.00, "cota": 542.97},
        ]

        cfg = clima.configuracion_dlr_linea(
            apoyos, conductor={"t_limite_C": 50.0}
        )

        self.assertAlmostEqual(cfg["zl_deg"], 185.7106, places=3)
        self.assertAlmostEqual(cfg["lat_deg"], 37.9468, places=3)
        self.assertAlmostEqual(cfg["lon_deg"], -3.0003, places=3)
        self.assertAlmostEqual(cfg["he_m"], 555.025, places=3)
        self.assertEqual(cfg["ts_limite_C"], 50.0)

    def test_calidad_ok_para_observacion_reciente(self):
        ahora = datetime(2026, 8, 13, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        calidad = clima.evaluar_calidad_meteorologica(
            {"fecha_observacion": "2026-08-13T11:00+02:00"}, ahora=ahora
        )

        self.assertEqual(calidad["estado"], "OK")
        self.assertTrue(calidad["datos_validos"])
        self.assertEqual(calidad["antiguedad_min"], 60.0)

    def test_calidad_obsoleta_para_observacion_antigua(self):
        ahora = datetime(2026, 8, 13, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        calidad = clima.evaluar_calidad_meteorologica(
            {"fecha_observacion": "2026-08-13T08:00+02:00"},
            ahora=ahora,
            max_antiguedad_min=180,
        )

        self.assertEqual(calidad["estado"], "OBSOLETO")
        self.assertFalse(calidad["datos_validos"])

    def test_calidad_fallback_nunca_es_operativa(self):
        calidad = clima.evaluar_calidad_meteorologica(
            {"fecha_observacion": "2026-08-13T11:00+02:00"},
            estado_api="FALLBACK",
        )

        self.assertEqual(calidad["estado"], "FALLBACK")
        self.assertFalse(calidad["datos_validos"])
        self.assertTrue(calidad["es_fallback"])

    def test_calidad_error_si_falta_fecha_observacion(self):
        calidad = clima.evaluar_calidad_meteorologica({}, estado_api="ERROR")

        self.assertEqual(calidad["estado"], "ERROR")
        self.assertFalse(calidad["datos_validos"])

    def test_fallback_municipal_no_es_limite_operativo(self):
        apoyos = [
            {"id": "1", "x": 500000.00, "y": 4200000.00, "cota": 560.56},
            {"id": "2", "x": 499999.00, "y": 4199990.00, "cota": 560.00},
        ]
        conductor = {
            "diametro_mm": 9.45,
            "seccion_mm2": 54.6,
            "r_low_ohm_km": 0.6101,
            "r_high_ohm_km": 0.6106,
            "t_low_C": 25.0,
            "t_high_C": 70.0,
            "t_limite_C": 50.0,
        }
        cfg = clima.configuracion_dlr_linea(apoyos, conductor=conductor)

        originales = (
            clima.agrupar_por_municipios,
            clima._cargar_conductor_configurado,
            clima.estacion_mas_cercana,
            clima.consultar_aemet,
            clima._cargar_cache_ultima_valida,
        )
        try:
            clima.agrupar_por_municipios = lambda _: [{
                "codigo_ine": "00000",
                "nombre": "Demo",
                "natcode": "demo",
                "apoyos": apoyos,
                "lat_media": cfg["lat_deg"],
                "lon_media": cfg["lon_deg"],
                "he_m": cfg["he_m"],
            }]
            clima._cargar_conductor_configurado = lambda: conductor
            clima.estacion_mas_cercana = lambda *_: ({
                "nombre": "AEMET_PRUEBA",
                "tipo": "AEMET",
                "id": "X",
                "altitud": 0,
            }, 1.0)
            clima.consultar_aemet = lambda _: None
            clima._cargar_cache_ultima_valida = lambda *_: (None, None)

            grupos, limite, _ = clima.calcular_capacidad_municipios(apoyos, cfg)
        finally:
            (
                clima.agrupar_por_municipios,
                clima._cargar_conductor_configurado,
                clima.estacion_mas_cercana,
                clima.consultar_aemet,
                clima._cargar_cache_ultima_valida,
            ) = originales

        self.assertEqual(grupos[0]["calidad"]["estado"], "FALLBACK")
        self.assertFalse(grupos[0]["calidad"]["datos_validos"])
        self.assertIsNone(limite)

    def test_limite_municipios_reproducible_con_motor(self):
        """El limite agregado (min de municipios) debe reproducirse con calcular_dlr."""
        ahora = datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="minutes")
        apoyos = [
            {"id": "1", "x": 500000.00, "y": 4200000.00, "cota": 560.56},
            {"id": "2", "x": 499999.00, "y": 4199990.00, "cota": 560.00},
        ]
        conductor = {
            "designacion": "47-AL1/8-ST1A",
            "diametro_mm": 9.45,
            "seccion_mm2": 54.6,
            "composicion": "6+1",
            "r_low_ohm_km": 0.6101,
            "r_high_ohm_km": 0.6106,
            "t_low_C": 25.0,
            "t_high_C": 70.0,
            "t_limite_C": 50.0,
            "emisividad": 0.8,
            "absortividad": 0.8,
        }
        configuracion = {"zl_deg": 185.7106, "ts_limite_C": 50.0}
        grupos = [{
            "codigo_ine": "00000",
            "nombre": "Demo",
            "natcode": "demo",
            "apoyos": apoyos,
            "lat_media": 37.9468,
            "lon_media": -3.0003,
            "he_m": 555.0,
        }]
        estacion = {
            "nombre": "AEMET_TEST", "tipo": "AEMET",
            "id": "TEST", "altitud": 771,
        }
        meteorologia = {
            "ta_C": 30.0,
            "vw_m_s": 2.0,
            "direccion_viento_deg": 90.0,
            "fecha": ahora[:10].replace("-", "/"),
            "hora_local": ahora[11:16],
            "fecha_observacion": ahora,
        }

        originales = (
            clima.agrupar_por_municipios,
            clima._cargar_conductor_configurado,
            clima.estacion_mas_cercana,
            clima.consultar_aemet,
            clima._guardar_cache_ultima_valida,
        )
        try:
            clima.agrupar_por_municipios = lambda _: grupos
            clima._cargar_conductor_configurado = lambda: conductor
            clima.estacion_mas_cercana = lambda *_a: (estacion, 6.2)
            clima.consultar_aemet = lambda _id: meteorologia
            clima._guardar_cache_ultima_valida = lambda *_a: None

            grupos_res, limite, _ = clima.calcular_capacidad_municipios(
                apoyos, configuracion
            )
        finally:
            (
                clima.agrupar_por_municipios,
                clima._cargar_conductor_configurado,
                clima.estacion_mas_cercana,
                clima.consultar_aemet,
                clima._guardar_cache_ultima_valida,
            ) = originales

        # Recalculo independiente con el motor usando exactamente los mismos
        # datos que el pipeline utilizo para ese municipio.
        entradas = {
            "conductor": {
                "designacion": conductor["designacion"],
                "diametro_mm": conductor["diametro_mm"],
                "seccion_mm2": conductor["seccion_mm2"],
                "composicion": conductor["composicion"],
                "r_low_ohm_km": conductor["r_low_ohm_km"],
                "r_high_ohm_km": conductor["r_high_ohm_km"],
                "t_low_C": conductor["t_low_C"],
                "t_high_C": conductor["t_high_C"],
                "emisividad": conductor["emisividad"],
                "absortividad": conductor["absortividad"],
            },
            "meteorologia": {
                "ta_C": meteorologia["ta_C"],
                "vw_m_s": meteorologia["vw_m_s"],
                "direccion_viento_deg": meteorologia["direccion_viento_deg"],
            },
            "geometria": {
                "he_m": grupos[0]["he_m"],
                "lat_deg": grupos[0]["lat_media"],
                "zl_deg": configuracion["zl_deg"],
            },
            "fecha": meteorologia["fecha"].replace("/", "-"),
            "hora_solar": clima.hora_solar_aparente(
                meteorologia["fecha"],
                meteorologia["hora_local"],
                grupos[0]["lon_media"],
            ),
            "limite": {"ts_C": configuracion["ts_limite_C"]},
        }
        esperado = round(
            clima.dlr.calcular_dlr(entradas, modo="ieee738")["resultado"]["i_max_A"], 2
        )

        self.assertEqual(grupos_res[0]["calidad"]["estado"], "OK")
        self.assertTrue(grupos_res[0]["calidad"]["datos_validos"])
        self.assertEqual(grupos_res[0]["i_max_A"], esperado)
        self.assertEqual(limite, esperado)


if __name__ == "__main__":
    unittest.main()
