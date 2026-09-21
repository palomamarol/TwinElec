# Ejecución y build

## Entorno de desarrollo

- Windows 11 (plataforma usada para validar el build).
- Unity 6000.4.0f1 con soporte Windows Standalone.
- Python 3.14.
- Blender es opcional salvo que se regeneren modelos FBX.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Abra `unity/` desde Unity Hub. `Assets`, `Packages`, `ProjectSettings` y todos
los `.meta` deben permanecer juntos.

## Regenerar el ejemplo

```powershell
Set-Location data/examples/demo_line
python ../../../src/python/principal.py
python ../../../src/python/generar_graficos_utilizacion.py
python ../../../src/python/generar_png_graficos.py
```

El MDT de muestra es suficiente para probar el tratamiento del relieve. No se
incluye ortofotografía del emplazamiento anonimizado, por lo que el motor informa
de su ausencia y continúa.

## Preparar la aplicación autónoma

Desde la raíz del repositorio:

```powershell
python src/python/tools/preparar_datos_exportable.py
python src/python/tools/empacar_motor.py
```

El primer comando reconstruye `release/TwinElec/Datos/`, copia únicamente los
recursos de runtime y genera `manifest.sha256.json`. El segundo crea
`release/TwinElec/motor.exe` con PyInstaller. Ninguno empaqueta credenciales.

Después compile en Unity para Windows x86_64, con salida:

```text
release/TwinElec/TwinElec.exe
```

Por último, retire la información de depuración no distribuible y las rutas de
compilación incrustadas:

```powershell
python src/python/tools/sanitize_release.py
```

La carpeta final contiene `TwinElec.exe`, `TwinElec_Data/`, `UnityPlayer.dll`,
`motor.exe` y `Datos/`. No distribuya carpetas `DoNotShip`, símbolos de
depuración, logs, cachés o el fichero `.spec` de PyInstaller.

## Variables de entorno del motor

Unity las configura al lanzar Python o `motor.exe`:

- `TWINELEC_DATA_DIR`
- `TWINELEC_ASSETS_DIR`
- `TWINELEC_CATALOGS_DIR`
- `TWINELEC_BLENDER_SCRIPTS_DIR`

Las credenciales opcionales se describen en [SECURITY.md](SECURITY.md).
