# Datos, ejemplo y atribución

## Ejemplo público

`data/examples/demo_line/` contiene un caso pequeño para recorrer el flujo real:

- un Excel compatible con la importación Andelec;
- coordenadas y cuadros en DOCX;
- coordenadas UTM desplazadas y anonimizadas;
- un recorte MDT05 reducido para validar el relieve.

No contiene ortofotografía completa, coordenadas del emplazamiento original,
datos meteorológicos vivos, claves ni documentos de terceros.

## PNOA y MDT05

Los mosaicos originales ocupaban varios gigabytes y no deben guardarse en Git.
Para trabajar con una línea propia:

1. obtenga la envolvente UTM de sus apoyos y el huso correspondiente;
2. descargue las hojas MDT05 y, si desea textura, las ortofotos de máxima
   actualidad desde el [Centro de Descargas del CNIG](https://centrodedescargas.cnig.es/);
3. coloque solo las hojas que cubran el trazado en la carpeta de datos activa;
4. use nombres `PNOA_MDT05*.tif` para relieve y `PNOA_MA*.tif` para ortofoto;
5. mantenga el mismo sistema de referencia que las coordenadas de la línea.

El recorte incluido es una obra derivada de datos PNOA MDT05. Reconocimiento:

> Obra derivada de MDT05-cob1 2008-2015 CC-BY 4.0 scne.es.

Consulte siempre la licencia mostrada por el CNIG para la hoja y cobertura que
descargue.

## Meteorología

La integración implementada admite observaciones AEMET OpenData y SiAR. Cada
usuario debe obtener sus propias credenciales en los portales oficiales:

- [AEMET OpenData](https://opendata.aemet.es/)
- [SiAR](https://servicio.mapa.gob.es/siarweb/)

Los datos de estaciones, municipios y coberturas auxiliares se mantienen fuera
del repositorio, en `data/reference/` o mediante `TWINELEC_REFERENCE_DATA_DIR`.

## Andelec y catálogos

Andelec es una herramienta externa. TwinElec procesa documentos exportados por
ella, pero no distribuye el programa, manuales ni material docente/propietario.
Los catálogos JSON mantenidos en este repositorio son los datos estructurados que
el código necesita; sus campos de procedencia no apuntan a rutas locales.
