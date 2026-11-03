"""Write the validation plans to data/validation/ (deterministic PDFs), plus
an image-only scanned copy of the Meridian plan.

    python -m synthetic_data.validation.generate
"""

from pathlib import Path

from ..render import render_policy, scan_copy
from .plans import cedar_valley_sbc, harborview_epo, lakeshore_student, meridian_catastrophic, pinecrest_medicare

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "validation"
PLANS = [
    cedar_valley_sbc.POLICY,
    harborview_epo.POLICY_2025,
    harborview_epo.POLICY_2026,
    pinecrest_medicare.POLICY,
    lakeshore_student.POLICY,
    meridian_catastrophic.POLICY,
]
SCANNED = {"meridian_catastrophic_2026_scanned.pdf": "meridian_catastrophic_2026.pdf"}


def generate(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    written = [render_policy(spec, output_dir) for spec in PLANS]
    for scanned, source in SCANNED.items():
        written.append(scan_copy(output_dir / source, output_dir / scanned))
    return written


if __name__ == "__main__":
    for path in generate():
        print(f"Generated: {path.name}")
