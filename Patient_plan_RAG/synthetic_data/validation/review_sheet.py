"""Write the reviewer's copy of the validation questions:
REVIEW_SHEET.md (to read) and review_sheet.csv (to mark up in a spreadsheet).

    python -m synthetic_data.validation.review_sheet
"""

import csv
from pathlib import Path

from .questions import METADATA, METADATA_NOTES, QUESTIONS

HERE = Path(__file__).resolve().parent
PLAN_TITLES = {
    "CV": "Cedar Valley Health Plan — Cedar Silver 3500 (SBC format)",
    "HV": "Harborview Health Partners — Gold EPO 1000, 2026 booklet",
    "PC": "Pinecrest Senior Care HMO (Medicare Advantage)",
    "LS": "Lakeshore University Student Health Insurance Plan (two columns, footnotes)",
    "MD": "Meridian Catastrophic Shield 10150 (text PDF)",
    "MS": "Meridian Catastrophic Shield 10150 (scanned copy, read by OCR)",
    "MP": "People with several plans",
}
CATEGORY = {"lookup": "Look-up", "nuance": "Nuance", "abstain": "Not in the document",
            "multi_plan": "Several plans", "scanned": "Scanned"}


def _cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def write() -> tuple[Path, Path]:
    md = ["# Validation set — review sheet", "",
          "Please check each **expected answer** against the plan documents in "
          "`data/validation/`. Mark anything you disagree with, or that an experienced reader "
          "would interpret differently, and add a note. Nuance questions matter most. The app "
          "has **not** been run on these yet; it will be scored only after your review.", "",
          "Columns: what the person asks · the answer the app should give · where it is in the "
          "document · what makes it tricky. \"Not in the document\" means the app should say it "
          "can't find the answer rather than guess.", "",
          "## Plan details the app should read from each document", "",
          "| Document | Insurer | Plan | Plan ID | Effective | Ends | Note |",
          "|---|---|---|---|---|---|---|"]
    for doc, m in METADATA.items():
        md.append(f"| {doc} | {_cell(m['insurer_name'])} | {_cell(m['plan_name'])} | {m['plan_id']} | "
                  f"{m['effective_date']} | {m['expiration_date']} | {_cell(METADATA_NOTES.get(doc, ''))} |")
    for prefix, title in PLAN_TITLES.items():
        qs = [q for q in QUESTIONS if q["id"].startswith(prefix)]
        md += ["", f"## {title}", "", "| ID | Question | Expected answer | Where | Type | Tricky because | Agree? |",
               "|---|---|---|---|---|---|---|"]
        for q in qs:
            where = ", ".join(q["sections"]) or ("—" if q["category"] == "abstain" else "")
            if prefix == "MP":
                where = " + ".join(d.replace(".pdf", "") for d in q["docs"])
            md.append(f"| {q['id']} | {_cell(q['question'])} | {_cell(q['expected'])} | {_cell(where)} | "
                      f"{CATEGORY[q['category']]} | {_cell(q['note'])} | |")
    md_path = HERE / "REVIEW_SHEET.md"
    md_path.write_text("\n".join(md) + "\n")

    csv_path = HERE / "review_sheet.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ID", "Documents", "Question", "Expected answer", "Where", "Type",
                    "Tricky because", "Agree? (Y/N)", "Reviewer note"])
        for q in QUESTIONS:
            w.writerow([q["id"], "; ".join(q["docs"]), q["question"], q["expected"],
                        ", ".join(q["sections"]), CATEGORY[q["category"]], q["note"], "", ""])
    return md_path, csv_path


if __name__ == "__main__":
    for path in write():
        print(f"Wrote {path}")
