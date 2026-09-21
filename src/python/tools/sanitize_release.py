"""Remove non-distributable debug output and personal build paths.

Run this after the Unity Windows build. Binary replacements preserve the exact
field length, so PE/CodeView offsets are not changed.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RELEASE = REPOSITORY_ROOT / "release" / "TwinElec"
PDB_PATH = re.compile(rb"[A-Za-z]:\\Users\\[^\x00\r\n]{1,500}?\.pdb")


def _portable_label(original: bytes) -> bytes:
    basename = re.split(rb"[\\/]", original)[-1]
    label = b"TwinElec/build/" + basename
    if len(label) > len(original):
        raise ValueError(f"Replacement is longer than embedded field: {original!r}")
    return label + (b" " * (len(original) - len(label)))


def main() -> int:
    release = DEFAULT_RELEASE.resolve()
    repository = REPOSITORY_ROOT.resolve()
    if repository not in release.parents or not release.is_dir():
        raise ValueError("Expected an existing release/TwinElec directory")

    removed = []
    for path in sorted(release.rglob("*"), reverse=True):
        if path.is_dir() and "DoNotShip" in path.name:
            shutil.rmtree(path)
            removed.append(path.relative_to(release).as_posix())

    rewritten = []
    for path in sorted(p for p in release.rglob("*") if p.is_file()):
        payload = path.read_bytes()
        matches = list(PDB_PATH.finditer(payload))
        if not matches:
            continue
        updated = PDB_PATH.sub(lambda match: _portable_label(match.group(0)), payload)
        path.write_bytes(updated)
        rewritten.append((path.relative_to(release).as_posix(), len(matches)))

    print(f"Removed {len(removed)} DoNotShip directorie(s).")
    print(f"Sanitised {sum(count for _, count in rewritten)} path(s) in "
          f"{len(rewritten)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
