"""Payer documents: the evidence behind payer-specific rules (data/payer_documents.py).

Everyone who can see claims can read them; administrators (rules:write) upload and delete
them. Uploads, downloads and deletions are in the audit log, by document ID.
"""

import base64
import binascii
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.data.payer_documents import DocumentError, PayerDocument
from app.models import PayerType, Permission
from app.models.common import PayerId
from app.services.auth import SignedIn, audit_note, require
from app.services.org_context import OrgClaims, OrgPayerDocuments, OrgRules

router = APIRouter(
    prefix="/api/payer-documents", tags=["payer documents"], dependencies=[require(Permission.CLAIMS_READ)]
)

WRITE = [require(Permission.RULES_WRITE)]
DocumentId = str


class DocumentUpload(BaseModel):
    payer_id: PayerId
    title: str = Field(min_length=1, max_length=150)
    effective_date: date | None = None
    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(description="The file's bytes, base64-encoded")


class DocumentPage(BaseModel):
    document_id: str
    page: int
    pages: int
    text: str


def _found(documents, document_id: str) -> PayerDocument:
    document = documents.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return document


@router.get("", response_model=list[PayerDocument])
def list_documents(documents: OrgPayerDocuments) -> list[PayerDocument]:
    return documents.all()


@router.post("", response_model=PayerDocument, status_code=status.HTTP_201_CREATED, dependencies=WRITE)
def upload_document(
    body: DocumentUpload, documents: OrgPayerDocuments, repo: OrgClaims, user: SignedIn, request: Request
) -> PayerDocument:
    """Add a payer's document (PDF or text, up to 15 MB). Its text is read page by page so
    rules can cite a page and the assistant can search it."""
    payer = repo.get_payer(body.payer_id)
    if payer is None:
        raise HTTPException(status_code=422, detail=f"Unknown payer {body.payer_id}")
    if payer.payer_type == PayerType.SELF_PAY:
        raise HTTPException(status_code=422, detail="Self-pay isn't a payer with documents")
    try:
        data = base64.b64decode(body.content, validate=True)
    except (binascii.Error, ValueError) as err:
        raise HTTPException(status_code=422, detail="The file's content isn't valid base64") from err
    try:
        document = documents.add(body.payer_id, body.title, body.effective_date, body.filename, data, user.username)
    except DocumentError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    audit_note(request, document_id=document.id, payer_id=document.payer_id, pages=document.pages)
    return document


@router.get("/{document_id}", response_model=PayerDocument)
def get_document(document_id: DocumentId, documents: OrgPayerDocuments) -> PayerDocument:
    return _found(documents, document_id)


@router.get("/{document_id}/file")
def download_document(document_id: DocumentId, documents: OrgPayerDocuments, request: Request) -> Response:
    document = _found(documents, document_id)
    audit_note(request, document_id=document.id)
    return Response(
        content=documents.content(document_id),
        media_type=document.media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}"},
    )


@router.get("/{document_id}/pages/{page}", response_model=DocumentPage)
def read_page(document_id: DocumentId, page: int, documents: OrgPayerDocuments) -> DocumentPage:
    """The text read from one page, e.g. to copy the passage a rule is based on."""
    document = _found(documents, document_id)
    if not 1 <= page <= document.pages:
        raise HTTPException(status_code=404, detail=f"{document_id} has pages 1 to {document.pages}")
    return DocumentPage(
        document_id=document_id, page=page, pages=document.pages, text=documents.pages(document_id)[page - 1]
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete_document(
    document_id: DocumentId, documents: OrgPayerDocuments, rules: OrgRules, request: Request
) -> None:
    """Delete a document, unless a rule still cites it."""
    _found(documents, document_id)
    citing = sorted(rule.id for rule in rules.list() if rule.source and rule.source.document_id == document_id)
    if citing:
        raise HTTPException(
            status_code=409,
            detail=f"{', '.join(citing)} {'cites' if len(citing) == 1 else 'cite'} this document. "
            "Remove it from the rule's source first.",
        )
    documents.remove(document_id)
    audit_note(request, document_id=document_id)
