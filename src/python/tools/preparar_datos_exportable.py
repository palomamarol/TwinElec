# -*- coding: utf-8 -*-
"""Prepare the external ``Datos`` folder distributed with TwinElec.

The folder is rebuilt from maintained sources every time. Credentials and
local caches are deliberately excluded.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


PYTHON_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PYTHON_DIR.parents[1]
DEFAULT_DESTINATION = REPOSITORY_ROOT / "release" / "TwinElec" / "Datos"

ASSET_PATTERNS = (
    "*.json",
    "*.csv",
    "terreno_real.png",
    "textura_real.jpg",
    "fisica_linea.csv",
)


def _copy_file(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def _safe_clean(destination: Path) -> None:
    destination = destination.resolve()
    repository = REPOSITORY_ROOT.resolve()
    if destination == repository or repository not in destination.parents:
        raise ValueError("The runtime destination must stay inside the repository.")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)


def _write_manifest(destination: Path) -> None:
    entries = []
    for path in sorted(p for p in destination.rglob("*") if p.is_file()):
        if path.name == "manifest.sha256.json":
            continue
        entries.append({
            "path": path.relative_to(destination).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (destination / "manifest.sha256.json").write_text(
        json.dumps(entries, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    destination = DEFAULT_DESTINATION
    if "--destino" in sys.argv:
        destination = Path(sys.argv[sys.argv.index("--destino") + 1])
    destination = destination.resolve()
    _safe_clean(destination)

    # Python motor. Utility/build scripts are not runtime dependencies.
    for source in sorted(PYTHON_DIR.glob("*.py")):
        _copy_file(source, destination / source.name)

    # Compact, maintained inputs.
    example = REPOSITORY_ROOT / "data" / "examples" / "demo_line"
    for source in sorted(example.iterdir()):
        if source.is_file() and source.name.lower() != "secrets.local.json":
            _copy_file(source, destination / source.name)
    shutil.copytree(
        REPOSITORY_ROOT / "data" / "catalogs",
        destination / "catalogs",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        REPOSITORY_ROOT / "blender" / "scripts",
        destination / "blender" / "scripts",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # State shared by Unity and Python.
    assets_source = REPOSITORY_ROOT / "unity" / "Assets"
    assets_destination = destination / "unity" / "Assets"
    for pattern in ASSET_PATTERNS:
        for source in sorted(assets_source.glob(pattern)):
            _copy_file(source, assets_destination / source.name)

    resources_source = assets_source / "Resources"
    for directory_name in (
        "graficos_utilizacion",
        "ModelosArmado",
        "ModelosCadenas",
        "ModelosCruceta",
    ):
        source_dir = resources_source / directory_name
        if not source_dir.is_dir():
            continue
        for source in source_dir.rglob("*"):
            if source.is_file() and source.suffix.lower() in {".fbx", ".png", ".pdf"}:
                relative = source.relative_to(resources_source)
                _copy_file(source, assets_destination / "Resources" / relative)

    (destination / "README.txt").write_text(
        "TwinElec runtime data\n"
        "=====================\n"
        "This folder contains an anonymised demonstration line and compact "
        "runtime resources. Real AEMET/SiAR credentials are never packaged; "
        "configure them with TWINELEC_* environment variables.\n",
        encoding="utf-8",
    )
    _write_manifest(destination)
    print(f"Runtime data prepared at: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
