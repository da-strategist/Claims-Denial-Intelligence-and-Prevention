"""Generate the synthetic insurance policy PDFs into data/policies/.

Run from the Patient_plan_RAG directory:
    python -m synthetic_data.generate_policy            # only missing PDFs
    python -m synthetic_data.generate_policy --force    # regenerate all

Existing PDFs are skipped by default: regenerating changes a PDF's bytes
(unless it was already written in invariant mode), which gives it a new
content-hash document ID on a fresh ingest. The backend ingests new PDFs in
data/policies/ automatically at startup.
"""

import argparse
from pathlib import Path

from .policies import POLICIES
from .render import render_policy

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "policies"


def generate(force: bool = False, output_dir: Path = OUTPUT_DIR) -> list[Path]:
    written = []
    for spec in POLICIES:
        target = output_dir / spec["filename"]
        if target.exists() and not force:
            print(f"Exists, skipped: {target.name}")
            continue
        written.append(render_policy(spec, output_dir))
        print(f"Generated: {target.name}")
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="regenerate existing PDFs")
    generate(force=parser.parse_args().force)
