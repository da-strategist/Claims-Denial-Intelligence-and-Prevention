"""Check the validation questions against the plan specs (not the app):
every expected phrase must appear in the source text of a document in scope.

    python -m synthetic_data.validation.ground_truth
"""

import html
import re
from collections import Counter

from .generate import PLANS, SCANNED
from .questions import METADATA, QUESTIONS


def _flatten(spec: dict) -> str:
    parts = [t for t, _ in spec["title_lines"]]
    for heading, blocks in spec["sections"]:
        parts.append(heading)
        for b in blocks:
            if isinstance(b, dict) and "table" in b:
                parts += [cell for row in b["table"] for cell in row]
            elif isinstance(b, dict):
                parts.append(b["note"])
            else:
                parts.append(b)
    return html.unescape(" ".join(parts))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


def source_texts() -> dict[str, str]:
    texts = {spec["filename"]: norm(_flatten(spec)) for spec in PLANS}
    for scanned, source in SCANNED.items():
        texts[scanned] = texts[source]
    return texts


def problems() -> list[str]:
    texts = source_texts()
    out = []
    for q in QUESTIONS:
        for d in q["docs"]:
            if d not in texts:
                out.append(f"{q['id']}: unknown document {d}")
        scope = " ".join(texts.get(d, "") for d in q["docs"])
        for p in q["phrases"]:
            if norm(p) not in scope:
                out.append(f"{q['id']}: phrase not in the documents: {p!r}")
        if q["category"] == "abstain" and q["phrases"]:
            out.append(f"{q['id']}: abstain questions have no phrases")
        if q["category"] != "abstain" and not q["phrases"]:
            out.append(f"{q['id']}: no expected phrases")
    for doc in METADATA:
        if doc not in texts:
            out.append(f"metadata for unknown document {doc}")
    ids = Counter(q["id"] for q in QUESTIONS)
    out += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    return out


if __name__ == "__main__":
    found = problems()
    print("\n".join(found) or "Ground truth OK")
    print(dict(Counter(q["category"] for q in QUESTIONS)), "total", len(QUESTIONS))
