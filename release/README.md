# Release output

Generated desktop builds are intentionally ignored by Git.

Use `src/python/tools/preparar_datos_exportable.py` to create the compact
`TwinElec/Datos/` runtime folder and `src/python/tools/empacar_motor.py` to create
`TwinElec/motor.exe`. Build Unity for Windows into the same `TwinElec/` folder.

See [docs/BUILD_AND_RUN.md](../docs/BUILD_AND_RUN.md) for the verified workflow.
