# -*- coding: utf-8 -*-
"""
graficos_utilizacion_ecuaciones.py
==================================
Base de datos de ecuaciones del Tema 10
"Graficos de utilizacion de apoyos y crucetas" (Instalaciones Electricas de
Alta Tension - U. Jaen - Fco. J. Sanchez Sutil).

Este modulo SOLO ALMACENA las ecuaciones tal y como aparecen en las tablas del
Tema 10, organizadas por caso (tipo de apoyo x zona/categoria). En esta fase no
se resuelven: quedan documentadas e indexadas para que el resto del codigo
(motor de calculo, exportador JSON, Unity, ...) pueda pedir el conjunto de
ecuaciones que le corresponde a cada apoyo.

USO:
    from graficos_utilizacion_ecuaciones import obtener_ecuaciones
    caso = obtener_ecuaciones("alineacion_suspension", zona="A")
    print(caso["hipotesis"]["1a"]["T"]["ecuacion"])
    print(caso["rectas"]["1a"])

CLAVES DE CASO (tipo_apoyo):
    "alineacion_suspension", "alineacion_amarre", "alineacion_anclaje",
    "angulo_suspension", "angulo_amarre", "angulo_anclaje",
    "principio_final_de_linea"

CLAVES DE ZONA:
    "A"                  -> zona A
    "BC_no_especial"     -> zonas B y C, lineas de categoria no especial
    "BC_especial"        -> zonas B y C, lineas de categoria especial
"""

# ---------------------------------------------------------------------------
# 2. PORCENTAJES DE DESEQUILIBRIO DE TRACCIONES (3a hipotesis) por tipo de apoyo
#    Segun el Tema 10:
#      - "<=66 kV": lineas de tension menor o igual que 66 kV
#      - ">66 kV":  lineas de tension superior a 66 kV
#      - Principio-final de linea no tiene 3a hipotesis: el desequilibrio (100%)
#        va incorporado en las hipotesis 1a y 2a.
# ---------------------------------------------------------------------------
PORCENTAJES_DESEQUILIBRIO = {
    "alineacion_suspension":    {"<=66 kV": 0.08, ">66 kV": 0.15},
    "alineacion_amarre":        {"<=66 kV": 0.15, ">66 kV": 0.25},
    "alineacion_anclaje":       {"<=66 kV": 0.50, ">66 kV": 0.50},
    "angulo_suspension":        {"<=66 kV": 0.08, ">66 kV": 0.15},
    "angulo_amarre":            {"<=66 kV": 0.15, ">66 kV": 0.25},
    "angulo_anclaje":           {"<=66 kV": 0.50, ">66 kV": 0.50},
    "principio_final_de_linea": {"<=66 kV": 1.00, ">66 kV": 1.00},  # no hay 3a hipotesis
}


# ---------------------------------------------------------------------------
# 1. GLOSARIO DE VARIABLES (paginas 74-76 del Tema 10)
#    Referencia unica de nombres para que todas las ecuaciones compartan
#    la misma notacion y en la fase siguiente se pueda enlazar cada variable
#    con su valor real procedente del Excel.
# ---------------------------------------------------------------------------
VARIABLES = {
    # --- Parametros del grafico (ejes y familias de curvas) ---
    "L":        "Parametro de longitud del vano (semisuma de vanos, eje X) [m]",
    "N":        "Parametro de diferencia de tangentes (eje Y): tan(n1)-tan(n2) [-]",
    "S":        "Parametro de angulo (solo apoyos de angulo): S = 2*cos(alfa/2) [-]",
    "a1":       "Vano anterior al apoyo [m]",
    "a2":       "Vano posterior al apoyo [m]",
    "n1":       "Pendiente del vano anterior al apoyo [-]",
    "n2":       "Pendiente del vano posterior al apoyo [-]",
    "h1":       "Desnivel del vano anterior al apoyo [m]",
    "h2":       "Desnivel del vano posterior al apoyo [m]",
    "alfa":     "Angulo interno de la linea (grados sexagesimales) [grad]",
    "beta":     "Referencia de alineacion para apoyos de angulo (en los ejemplos del Tema 10 beta=180 grad) [grad]",

    # --- Ecuacion resistente del apoyo ---
    "Fu":       "Esfuerzo util del apoyo [daN]",
    "h_":       "Altura del punto de aplicacion del esfuerzo util [m]",
    "F":        "Esfuerzo de calculo del apoyo [daN]",
    "h":        "Altura del punto de aplicacion de esfuerzos [m]",
    "d1":       "Distancia entre montantes en el punto de fallo [m]",
    "P":        "Cargas verticales sobre el apoyo [daN]",

    # --- Conductor ---
    "pF":       "Peso del conductor de fase [daN/m]",
    "pCond":    "Peso del conductor [daN/m]",
    "dF":       "Diametro del conductor de fase [m]",
    "d":        "Diametro del conductor [m]",
    "vF":       "Presion del viento sobre el conductor de fase [daN/m2]",
    "v":        "Presion del viento a 120 km/h [daN/m2]",
    "vF60":     "Presion del viento a 60 km/h [daN/m2]",
    "T0F":      "Componente horizontal maxima del conductor de fase [daN]",
    "TVF":      "Tension maxima de viento del conductor de fase [daN]",
    "THF":      "Tension maxima de hielo del conductor de fase [daN]",
    "TVHF":     "Tension de viento mas hielo del conductor de fase [daN]",
    "TVM":      "Tension en condiciones de la mitad de la presion del viento [daN]",
    "TTemp":    "Tension en la hipotesis de temperatura [daN]",
    "T0H":      "Tension a 0 grados C mas hielo [daN]",
    "SHF":      "Sobrecarga debida al hielo del conductor de fase [daN/m]",
    "SV":       "Sobrecarga debida al viento [daN/m]",
    "SVH":      "Sobrecarga debida al viento mas hielo [daN/m]",
    "CVF":      "Constante de catenaria en condiciones de viento maximo para conductor de fase [daN/m]",
    "CVHF":     "Constante de catenaria de viento mas hielo para el conductor de fase [daN/m]",
    "cVM":      "Constante de catenaria con la mitad de la presion del viento [daN/m]",
    "dMHF":     "Diametro del manguito de hielo del conductor de fase [m]",
    "SV2":      "Sobrecarga debida a la mitad de la presion del viento [daN/m]",

    # --- Cadena de aisladores ---
    "PCADF":    "Peso de la cadena de aisladores de fase [daN]",
    "NCAD":     "Numero de cadenas (una por conductor de fase) [-]",
    "EVCADF":   "Esfuerzo del viento sobre las cadenas del conductor de fase [daN]",
    "EVCADF60": "Esfuerzo del viento a 60 km/h sobre las cadenas del conductor de fase [daN]",
    "EVCad":    "Esfuerzo del viento sobre la cadena de aisladores [daN]",
    "PCad":     "Peso de la cadena de aisladores [daN]",
    "LCad":     "Longitud de la cadena de aisladores [m]",
    "gammamax": "Angulo maximo de desviacion de la cadena de aisladores [grad]",

    # --- Vano maximo por separacion de conductores ---
    "D":        "Distancia o separacion entre conductores [m]",
    "K":        "Coeficiente que depende del angulo de oscilacion del viento [-]",
    "K_":       "Coeficiente que depende de la tension nominal de la linea [-]",
    "DPP":      "Distancia minima aerea especificada para prevenir descarga disruptiva [m]",
    "fmx":      "Flecha maxima [m]",

    # --- Crucetas ---
    "PAdmCru":  "Peso vertical maximo admisible en cruceta [daN]",
    "PHombre":  "Peso del operario (80 daN) [daN]",

    # --- Porcentajes ---
    "pctP":     "Porcentaje de desequilibrio de tracciones de la 3a hipotesis [-]",

    # --- Variantes por vano (anterior/posterior) ---
    "CVF1":     "Constante de catenaria de viento del conductor de fase en el vano anterior [daN/m]",
    "CVF2":     "Constante de catenaria de viento del conductor de fase en el vano posterior [daN/m]",
    "THF1":     "Tension maxima de hielo en el vano anterior al apoyo [daN]",
    "THF2":     "Tension maxima de hielo en el vano posterior al apoyo [daN]",
    "CVHF1":    "Constante de catenaria de viento mas hielo en el vano anterior [daN/m]",
    "CVHF2":    "Constante de catenaria de viento mas hielo en el vano posterior [daN/m]",
    "TVF1":     "Tension maxima de viento en el vano anterior al apoyo [daN]",
    "TVF2":     "Tension maxima de viento en el vano posterior al apoyo [daN]",
    "TVHF1":    "Tension maxima de viento mas hielo en el vano anterior al apoyo [daN]",
    "TVHF2":    "Tension maxima de viento mas hielo en el vano posterior al apoyo [daN]",
    "T0F1":     "Componente horizontal maxima en el vano anterior al apoyo [daN]",
    "T0F2":     "Componente horizontal maxima en el vano posterior al apoyo [daN]",
    "dMF":      "Diametro del manguito de hielo del conductor de fase (variante usada en las rectas V+H) [m]",
    "p":        "Peso del conductor (notacion sin subindice usada en desviacion de cadena) [daN/m]",
    "SH":       "Sobrecarga de hielo (notacion sin subindice usada en vano maximo) [daN/m]",
}


