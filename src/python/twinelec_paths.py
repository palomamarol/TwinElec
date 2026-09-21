"""Shared path resolution for the TwinElec editor and packaged application.

The Unity editor sets explicit environment variables before starting Python.
The packaged motor uses the same variables and falls back to its ``Datos``
directory. Keeping this logic in one place prevents source-tree names from
leaking into the engineering calculations.
"""

from __future__ import annotations

import os
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_DIR.parents[1]


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def data_dir() -> Path:
    """Active line-data directory (the process working directory by default)."""
    return _env_path("TWINELEC_DATA_DIR") or Path.cwd().resolve()


def assets_dir() -> Path:
    """Directory shared by Unity and the Python engineering motor."""
    configured = _env_path("TWINELEC_ASSETS_DIR")
    if configured:
        return configured
    packaged = data_dir() / "unity" / "Assets"
    if packaged.exists():
        return packaged
    return REPOSITORY_ROOT / "unity" / "Assets"


def catalogs_dir() -> Path:
    configured = _env_path("TWINELEC_CATALOGS_DIR")
    if configured:
        return configured
    packaged = data_dir() / "catalogs"
    if packaged.exists():
        return packaged
    return REPOSITORY_ROOT / "data" / "catalogs"


def blender_scripts_dir() -> Path:
    configured = _env_path("TWINELEC_BLENDER_SCRIPTS_DIR")
    if configured:
        return configured
    packaged = data_dir() / "blender" / "scripts"
    if packaged.exists():
        return packaged
    return REPOSITORY_ROOT / "blender" / "scripts"


def unity_model_dir() -> Path:
    return assets_dir() / "Resources" / "ModelosCruceta"
