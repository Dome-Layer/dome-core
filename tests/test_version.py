"""The package version is declared twice; keep the two in step.

v0.4.1 was tagged with pyproject.toml at 0.4.1 and __version__ still at 0.4.0.
"""

import tomllib
from pathlib import Path

import dome_core


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert dome_core.__version__ == declared
