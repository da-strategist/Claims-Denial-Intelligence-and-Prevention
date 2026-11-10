"""Payer documents the organisation uploads: provider manuals, prior authorization lists, policy
bulletins. They're the evidence behind payer-specific rules: a rule can cite a document and page,
and the assistant searches them and cites them by page.

Each organisation keeps its own (payers often license manuals to in-network providers only), in
its folder: `payer_documents.json` lists them, and `payer_documents/` holds each file and the
text read from each of its pages. Payer documents carry no patient information, but contract
terms can be confidential, so all of it is encrypted with the organisation's key like its PHI.
"""

import io
import json
import re
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from app.data.knowledge import Source
from app.data.orgs import org_cipher_for, org_file
from app.data.secure_files import read_bytes, read_text, write_bytes, write_text
from app.models import SourceType

DOCUMENTS_FILE = "payer_documents.json"
DOCUMENTS_FOLDER = "payer_documents"
MAX_BYTES = 15 * 1024 * 1024
MAX_PAGES = 1000
# A plain-text document has no pages: it's read in parts of about this many characters
TEXT_PART_CHARS = 3000

MEDIA_TYPES = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/plain"}


class DocumentError(ValueError):
    """A file that can't be used: wrong type, too large, or unreadable."""


class PayerDocument(BaseModel):
    id: str = Field(pattern=r"^DOC-\d{3,}$")
    payer_id: str
    title: str
    effective_date: date | None = None
    filename: str
    media_type: str
    size_bytes: int
    pages: int = Field(description="Pages of a PDF, or parts of a text file")
    pages_with_text: int = Field(description="Pages the assistant can search (0 for a scanned PDF)")
    uploaded_at: datetime
    uploaded_by: str


def media_type_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise DocumentError("Upload a PDF or a text file (.pdf, .txt or .md)")
    return MEDIA_TYPES[suffix]


def _pieces(text: str) -> list[str]:
    """Paragraphs; a paragraph too long for one part is split by line, then by length."""
    pieces = []
    for paragraph in text.split("\n\n"):
        if len(paragraph) <= TEXT_PART_CHARS:
            pieces.append(paragraph + "\n\n")
            continue
        for line in paragraph.split("\n"):
            for start in range(0, max(len(line), 1), TEXT_PART_CHARS):
                pieces.append(line[start : start + TEXT_PART_CHARS] + "\n")
    return pieces


def _text_parts(text: str) -> list[str]:
    """A text file in parts of about TEXT_PART_CHARS, broken between paragraphs or lines."""
    parts, current = [], ""
    for piece in _pieces(text.replace("\r\n", "\n")):
        if current and len(current) + len(piece) > TEXT_PART_CHARS:
            parts.append(current.strip())
            current = ""
        current += piece
    if current.strip():
        parts.append(current.strip())
    return parts or [""]


def read_pages(data: bytes, media_type: str) -> list[str]:
    """The text of each page (or part). A page with no text, e.g. a scan, is an empty string."""
    if media_type == "text/plain":
        try:
            return _text_parts(data.decode("utf-8-sig"))
        except UnicodeDecodeError:
            raise DocumentError("The text file isn't UTF-8 text") from None
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentError("The PDF is password-protected; upload an unprotected copy")
        if len(reader.pages) > MAX_PAGES:
            raise DocumentError(f"The PDF has more than {MAX_PAGES} pages")
        return [" ".join((page.extract_text() or "").split()) for page in reader.pages]
    except DocumentError:
        raise
    except Exception as err:  # pypdf raises many kinds of error on damaged files
        raise DocumentError("The PDF can't be read") from err