# ---------------------------------------------------------------------------
# 3. CASOS DEL TEMA 10
#    Cada caso (tipo de apoyo x zona) contiene:
#      - "hipotesis": ecuaciones de los esfuerzos V, T, L de cada hipotesis
#                     reglamentaria, tal y como vienen en las tablas.
#      - "rectas":    las rectas resultantes de aplicar la ecuacion resistente
#                     Fu*h'/(2*d1) = F*h/(2*d1) + P/4  y reagrupar en L y N.
#      - "auxiliares": vano maximo, desviacion de cadena y cruceta.
#    Formato de cada ecuacion:
#      {"ecuacion": "texto legible", "variables": ["var1", ...], "notas": "..."}
# ---------------------------------------------------------------------------

CASOS = {
    # =====================================================================
    # 2.- APOYO DE ALINEACION-SUSPENSION (Tema 10, pag. 5)
    # =====================================================================
    "alineacion_suspension": {
        "nombre": "Apoyo de alineacion-suspension",
        "desviacion_cadena": True,
        "usa_parametro_S": False,
        "porcentajes_desequilibrio": PORCENTAJES_DESEQUILIBRIO["alineacion_suspension"],
        "zonas": {
            # -------------------------------------------------------------
            # 2.1.- Zona A (pag. 5-6)
            # -------------------------------------------------------------
            "A": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "L = %P*T0F   (8% para lineas de tension <= 66 kV, 15% para > 66 kV)",
                                "variables": ["pctP", "T0F"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*T0F*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "T0F", "h",
                                      "pF", "L", "CVF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
                        "variables": ["fmx", "TTemp", "pCond"],
                    },
                    "desviacion_cadena": {
                        "ecuacion": ("tan(gammamax) = [v/2*d*L + EVCad/2]"
                                     " / [p*L + TVM*N + PCad/2]"),
                        "variables": ["gammamax", "v", "d", "L", "EVCad",
                                      "p", "TVM", "N", "PCad"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 2.2.- Zonas B y C, lineas de categoria no especial (pag. 6-7)
            # -------------------------------------------------------------
            "BC_no_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = [SHF*(a1+a2)/2 + THF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "a2", "THF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (opcional en este tipo de lineas)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = SHF*[(a1+a2)/2 + CVHF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "a2", "CVHF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dMF*vF60*(a1+a2)/2 + EVCADF60*NCAD",
                                "variables": ["dMF", "vF60", "a1", "a2", "EVCADF60", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = [SHF*(a1+a2)/2 + THF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "a2", "THF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": "Fu*h'/(2*d1) = [SHF*L + THF*N + PCADF*NCAD]/4",
                        "variables": ["Fu", "h_", "d1", "SHF", "L", "THF", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h + EVCADF60*NCAD*h]/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "EVCADF60",
                                      "NCAD", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*THF*h/(2*d1)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "THF", "h",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                    "desviacion_cadena": {
                        "ecuacion": ("tan(gammamax) = [v/2*d*L + EVCad/2]"
                                     " / [p*L + TVM*N + PCad/2]"),
                        "variables": ["gammamax", "v", "d", "L", "EVCad",
                                      "p", "TVM", "N", "PCad"],
                    },
                },
            },
            # -------------------------------------------------------------
            # 2.3.- Zonas B y C, lineas de categoria especial (pag. 7)
            # Igual que el caso no especial salvo la 3a hipotesis, que pasa
            # a usar la sobrecarga y la tension de viento mas hielo.
            # -------------------------------------------------------------
            "BC_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = [SHF*(a1+a2)/2 + THF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "a2", "THF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (obligatoria en categoria especial)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = SHF*[(a1+a2)/2 + CVHF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "a2", "CVHF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dMF*vF60*(a1+a2)/2 + EVCADF60*NCAD",
                                "variables": ["dMF", "vF60", "a1", "a2", "EVCADF60", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": "V = SHF*[(a1+a2)/2 + CVHF*(tan(n1)-tan(n2))] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "a2", "CVHF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "L = %P*TVHF   (8% para <= 66 kV, 15% para > 66 kV)",
                                "variables": ["pctP", "TVHF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": "Fu*h'/(2*d1) = [SHF*L + THF*N + PCADF*NCAD]/4",
                        "variables": ["Fu", "h_", "d1", "SHF", "L", "THF", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h + EVCADF60*NCAD*h]/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "EVCADF60",
                                      "NCAD", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*TVHF*h/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "TVHF", "h",
                                      "SHF", "L", "CVHF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                    "desviacion_cadena": {
                        "ecuacion": ("tan(gammamax) = [v/2*d*L + EVCad/2]"
                                     " / [p*L + TVM*N + PCad/2]"),
                        "variables": ["gammamax", "v", "d", "L", "EVCad",
                                      "p", "TVM", "N", "PCad"],
                    },
                },
            },
        },
    },

    # =====================================================================
    # 3.- APOYO DE ALINEACION-AMARRE (Tema 10, pag. 14)
    # Al tener cadenas de amarre no existe la recta de desviacion de cadena.
    # =====================================================================
    "alineacion_amarre": {
        "nombre": "Apoyo de alineacion-amarre",
        "desviacion_cadena": False,
        "usa_parametro_S": False,
        "porcentajes_desequilibrio": PORCENTAJES_DESEQUILIBRIO["alineacion_amarre"],
        "zonas": {
            # -------------------------------------------------------------
            # 3.1.- Zona A (pag. 14-15)
            # -------------------------------------------------------------
            "A": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": ("L = %P*T0F   (15% para <= 66 kV, 25% para > 66 kV;"
                                             " T0F mayor entre T0F1 y T0F2)"),
                                "variables": ["pctP", "T0F"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*T0F*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "T0F", "h",
                                      "pF", "L", "CVF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
                        "variables": ["fmx", "TTemp", "pCond"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 3.2.- Zonas B y C, lineas de categoria no especial (pag. 15-16)
            # -------------------------------------------------------------
            "BC_no_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (opcional)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dMHF*vF60*(a1+a2)/2 + EVCADF60*NCAD",
                                "variables": ["dMHF", "vF60", "a1", "a2", "EVCADF60", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": ("L = %P*THF   (15% para <= 66 kV, 25% para > 66 kV;"
                                             " THF mayor entre THF1 y THF2)"),
                                "variables": ["pctP", "THF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": "Fu*h'/(2*d1) = [SHF*L + THF*N + PCADF*NCAD]/4",
                        "variables": ["Fu", "h_", "d1", "SHF", "L", "THF", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h + EVCADF60*NCAD*h]/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "EVCADF60",
                                      "NCAD", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*THF*h/(2*d1)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "THF", "h",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 3.3.- Zonas B y C, lineas de categoria especial (pag. 16-17)
            # Igual que el caso no especial salvo la 3a hipotesis.
            # -------------------------------------------------------------
            "BC_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (obligatoria en categoria especial)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             + " PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dMHF*vF60*(a1+a2)/2 + EVCADF60*NCAD",
                                "variables": ["dMHF", "vF60", "a1", "a2", "EVCADF60", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": ("L = %P*TVHF   (15% para <= 66 kV, 25% para > 66 kV;"
                                             " TVHF mayor entre TVHF1 y TVHF2)"),
                                "variables": ["pctP", "TVHF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": "Fu*h'/(2*d1) = [SHF*L + THF*N + PCADF*NCAD]/4",
                        "variables": ["Fu", "h_", "d1", "SHF", "L", "THF", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h + EVCADF60*NCAD*h]/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "EVCADF60",
                                      "NCAD", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*TVHF*h/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "TVHF", "h",
                                      "SHF", "L", "CVHF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },
        },
    },

    # =====================================================================
    # 4.- APOYO DE ALINEACION-ANCLAJE (Tema 10, pag. 21)
    # Cadenas de anclaje: tampoco hay recta de desviacion de cadena.
    # =====================================================================
    "alineacion_anclaje": {
        "nombre": "Apoyo de alineacion-anclaje",
        "desviacion_cadena": False,
        "usa_parametro_S": False,
        "porcentajes_desequilibrio": PORCENTAJES_DESEQUILIBRIO["alineacion_anclaje"],
        "zonas": {
            # -------------------------------------------------------------
            # 4.1.- Zona A (pag. 21)
            # -------------------------------------------------------------
            "A": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": ("L = %P*T0F   (50% para todas las lineas;"
                                             " T0F mayor entre T0F1 y T0F2)"),
                                "variables": ["pctP", "T0F"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*T0F*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "T0F", "h",
                                      "pF", "L", "CVF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
                        "variables": ["fmx", "TTemp", "pCond"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 4.2.- Zonas B y C, lineas de categoria no especial (pag. 21-22)
            # -------------------------------------------------------------
            "BC_no_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (opcional)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dMHF*vF60*(a1+a2)/2 + EVCADF60*NCAD",
                                "variables": ["dMHF", "vF60", "a1", "a2", "EVCADF60", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": ("L = %P*THF   (50% para todas las lineas;"
                                             " THF mayor entre THF1 y THF2)"),
                                "variables": ["pctP", "THF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": "Fu*h'/(2*d1) = [SHF*L + THF*N + PCADF*NCAD]/4",
                        "variables": ["Fu", "h_", "d1", "SHF", "L", "THF", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h + EVCADF60*NCAD*h]/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "EVCADF60",
                                      "NCAD", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*THF*h/(2*d1)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "THF", "h",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 4.3.- Zonas B y C, lineas de categoria especial (pag. 23)
            # Igual que el caso no especial salvo la 3a hipotesis.
            # -------------------------------------------------------------
            "BC_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*(a1+a2)/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (obligatoria en categoria especial)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dMHF*vF60*(a1+a2)/2 + EVCADF60*NCAD",
                                "variables": ["dMHF", "vF60", "a1", "a2", "EVCADF60", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": ("L = %P*TVHF   (50% para todas las lineas;"
                                             " TVHF mayor entre TVHF1 y TVHF2)"),
                                "variables": ["pctP", "TVHF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": "Fu*h'/(2*d1) = [SHF*L + THF*N + PCADF*NCAD]/4",
                        "variables": ["Fu", "h_", "d1", "SHF", "L", "THF", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h + EVCADF60*NCAD*h]/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "EVCADF60",
                                      "NCAD", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*TVHF*h/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "TVHF", "h",
                                      "SHF", "L", "CVHF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },
        },
    },

    # =====================================================================
    # 5.- APOYO DE ANGULO-SUSPENSION (Tema 10, pag. 27)
    # Entra en juego el parametro S (se dibuja una linea por cada angulo).
    # Al ser de suspension si existe la recta de desviacion de cadena.
    # =====================================================================
    "angulo_suspension": {
        "nombre": "Apoyo de angulo-suspension",
        "desviacion_cadena": True,
        "usa_parametro_S": True,
        "porcentajes_desequilibrio": PORCENTAJES_DESEQUILIBRIO["angulo_suspension"],
        "zonas": {
            # -------------------------------------------------------------
            # 5.1.- Zona A (pag. 27-28)
            # -------------------------------------------------------------
            "A": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2) + EVCADF*NCAD"
                                             " + 2*TVF*cos(alfa/2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa",
                                              "EVCADF", "NCAD", "TVF"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = 2*T0F*cos(alfa/2)",
                                "variables": ["T0F", "alfa"],
                            },
                            "L": {
                                "ecuacion": "L = %P*T0F   (8% para <= 66 kV, 15% para > 66 kV)",
                                "variables": ["pctP", "T0F"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + T0F*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "T0F", "pF", "CVF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = T0F*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*T0F*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "T0F", "h", "alfa", "pctP",
                                      "pF", "L", "CVF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
                        "variables": ["fmx", "TTemp", "pCond"],
                    },
                    "desviacion_cadena": {
                        "ecuacion": ("tan(gammamax) = [2*TVM*cos((beta-alfa)/2)"
                                     " + v/2*d*L*cos((beta-alfa)/2) + EVCad/2]"
                                     " / [p*L + TVM*N + PCad/2]"),
                        "variables": ["gammamax", "TVM", "beta", "alfa", "v", "d", "L",
                                      "EVCad", "p", "N", "PCad"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 5.2.- Zonas B y C, lineas de categoria no especial (pag. 28-29)
            # -------------------------------------------------------------
            "BC_no_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF*NCAD + 2*TVF*cos(alfa/2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa",
                                              "EVCADF", "NCAD", "TVF"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = 2*THF*cos(alfa/2)",
                                "variables": ["THF", "alfa"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (opcional)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dMHF*vF60*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF60*NCAD + 2*TVHF*cos(alfa/2)"),
                                "variables": ["dMHF", "vF60", "a1", "a2", "beta", "alfa",
                                              "EVCADF60", "NCAD", "TVHF"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = 2*THF*cos(alfa/2)",
                                "variables": ["THF", "alfa"],
                            },
                            "L": {
                                "ecuacion": "L = %P*THF   (8% para <= 66 kV, 15% para > 66 kV)",
                                "variables": ["pctP", "THF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + TVF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "TVF", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF60*NCAD*h]/(2*d1)"
                                     " + TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "beta", "alfa",
                                      "EVCADF60", "NCAD", "TVHF", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*THF*h/(2*d1)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa", "pctP",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                    "desviacion_cadena": {
                        "ecuacion": ("tan(gammamax) = [2*TVM*cos((beta-alfa)/2)"
                                     " + v/2*d*L*cos((beta-alfa)/2) + EVCad/2]"
                                     " / [p*L + TVM*N + PCad/2]"),
                        "variables": ["gammamax", "TVM", "beta", "alfa", "v", "d", "L",
                                      "EVCad", "p", "N", "PCad"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 5.3.- Zonas B y C, lineas de categoria especial (pag. 30)
            # Igual que el caso no especial salvo la 3a hipotesis.
            # -------------------------------------------------------------
            "BC_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF*NCAD + 2*TVF*cos(alfa/2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa",
                                              "EVCADF", "NCAD", "TVF"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = 2*THF*cos(alfa/2)",
                                "variables": ["THF", "alfa"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (obligatoria en categoria especial)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dMHF*vF60*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF60*NCAD + 2*TVHF*cos(alfa/2)"),
                                "variables": ["dMHF", "vF60", "a1", "a2", "beta", "alfa",
                                              "EVCADF60", "NCAD", "TVHF"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF*(tan(n1)-tan(n2))]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF", "n1", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = 2*TVHF*cos(alfa/2)",
                                "variables": ["TVHF", "alfa"],
                            },
                            "L": {
                                "ecuacion": "L = %P*TVHF   (8% para <= 66 kV, 15% para > 66 kV)",
                                "variables": ["pctP", "TVHF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + TVF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "TVF", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF60*NCAD*h]/(2*d1)"
                                     " + TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "beta", "alfa",
                                      "EVCADF60", "NCAD", "TVHF", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*TVHF*h/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "TVHF", "h", "alfa", "pctP",
                                      "SHF", "L", "CVHF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                    "desviacion_cadena": {
                        "ecuacion": ("tan(gammamax) = [2*TVM*cos((beta-alfa)/2)"
                                     " + v/2*d*L*cos((beta-alfa)/2) + EVCad/2]"
                                     " / [p*L + TVM*N + PCad/2]"),
                        "variables": ["gammamax", "TVM", "beta", "alfa", "v", "d", "L",
                                      "EVCad", "p", "N", "PCad"],
                    },
                },
            },
        },
    },

    # =====================================================================
    # 6.- APOYO DE ANGULO-AMARRE (Tema 10, pag. 35)
    # Cadenas de amarre: sin desviacion de cadena. Entra el parametro S.
    # =====================================================================
    "angulo_amarre": {
        "nombre": "Apoyo de angulo-amarre",
        "desviacion_cadena": False,
        "usa_parametro_S": True,
        "porcentajes_desequilibrio": PORCENTAJES_DESEQUILIBRIO["angulo_amarre"],
        "zonas": {
            # -------------------------------------------------------------
            # 6.1.- Zona A (pag. 35-37)
            # -------------------------------------------------------------
            "A": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2) + EVCADF*NCAD"
                                             " + raiz(((T0F1+T0F2)*cos(alfa/2))^2"
                                             " + ((T0F1-T0F2)*sen(alfa/2))^2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa", "EVCADF",
                                              "NCAD", "T0F1", "T0F2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((T0F1+T0F2)*cos(alfa/2))^2"
                                             " + ((T0F1-T0F2)*sen(alfa/2))^2)"),
                                "variables": ["T0F1", "T0F2", "alfa"],
                            },
                            "L": {
                                "ecuacion": ("L = %P*T0F   (15% para <= 66 kV, 25% para > 66 kV;"
                                             " T0F mayor entre T0F1 y T0F2)"),
                                "variables": ["pctP", "T0F"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + T0F*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "T0F", "pF", "CVF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = T0F*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*T0F*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "T0F", "h", "alfa", "pctP",
                                      "pF", "L", "CVF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
                        "variables": ["fmx", "TTemp", "pCond"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 6.2.- Zonas B y C, lineas de categoria no especial (pag. 37-38)
            # -------------------------------------------------------------
            "BC_no_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2) + EVCADF*NCAD"
                                             " + raiz(((TVF1+TVF2)*cos(alfa/2))^2"
                                             " + ((TVF1-TVF2)*sen(alfa/2))^2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa", "EVCADF",
                                              "NCAD", "TVF1", "TVF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((THF1+THF2)*cos(alfa/2))^2"
                                             " + ((THF1-THF2)*sen(alfa/2))^2)"),
                                "variables": ["THF1", "THF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (opcional)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dMHF*vF60*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF60*NCAD"
                                             " + raiz(((TVHF1+TVHF2)*cos(alfa/2))^2"
                                             " + ((TVHF1-TVHF2)*sen(alfa/2))^2)"),
                                "variables": ["dMHF", "vF60", "a1", "a2", "beta", "alfa",
                                              "EVCADF60", "NCAD", "TVHF1", "TVHF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((THF1+THF2)*cos(alfa/2))^2"
                                             " + ((THF1-THF2)*sen(alfa/2))^2)"),
                                "variables": ["THF1", "THF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": ("L = %P*THF   (15% para <= 66 kV, 25% para > 66 kV;"
                                             " THF mayor entre THF1 y THF2)"),
                                "variables": ["pctP", "THF"],
                            },
                        },
                    },
                },

                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + TVF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "TVF", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF60*NCAD*h]/(2*d1)"
                                     " + TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "beta", "alfa",
                                      "EVCADF60", "NCAD", "TVHF", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*THF*h/(2*d1)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa", "pctP",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 6.3.- Zonas B y C, lineas de categoria especial (pag. 38-39)
            # Igual que el caso no especial salvo la 3a hipotesis.
            # -------------------------------------------------------------
            "BC_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2) + EVCADF*NCAD"
                                             " + raiz(((TVF1+TVF2)*cos(alfa/2))^2"
                                             " + ((TVF1-TVF2)*sen(alfa/2))^2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa", "EVCADF",
                                              "NCAD", "TVF1", "TVF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((THF1+THF2)*cos(alfa/2))^2"
                                             " + ((THF1-THF2)*sen(alfa/2))^2)"),
                                "variables": ["THF1", "THF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (obligatoria en categoria especial)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dMHF*vF60*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF60*NCAD"
                                             " + raiz(((TVHF1+TVHF2)*cos(alfa/2))^2"
                                             " + ((TVHF1-TVHF2)*sen(alfa/2))^2)"),
                                "variables": ["dMHF", "vF60", "a1", "a2", "beta", "alfa",
                                              "EVCADF60", "NCAD", "TVHF1", "TVHF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((TVHF1+TVHF2)*cos(alfa/2))^2"
                                             " + ((TVHF1-TVHF2)*sen(alfa/2))^2)"),
                                "variables": ["TVHF1", "TVHF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": ("L = %P*TVHF   (15% para <= 66 kV, 25% para > 66 kV;"
                                             " TVHF mayor entre TVHF1 y TVHF2)"),
                                "variables": ["pctP", "TVHF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + TVF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "TVF", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF60*NCAD*h]/(2*d1)"
                                     " + TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "beta", "alfa",
                                      "EVCADF60", "NCAD", "TVHF", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*TVHF*h/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "TVHF", "h", "alfa", "pctP",
                                      "SHF", "L", "CVHF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },
        },
    },


    # =====================================================================
    # 7.- APOYO DE ANGULO-ANCLAJE (Tema 10, pag. 44)
    # Cadenas de anclaje: sin desviacion de cadena. Entra el parametro S.
    # =====================================================================
    "angulo_anclaje": {
        "nombre": "Apoyo de angulo-anclaje",
        "desviacion_cadena": False,
        "usa_parametro_S": True,
        "porcentajes_desequilibrio": PORCENTAJES_DESEQUILIBRIO["angulo_anclaje"],
        "zonas": {
            # -------------------------------------------------------------
            # 7.1.- Zona A (pag. 44-45)
            # -------------------------------------------------------------
            "A": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2) + EVCADF*NCAD"
                                             " + raiz(((T0F1+T0F2)*cos(alfa/2))^2"
                                             " + ((T0F1-T0F2)*sen(alfa/2))^2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa", "EVCADF",
                                              "NCAD", "T0F1", "T0F2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((T0F1+T0F2)*cos(alfa/2))^2"
                                             " + ((T0F1-T0F2)*sen(alfa/2))^2)"),
                                "variables": ["T0F1", "T0F2", "alfa"],
                            },
                            "L": {
                                "ecuacion": ("L = %P*T0F   (50% para todas las lineas;"
                                             " T0F mayor entre T0F1 y T0F2)"),
                                "variables": ["pctP", "T0F"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + T0F*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "T0F", "pF", "CVF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = T0F*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*T0F*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "T0F", "h", "alfa", "pctP",
                                      "pF", "L", "CVF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
                        "variables": ["fmx", "TTemp", "pCond"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 7.2.- Zonas B y C, lineas de categoria no especial (pag. 45-47)
            # -------------------------------------------------------------
            "BC_no_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2) + EVCADF*NCAD"
                                             " + raiz(((TVF1+TVF2)*cos(alfa/2))^2"
                                             " + ((TVF1-TVF2)*sen(alfa/2))^2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa", "EVCADF",
                                              "NCAD", "TVF1", "TVF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((THF1+THF2)*cos(alfa/2))^2"
                                             " + ((THF1-THF2)*sen(alfa/2))^2)"),
                                "variables": ["THF1", "THF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (opcional)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dMHF*vF60*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF60*NCAD"
                                             " + raiz(((TVHF1+TVHF2)*cos(alfa/2))^2"
                                             " + ((TVHF1-TVHF2)*sen(alfa/2))^2)"),
                                "variables": ["dMHF", "vF60", "a1", "a2", "beta", "alfa",
                                              "EVCADF60", "NCAD", "TVHF1", "TVHF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((THF1+THF2)*cos(alfa/2))^2"
                                             " + ((THF1-THF2)*sen(alfa/2))^2)"),
                                "variables": ["THF1", "THF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": ("L = %P*THF   (50% para todas las lineas;"
                                             " THF mayor entre THF1 y THF2)"),
                                "variables": ["pctP", "THF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + TVF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "TVF", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF60*NCAD*h]/(2*d1)"
                                     " + TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "beta", "alfa",
                                      "EVCADF60", "NCAD", "TVHF", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*THF*h/(2*d1)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa", "pctP",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },

            # -------------------------------------------------------------
            # 7.3.- Zonas B y C, lineas de categoria especial (pag. 47)
            # Igual que el caso no especial salvo la 3a hipotesis.
            # -------------------------------------------------------------
            "BC_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = pF*[(a1+a2)/2 + CVF1*tan(n1) - CVF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["pF", "a1", "a2", "CVF1", "n1", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dF*vF*(a1+a2)/2*cos((beta-alfa)/2) + EVCADF*NCAD"
                                             " + raiz(((TVF1+TVF2)*cos(alfa/2))^2"
                                             " + ((TVF1-TVF2)*sen(alfa/2))^2)"),
                                "variables": ["dF", "vF", "a1", "a2", "beta", "alfa", "EVCADF",
                                              "NCAD", "TVF1", "TVF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = [SHF*(a1+a2)/2 + THF1*tan(n1) - THF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "THF1", "n1", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((THF1+THF2)*cos(alfa/2))^2"
                                             " + ((THF1-THF2)*sen(alfa/2))^2)"),
                                "variables": ["THF1", "THF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": "2a hipotesis de viento mas hielo (obligatoria en categoria especial)",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = dMHF*vF60*(a1+a2)/2*cos((beta-alfa)/2)"
                                             " + EVCADF60*NCAD"
                                             " + raiz(((TVHF1+TVHF2)*cos(alfa/2))^2"
                                             " + ((TVHF1-TVHF2)*sen(alfa/2))^2)"),
                                "variables": ["dMHF", "vF60", "a1", "a2", "beta", "alfa",
                                              "EVCADF60", "NCAD", "TVHF1", "TVHF2"],
                            },
                            "L": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                        },
                    },
                    "3a": {
                        "nombre": "3a hipotesis: desequilibrio de tracciones",
                        "esfuerzos": {
                            "V": {
                                "ecuacion": ("V = SHF*[(a1+a2)/2 + CVHF1*tan(n1) - CVHF2*tan(n2)]"
                                             " + PCADF*NCAD"),
                                "variables": ["SHF", "a1", "a2", "CVHF1", "n1", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": ("T = raiz(((TVHF1+TVHF2)*cos(alfa/2))^2"
                                             " + ((TVHF1-TVHF2)*sen(alfa/2))^2)"),
                                "variables": ["TVHF1", "TVHF2", "alfa"],
                            },
                            "L": {
                                "ecuacion": ("L = %P*TVHF   (50% para todas las lineas;"
                                             " TVHF mayor entre TVHF1 y TVHF2)"),
                                "variables": ["pctP", "TVHF"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF*NCAD*h]/(2*d1)"
                                     " + TVF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "beta", "alfa",
                                      "EVCADF", "NCAD", "TVF", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": ("Fu*h'/(2*d1) = THF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "THF", "h", "alfa",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h*cos((beta-alfa)/2)"
                                     " + EVCADF60*NCAD*h]/(2*d1)"
                                     " + TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "beta", "alfa",
                                      "EVCADF60", "NCAD", "TVHF", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "3a": {
                        "ecuacion": ("Fu*h'/(2*d1) = TVHF*h/(2*d1)*2*cos(alfa/2)"
                                     " + %P*TVHF*h/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "TVHF", "h", "alfa", "pctP",
                                      "SHF", "L", "CVHF", "N", "PCADF", "NCAD"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },
        },
    },

    # =====================================================================
    # 8.- APOYO DE PRINCIPIO-FINAL DE LINEA (Tema 10, pag. 55)
    # No hay 3a hipotesis: el desequilibrio de tracciones (100%) se incorpora
    # a las hipotesis 1a y 2a. Sin desviacion de cadena (cadenas de anclaje).
    # En el esfuerzo V se distingue entre principio (VPL) y final (VFL) de linea.
    # =====================================================================
    "principio_final_de_linea": {
        "nombre": "Apoyo de principio-final de linea",
        "desviacion_cadena": False,
        "usa_parametro_S": False,
        "porcentajes_desequilibrio": PORCENTAJES_DESEQUILIBRIO["principio_final_de_linea"],
        "zonas": {
            # -------------------------------------------------------------
            # 8.1.- Zona A (pag. 55)
            # -------------------------------------------------------------
            "A": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento (con desequilibrio de tracciones al 100%)",
                        "esfuerzos": {
                            "VPL": {
                                "ecuacion": "VPL = pF*[a2/2 - CVF2*tan(n2)] + PCADF*NCAD",
                                "variables": ["pF", "a2", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "VFL": {
                                "ecuacion": "VFL = pF*[a1/2 + CVF1*tan(n1)] + PCADF*NCAD",
                                "variables": ["pF", "a1", "CVF1", "n1", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*a/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "L = %P*T0F   (100% para todas las lineas)",
                                "variables": ["pctP", "T0F"],
                            },
                        },
                    },
                },
                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + %P*T0F*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pctP", "T0F", "pF", "CVF", "N", "PCADF"],
                    },
                    "vano_maximo": {
                        "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
                        "variables": ["fmx", "TTemp", "pCond"],
                    },
                },
            },


            # -------------------------------------------------------------
            # 8.2.- Zonas B y C, lineas de categoria no especial o especial
            #       (pag. 55-56). Las ecuaciones son las mismas para ambas
            #       categorias; solo cambia que la 2a V+H es opcional (no
            #       especial) u obligatoria (especial).
            # -------------------------------------------------------------
            "BC_no_especial": {
                "hipotesis": {
                    "1a": {
                        "nombre": "1a hipotesis: viento (con desequilibrio de tracciones al 100%)",
                        "esfuerzos": {
                            "VPL": {
                                "ecuacion": "VPL = pF*[a2/2 - CVF2*tan(n2)] + PCADF*NCAD",
                                "variables": ["pF", "a2", "CVF2", "n2", "PCADF", "NCAD"],
                            },
                            "VFL": {
                                "ecuacion": "VFL = pF*[a1/2 + CVF1*tan(n1)] + PCADF*NCAD",
                                "variables": ["pF", "a1", "CVF1", "n1", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF*a/2 + EVCADF*NCAD",
                                "variables": ["dF", "vF", "a1", "a2", "EVCADF", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "L = %P*TVF   (100% para todas las lineas)",
                                "variables": ["pctP", "TVF"],
                            },
                        },
                    },
                    "2a": {
                        "nombre": "2a hipotesis: hielo (con desequilibrio de tracciones al 100%)",
                        "esfuerzos": {
                            "VPL": {
                                "ecuacion": "VPL = [SHF*a2/2 - THF2*tan(n2)] + PCADF*NCAD",
                                "variables": ["SHF", "a2", "THF2", "n2", "PCADF", "NCAD"],
                            },
                            "VFL": {
                                "ecuacion": "VFL = [SHF*a1/2 + THF1*tan(n1)] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "THF1", "n1", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "No aplica",
                                "variables": [],
                            },
                            "L": {
                                "ecuacion": "L = %P*THF   (100% para todas las lineas)",
                                "variables": ["pctP", "THF"],
                            },
                        },
                    },
                    "2a_VH": {
                        "nombre": ("2a hipotesis de viento mas hielo (opcional en no especial,"
                                   " obligatoria en especial)"),
                        "esfuerzos": {
                            "VPL": {
                                "ecuacion": "VPL = SHF*[a2/2 - CVHF2*tan(n2)] + PCADF*NCAD",
                                "variables": ["SHF", "a2", "CVHF2", "n2", "PCADF", "NCAD"],
                            },
                            "VFL": {
                                "ecuacion": "VFL = SHF*[a1/2 + CVHF1*tan(n1)] + PCADF*NCAD",
                                "variables": ["SHF", "a1", "CVHF1", "n1", "PCADF", "NCAD"],
                            },
                            "T": {
                                "ecuacion": "T = dF*vF60*(a1+a2)/2 + EVCADF60*NCAD",
                                "variables": ["dF", "vF60", "a1", "a2", "EVCADF60", "NCAD"],
                            },
                            "L": {
                                "ecuacion": "L = %P*TVHF   (100% para todas las lineas)",
                                "variables": ["pctP", "TVHF"],
                            },
                        },
                    },
                },

                "rectas": {
                    "1a": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dF*vF*L*h + EVCADF*NCAD*h]/(2*d1)"
                                     " + %P*TVF*h/(2*d1)"
                                     " + [pF*(L + CVF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dF", "vF", "L", "h", "EVCADF",
                                      "NCAD", "pctP", "TVF", "pF", "CVF", "N", "PCADF"],
                    },
                    "2a": {
                        "ecuacion": ("Fu*h'/(2*d1) = %P*THF*h/(2*d1)"
                                     " + [SHF*L + THF*N + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "pctP", "THF", "h",
                                      "SHF", "L", "N", "PCADF", "NCAD"],
                    },
                    "2a_VH": {
                        "ecuacion": ("Fu*h'/(2*d1) = [dMF*vF60*L*h + EVCADF60*NCAD*h]/(2*d1)"
                                     " + %P*TVHF*h/(2*d1)"
                                     " + [SHF*(L + CVHF*N) + PCADF*NCAD]/4"),
                        "variables": ["Fu", "h_", "d1", "dMF", "vF60", "L", "h", "EVCADF60",
                                      "NCAD", "pctP", "TVHF", "SHF", "CVHF", "N", "PCADF"],
                    },
                    "vano_maximo": {
                        "ecuacion": ("L = la menor entre raiz(fmx*8*TTemp/pCond)"
                                     " y raiz(fmx*8*T0H/SH)"),
                        "variables": ["fmx", "TTemp", "pCond", "T0H", "SHF"],
                    },
                },
            },
            # BC_especial usa las mismas ecuaciones que BC_no_especial
            # (ver nota en el encabezado de la seccion 8.2).
            "BC_especial": "mismas_ecuaciones_que_BC_no_especial",
        },
    },
}

# ---------------------------------------------------------------------------
# 4. ECUACIONES AUXILIARES (comunes a todos los apoyos)
#    - Vano maximo por separacion de conductores (ITC-LAT 07, punto 5.4.1)
#    - Desviacion de la cadena de aisladores
#    - Cruceta (peso vertical maximo admisible)
# ---------------------------------------------------------------------------
AUXILIARES = {
    "vano_maximo": {
        "separacion_conductores": {
            "ecuacion": ("D = K*raiz(F) + L + K'*DPP   (ITC-LAT 07 5.4.1)"),
            "variables": ["D", "K", "F", "L", "K_", "DPP"],
        },
        "flecha_maxima": {
            "ecuacion": "fmx = ((D - K'*DPP)/K)^2 - L",
            "variables": ["D", "K_", "DPP", "K", "L"],
        },
        "vano_por_flecha": {
            "ecuacion": "L = raiz(fmx*8*TTemp/pCond)",
            "variables": ["fmx", "TTemp", "pCond"],
            "notas": ("Vano maximo por temperatura. En zonas B y C se compara con"
                      " la hipotesis 0C+H: L = raiz(fmx*8*T0H/SH), y se toma la menor."),
        },
        "vano_por_hielo": {
            "ecuacion": "L = raiz(fmx*8*T0H/SH)",
            "variables": ["fmx", "T0H", "SH"],
            "notas": "Hipotesis 0C mas hielo (zonas B y C).",
        },
    },
    "desviacion_cadena": {
        "alineacion": {
            "ecuacion": ("tan(gammamax) = [v/2*d*L + EVCad/2]"
                         " / [p*L + TVM*N + PCad/2]"),
            "variables": ["gammamax", "v", "d", "L", "EVCad", "p", "TVM", "N", "PCad"],
            "notas": ("Apoyo de alineacion-suspension. Partiendo de"
                      " tan(gammamax) = [v/2*d*(a1+a2)/2 + EVCad/2] / [p*(a1+a2)/2"
                      " + TVM*(tan(n1)-tan(n2)) + PCad/2]."),
        },
        "angulo": {
            "ecuacion": ("tan(gammamax) = [2*TVM*cos((beta-alfa)/2)"
                         " + v/2*d*L*cos((beta-alfa)/2) + EVCad/2]"
                         " / [p*L + TVM*N + PCad/2]"),
            "variables": ["gammamax", "TVM", "beta", "alfa", "v", "d", "L",
                          "EVCad", "p", "N", "PCad"],
            "notas": "Apoyo de angulo-suspension.",
        },
    },
    "cruceta": {
        "ecuacion": ("PAdmCru = P*L + T*N + PCADF*NCAD + PHombre"),
        "variables": ["PAdmCru", "P", "L", "T", "N", "PCADF", "NCAD", "PHombre"],
        "notas": (
            "Peso vertical maximo admisible de la cruceta. PHombre = 80 daN cuando se"
            " considera el peso del operario (se dibujan dos rectas: con y sin)."
            " Para zona A se usan el peso del conductor y la tension a -5 grados C;"
            " para zonas B y C el peso con hielo (SH) y la tension de la hipotesis"
            " correspondiente (-15/-20 grados C mas hielo)."),
        "peso_operario_daN": 80.0,
    },
}

# ---------------------------------------------------------------------------
# 5. FUNCION DE ACCESO: devuelve las ecuaciones de un caso concreto
#    (tipo de apoyo + zona). Es la interfaz que usara el resto del codigo.
# ---------------------------------------------------------------------------
def obtener_ecuaciones(tipo_apoyo, zona="A", categoria=None):
    """Devuelve el conjunto de ecuaciones (hipotesis y rectas) de un caso.

    Parametros:
        tipo_apoyo: clave de tipo de apoyo (ver docstring del modulo).
        zona: "A", "BC_no_especial" o "BC_especial". Se admite el parametro
              alternativo 'categoria' ("no_especial"/"especial") para
              compatibilidad con futuras lecturas del Excel.
        categoria: si se indica y zona es "BC", se traduce a la clave completa.

    Devuelve:
        dict con "nombre", "desviacion_cadena", "usa_parametro_S",
        "porcentajes_desequilibrio", "hipotesis" y "rectas".

    Lanza ValueError si el caso no existe.
    """
    if tipo_apoyo not in CASOS:
        raise ValueError(
            "Tipo de apoyo desconocido: %r. Valores validos: %s"
            % (tipo_apoyo, ", ".join(sorted(CASOS))))
    caso = CASOS[tipo_apoyo]

    # Traduccion de la combinacion zona/categoria a la clave de zona.
    if zona.upper() == "BC" and categoria:
        zona = "BC_especial" if str(categoria).lower() == "especial" else "BC_no_especial"
    elif zona not in ("A", "BC_no_especial", "BC_especial"):
        raise ValueError(
            "Zona desconocida: %r. Valores validos: A, BC_no_especial, BC_especial (o BC + categoria)" % zona)

    if zona not in caso["zonas"]:
        raise ValueError(
            "La zona %r no existe para el apoyo %r." % (zona, tipo_apoyo))

    zona_data = caso["zonas"][zona]
    # Principio-final de linea: la zona BC_especial comparte las mismas
    # ecuaciones que BC_no_especial (ver nota de la seccion 8.2 del Tema 10).
    if isinstance(zona_data, str):
        return caso["zonas"]["BC_no_especial"]
    return zona_data


def listar_casos():
    """Devuelve un resumen legible de todos los casos almacenados."""
    resumen = {}
    for tipo, caso in sorted(CASOS.items()):
        resumen[tipo] = {
            "nombre": caso["nombre"],
            "desviacion_cadena": caso["desviacion_cadena"],
            "usa_parametro_S": caso["usa_parametro_S"],
            "porcentajes_desequilibrio": caso["porcentajes_desequilibrio"],
            "zonas": sorted(caso["zonas"].keys()),
        }
    return resumen



# ---------------------------------------------------------------------------
# 6. AUTO-VERIFICACION (python graficos_utilizacion_ecuaciones.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    print("== Base de datos de ecuaciones del Tema 10 ==")
    print("Variables registradas:", len(VARIABLES))
    print("Casos de apoyo registrados:", len(CASOS))
    for tipo, res in sorted(listar_casos().items()):
        print("\n- %s (%s)" % (tipo, res["nombre"]))
        print("  desviacion_cadena=%s  usa_S=%s  desequilibrio=%s"
              % (res["desviacion_cadena"], res["usa_parametro_S"],
                 res["porcentajes_desequilibrio"]))
        for zona in res["zonas"]:
            ec = obtener_ecuaciones(tipo, zona=zona)
            n_hip = len(ec.get("hipotesis", {}))
            n_rect = len(ec.get("rectas", {}))
            print("  zona=%-14s hipotesis=%d rectas=%d" % (zona, n_hip, n_rect))

    # Ejemplo de uso: alineacion-suspension zona A
    print("\n== Ejemplo: alineacion_suspension zona A ==")
    caso = obtener_ecuaciones("alineacion_suspension", zona="A")
    print("Hipotesis 1a, esfuerzo V:")
    print("  ", caso["hipotesis"]["1a"]["esfuerzos"]["V"]["ecuacion"])
    print("Recta 1a hipotesis:")
    print("  ", caso["rectas"]["1a"]["ecuacion"])
    sys.exit(0)
