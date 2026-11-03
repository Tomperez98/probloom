"""Verify the built wheel is the zero-dependency library, not the harness."""

from __future__ import annotations

import sys
import tomllib
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REQUIRED_FILES = {
    "probloom/__init__.py",
    "probloom/filter.py",
    "probloom/py.typed",
}
_FORBIDDEN_FILES = {"probloom/cli.py"}


def main() -> int:
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())["project"]
    version = project["version"]
    wheels = sorted((_REPO_ROOT / "dist").glob(f"probloom-{version}-*.whl"))
    assert len(wheels) == 1, f"expected one wheel for {version}, found {wheels}"
    wheel = wheels[0]

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")

    requires_dist = [line for line in metadata.splitlines() if line.startswith("Requires-Dist:")]
    assert not requires_dist, f"{wheel.name} declares runtime dependencies: {requires_dist}"

    missing = _REQUIRED_FILES - names
    assert not missing, f"{wheel.name} is missing {sorted(missing)}"

    leaked = _FORBIDDEN_FILES & names
    assert not leaked, f"{wheel.name} must not ship the harness: {sorted(leaked)}"

    license_files = [name for name in names if Path(name).name == "LICENSE"]
    assert license_files, f"{wheel.name} is missing LICENSE"

    assert f"Version: {version}" in metadata, f"{wheel.name} does not report version {version}"

    sys.stdout.write(f"verified {wheel.name}: zero runtime dependencies, core package only\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
