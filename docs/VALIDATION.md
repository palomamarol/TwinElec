# Validación

Este documento registra qué debe comprobarse antes de publicar o distribuir.
Los resultados de la reorganización se actualizaron el 21 de septiembre de 2026.

## Python

```powershell
$env:PYTHONPATH = (Resolve-Path "src/python")
python -m pytest tests/python -q
```

- Suite: 15 pruebas y 6 subpruebas.
- Cobertura funcional: balance DLR, paridad numérica, geometría de línea,
  calidad meteorológica, fallback no operativo y publicación JSON atómica.
- Resultado: **superada**.

## Unity

Se valida con Unity 6000.4.0f1:

1. importación desde `Assets`, `Packages` y `ProjectSettings` limpios;
2. compilación de scripts sin errores;
3. pruebas EditMode de paridad DLR Python/C#;
4. build Windows x86_64;
5. análisis del build para secretos, rutas personales y `DoNotShip`.

- EditMode: **6/6 superadas**; comprueban la paridad del motor C# frente a los
  casos compartidos de Python.
- Segunda apertura/compilación batch: **código 0**, sin errores de compilación.
- Build Windows x86_64: **Success**, código 0.
- Smoke test: el ejecutable inicia en modo gráfico nulo, carga la escena y
  rechaza correctamente el fallback meteorológico como límite DLR operativo.
- `motor.exe`: inicia y devuelve correctamente el catálogo real de conductores.
- Saneado de release: sin `DoNotShip`, `.pdb`, `.spec`, logs, rutas personales o
  credenciales locales dentro de la carpeta distribuible.

## Integridad de Assets

La comprobación recorre archivos y directorios bajo `unity/Assets`, verifica el
`.meta` asociado, detecta `.meta` huérfanos y agrupa los GUID. No debe aparecer
ningún GUID duplicado.

Resultado final: **389 elementos, 389 `.meta`, 389 GUID; 0 `.meta` ausentes,
0 huérfanos y 0 GUID duplicados**.
