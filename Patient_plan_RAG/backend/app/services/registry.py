"""The document registry (data/policies/_registry.json): one entry per
ingested document. The startup sync (services/ingest.py) maintains it too."""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
POLICY_DIR = Path(os.getenv("POLICY_DIR", str(BASE_DIR / "data" / "policies")))


def load() -> list[dict]:
    path = POLICY_DIR / "_registry.json"
    return json.loads(path.read_text()) if path.exists() else []


def save(registry: list[dict]) -> None:
    (POLICY_DIR / "_registry.json").write_text(json.dumps(registry, indent=2, default=str))