class PayerDocumentStore:
    def __init__(self, path: Path | None = None, cipher: Fernet | None = None) -> None:
        self.path = path
        self.folder = path.parent / DOCUMENTS_FOLDER if path else None
        self._cipher = cipher
        self._documents: dict[str, PayerDocument] = {}
        self._pages: dict[str, list[str]] = {}  # in memory only when there's no path (tests)
        self._content: dict[str, bytes] = {}
        self._next_number = 1
        self._lock = Lock()
        self.version = 0  # changes whenever a document is added or removed
        if path is not None and path.exists():
            saved = json.loads(read_text(path, cipher))
            self._documents = {d["id"]: PayerDocument.model_validate(d) for d in saved["documents"]}
            self._next_number = saved["next_number"]

    # --- Reading -------------------------------------------------------------------

    def all(self) -> list[PayerDocument]:
        with self._lock:
            return sorted(self._documents.values(), key=lambda d: (d.payer_id, d.title.lower()))

    def get(self, document_id: str) -> PayerDocument | None:
        return self._documents.get(document_id)

    def content(self, document_id: str) -> bytes:
        if self.folder is None:
            return self._content[document_id]
        return read_bytes(self.folder / f"{document_id}.file", self._cipher)

    def pages(self, document_id: str) -> list[str]:
        if self.folder is None:
            return self._pages[document_id]
        return json.loads(read_text(self.folder / f"{document_id}.pages.json", self._cipher))

    # --- Changing ------------------------------------------------------------------

    def add(
        self, payer_id: str, title: str, effective_date: date | None, filename: str, data: bytes, by: str
    ) -> PayerDocument:
        media_type = media_type_for(filename)
        if not title.strip():
            raise DocumentError("Give the document a title")
        if not data:
            raise DocumentError("The file is empty")
        if len(data) > MAX_BYTES:
            raise DocumentError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB")
        pages = read_pages(data, media_type)
        with self._lock:
            document = PayerDocument(
                id=f"DOC-{self._next_number:03d}",
                payer_id=payer_id,
                title=title.strip(),
                effective_date=effective_date,
                filename=Path(filename).name,
                media_type=media_type,
                size_bytes=len(data),
                pages=len(pages),
                pages_with_text=sum(1 for page in pages if page.strip()),
                uploaded_at=datetime.now(UTC),
                uploaded_by=by,
            )
            if self.folder is None:
                self._content[document.id], self._pages[document.id] = data, pages
            else:
                self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
                stored = self._cipher.encrypt(data) if self._cipher else data
                write_bytes(self.folder / f"{document.id}.file", stored)
                write_text(self.folder / f"{document.id}.pages.json", json.dumps(pages), self._cipher)
            self._next_number += 1
            self._documents[document.id] = document
            self._save()
            self.version += 1
            return document

    def remove(self, document_id: str) -> bool:
        with self._lock:
            if self._documents.pop(document_id, None) is None:
                return False
            self._save()
            if self.folder is None:
                self._content.pop(document_id, None)
                self._pages.pop(document_id, None)
            else:
                for name in (f"{document_id}.file", f"{document_id}.pages.json"):
                    (self.folder / name).unlink(missing_ok=True)
            self.version += 1
            return True

    def _save(self) -> None:
        """Caller holds the lock. Document IDs are never reused."""
        if self.path is None:
            return
        payload = {
            "next_number": self._next_number,
            "documents": [d.model_dump(mode="json") for d in self._documents.values()],
        }
        write_text(self.path, json.dumps(payload, indent=2), self._cipher)


# Codes a page mentions, so a claim's own codes find the pages about them
_CPT = re.compile(r"\b(\d{5}|[A-Z]\d{4})\b")
SOURCE_TEXT_CHARS = 6000


def document_sources(store: PayerDocumentStore) -> list[Source]:
    """One assistant source per page with text, keyed by the payer and the codes it names."""
    sources = []
    for document in store.all():
        if not document.pages_with_text:
            continue
        unit = "page" if document.media_type == "application/pdf" else "part"
        effective = f", effective {document.effective_date.isoformat()}" if document.effective_date else ""
        for number, text in enumerate(store.pages(document.id), start=1):
            if not text.strip():
                continue
            codes = set(_CPT.findall(text))
            sources.append(
                Source(
                    SourceType.PAYER_DOCUMENT,
                    f"{document.id} p.{number}",
                    f"{document.title}, {unit} {number}",
                    f"From {document.title} ({document.filename}{effective}), {unit} {number} of "
                    f"{document.pages}: {text[:SOURCE_TEXT_CHARS]}",
                    frozenset({f"payer:{document.payer_id}", *(f"cpt:{code}" for code in codes)}),
                    {"payer_id": document.payer_id, "document_id": document.id, "page": number, "codes": codes},
                )
            )
    return sources


@lru_cache(maxsize=None)
def get_payer_documents(org_id: str) -> PayerDocumentStore:
    return PayerDocumentStore(org_file(org_id, DOCUMENTS_FILE), org_cipher_for(org_id))
