"""Pytest root configuration."""

from pathlib import Path

from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(_repo_root / ".env", override=False)
