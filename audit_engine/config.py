"""Centralized configuration loading.

All tunables live in config/default.yaml. This module loads that file, applies
environment-variable overrides (BRAND_AUDIT__SECTION__KEY=value), and exposes
a single immutable Config object. No script in this project should hardcode a
crawl limit, timeout, or threshold outside of this file's defaults.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ENV_PREFIX = "BRAND_AUDIT__"
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


def _coerce(raw: str, reference: Any) -> Any:
    """Coerce an environment-variable string to match the type of the default value."""
    if isinstance(reference, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(reference, int):
        return int(raw)
    if isinstance(reference, float):
        return float(raw)
    if isinstance(reference, list):
        return [item.strip() for item in raw.split(",") if item.strip()]
    return raw


def _apply_env_overrides(data: dict) -> dict:
    for env_key, raw_value in os.environ.items():
        if not env_key.startswith(_ENV_PREFIX):
            continue
        path = env_key[len(_ENV_PREFIX):].lower().split("__")
        cursor = data
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        leaf = path[-1]
        cursor[leaf] = _coerce(raw_value, cursor.get(leaf))
    return data


@dataclass(frozen=True)
class Config:
    """Read-only view over the merged configuration dictionary."""

    _data: dict

    def section(self, name: str) -> dict:
        return self._data.get(name, {})

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    @property
    def raw(self) -> dict:
        return copy.deepcopy(self._data)


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from YAML (default: config/default.yaml) plus env overrides."""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data = _apply_env_overrides(data)
    return Config(_data=data)
