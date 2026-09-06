"""Ensures the repo root (and therefore `audit_engine`) is importable regardless
of how pytest is invoked (`pytest`, `python -m pytest`, from a subdirectory, etc.)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
