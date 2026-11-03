"""Tests for the published package metadata."""

from __future__ import annotations

import tomllib
from pathlib import Path

from probloom import __version__

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_version_comes_from_the_single_pyproject_source() -> None:
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())["project"]

    assert __version__ == project["version"]


def test_core_package_has_no_runtime_dependencies() -> None:
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())["project"]

    assert project["dependencies"] == []
    assert project["requires-python"] == ">=3.13"
    assert project["license"] == "Apache-2.0"
