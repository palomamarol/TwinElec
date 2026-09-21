# Seguridad y publicación

## Estado actual del árbol de trabajo

- No hay claves AEMET o SiAR reales en los archivos actuales.
- `secrets.example.json` solo contiene valores vacíos.
- `secrets.local.json`, `.env` y variantes están ignorados.
- El motor acepta `TWINELEC_AEMET_API_KEY`,
  `TWINELEC_AEMET_PREDICCION_API_KEY` y `TWINELEC_SIAR_API_KEY`.
- Las rutas personales incrustadas en código, documentos y metadatos FBX se han
  retirado.
- El ejemplo público no conserva las coordenadas originales del caso de estudio.

Para uso local, copie `secrets.example.json` como `secrets.local.json` o utilice
variables de entorno. Nunca fuerce su incorporación con `git add -f`.

## Credenciales antiguas

Las credenciales AEMET/SiAR que estuvieron en el repositorio deben considerarse
comprometidas: elimine o revoque las antiguas en cada proveedor y genere otras
solo si necesita la consulta en vivo.

## Historial Git pendiente

El árbol actual está saneado, pero el historial aún puede contener secretos,
rutas, binarios y datos eliminados. No se ha ejecutado `git filter-repo`, BFG,
`git gc`, un `force push` ni ninguna otra reescritura. Esa fase requiere una
segunda autorización, coordinación con cualquier colaborador y verificación del
remoto después del cambio.
