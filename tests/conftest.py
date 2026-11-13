"""Load integration modules that do not need Home Assistant, by file path."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

COMP = Path(__file__).resolve().parent.parent / "custom_components" / "voyahtweaks-ha"


def load(name: str, filename: str | None = None):
    """Import a module of the integration without importing its package."""
    spec = importlib.util.spec_from_file_location(
        f"vc_{name}", COMP / (filename or f"{name}.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"vc_{name}"] = mod
    spec.loader.exec_module(mod)
    return mod
