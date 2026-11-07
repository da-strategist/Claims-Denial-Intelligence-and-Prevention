"""Payer documents: uploaded per organisation, cited by rules, shown on flagged claims and in
AI Fix, and searched by the assistant."""

import base64
import io
import zipfile

from reportlab.pdfgen import canvas

from app.data.audit import get_audit_log
from app.data.org_lifecycle import export_organisation
from app.models import Role
from app.tests.conftest import org_folder, sign_in
from app.tests.test_claim_entry import create

DOCS = "/api/payer-documents"
MANUAL = (
    "Medicare provider manual.\n\n"
    "Office visits (CPT 99213) billed with a chronic condition need the condition documented "
    "in the visit note.\n\n"
    "Claims must be filed within 365 days of the date of service."
)


def pdf(*pages: str) -> bytes:
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    for text in pages:
        page.drawString(72, 720, text)
        page.showPage()
    page.save()
    return buffer.getvalue()


def upload(client, data: bytes = MANUAL.encode(), filename="manual.txt", **changes):
    body = {
        "payer_id": "PAY001",
        "title": "Medicare provider manual",
        "effective_date": "2026-01-01",
        "filename": filename,
        "content": base64.b64encode(data).decode(),
        **changes,
    }
    return client.post(DOCS, json=body)


def rule_citing(client, document_id, page=1, **changes):
    body = {
        "name": "Medicare chronic condition note",
        "category": "Payer-Specific",
        "severity": "warning",
        "scope": {"type": "payer", "values": ["PAY001"]},
        "conditions": [{"field": "total_charge", "operator": "greaterThan", "value": "0"}],
        "recommended_action": "Check the visit note documents the condition",
        "source": {"document_id": document_id, "page": page, "excerpt": "  need the condition documented  "},
        **changes,
    }
    return client.post("/api/rules", json=body)


# ----- Uploading and reading ---------------------------------------------------------------


def test_a_text_document_is_listed_downloaded_and_read_by_part(client):
    created = upload(client)
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["id"] == "DOC-001"
    assert document["media_type"] == "text/plain"
    assert document["pages"] == document["pages_with_text"] == 1
    assert document["uploaded_by"] == "admin1"
    assert [d["id"] for d in client.get(DOCS).json()] == ["DOC-001"]
    downloaded = client.get(f"{DOCS}/DOC-001/file")
    assert downloaded.content == MANUAL.encode()
    assert "manual.txt" in downloaded.headers["content-disposition"]
    assert "365 days" in client.get(f"{DOCS}/DOC-001/pages/1").json()["text"]
    assert client.get(f"{DOCS}/DOC-001/pages/2").status_code == 404


def test_a_pdf_is_read_page_by_page(client):
    document = upload(client, pdf("Cover page", "Prior authorization is required for CPT 70553"), "manual.pdf").json()
    assert (document["media_type"], document["pages"]) == ("application/pdf", 2)
    assert "70553" in client.get(f"{DOCS}/{document['id']}/pages/2").json()["text"]


def test_a_long_text_file_is_split_into_parts(client):
    paragraphs = "\n\n".join(f"Paragraph {n}. " + "word " * 200 for n in range(10))
    assert upload(client, paragraphs.encode()).json()["pages"] > 1


def test_unusable_uploads_are_refused(client):
    assert upload(client, payer_id="PAY999").status_code == 422
    assert upload(client, payer_id="PAY010").status_code == 422  # self-pay
    assert upload(client, filename="manual.docx").status_code == 422
    assert upload(client, b"").status_code == 422
    assert upload(client, b"not a pdf", "manual.pdf").status_code == 422
    bad = client.post(DOCS, json={"payer_id": "PAY001", "title": "x", "filename": "a.txt", "content": "%%%"})
    assert bad.status_code == 422
    assert client.get(DOCS).json() == []


def test_only_rule_editors_upload_or_delete_but_everyone_reads(anon_client):
    admin = sign_in(anon_client, Role.ADMIN)
    upload(admin)
    analyst = sign_in(anon_client, Role.ANALYST)
    assert analyst.get(DOCS).status_code == 200
    assert analyst.get(f"{DOCS}/DOC-001/file").status_code == 200
    assert upload(analyst).status_code == 403
    assert analyst.delete(f"{DOCS}/DOC-001").status_code == 403
    biller = sign_in(anon_client, Role.BILLER)
    assert upload(biller).status_code == 403


def test_documents_are_encrypted_at_rest(client):
    upload(client)
    stored = org_folder() / "payer_documents"
    assert b"365 days" not in (stored / "DOC-001.file").read_bytes()
    assert b"365 days" not in (stored / "DOC-001.pages.json").read_bytes()
    assert b"Medicare provider manual" not in (org_folder() / "payer_documents.json").read_bytes()


def test_uploads_are_audited_and_exported(client):
    upload(client)
    event = [e for e in get_audit_log("meridian").events() if e.action == f"POST {DOCS}"][-1]
    assert event.detail["document_id"] == "DOC-001"
    data, manifest = export_organisation("meridian", "admin1")
    paths = [f["path"] for f in manifest["files"]]
    assert "app/payer_documents.json" in paths
    assert "app/payer_documents/DOC-001-manual.txt" in paths
    assert zipfile.ZipFile(io.BytesIO(data)).read("app/payer_documents/DOC-001-manual.txt") == MANUAL.encode()


# ----- Rules that cite a document -----------------------------------------------------------


def test_a_rule_cites_a_document_page(client):
    upload(client)
    rule = rule_citing(client, "DOC-001")
    assert rule.status_code == 201, rule.text
    assert rule.json()["source"] == {
        "document_id": "DOC-001",
        "page": 1,
        "excerpt": "need the condition documented",
        "document_title": "Medicare provider manual",
    }


def test_a_rule_cant_cite_a_missing_document_or_page(client):
    upload(client)
    assert rule_citing(client, "DOC-009").status_code == 422
    assert rule_citing(client, "DOC-001", page=5).status_code == 422


def test_a_cited_document_cant_be_deleted_until_the_rule_lets_go(client):
    upload(client)
    rule_id = rule_citing(client, "DOC-001").json()["id"]
    refused = client.delete(f"{DOCS}/DOC-001")
    assert refused.status_code == 409
    assert rule_id in refused.json()["detail"]
    patched = client.patch(f"/api/rules/{rule_id}", json={"source": None})
    assert patched.json()["source"] is None
    assert client.delete(f"{DOCS}/DOC-001").status_code == 204
    assert client.get(DOCS).json() == []
    assert client.get(f"{DOCS}/DOC-001/file").status_code == 404


def test_a_flagged_claim_and_its_fix_show_the_source(client, today):
    upload(client)
    rule_id = rule_citing(client, "DOC-001").json()["id"]
    created = create(client).json()
    finding = next(f for f in created["validation"]["findings"] if f["rule_id"] == rule_id)
    assert finding["source"]["document_title"] == "Medicare provider manual"
    assert finding["source"]["page"] == 1
    fixes = client.get(f"/api/aifix/{created['claim']['claim_id']}").json()
    suggestion = next(s for s in fixes["suggestions"] if s["rule_id"] == rule_id)
    cited = [c for c in suggestion["citations"] if c["source_type"] == "payer_document"]
    assert cited == [
        {
            "source_type": "payer_document",
            "reference_id": "DOC-001 p.1",
            "title": "Medicare provider manual, page 1",
            "excerpt": "need the condition documented",
        }
    ]


# ----- The assistant ------------------------------------------------------------------------


def ask(client, question, **body):
    return client.post("/api/assistant", json={"question": question, **body}).json()


def test_the_assistant_finds_the_page_for_the_claims_payer(client, today):
    upload(client, pdf("Cover page", "Claims must be filed within 365 days of the date of service"), "manual.pdf")
    claim_id = create(client).json()["claim"]["claim_id"]
    answer = ask(client, "What is the timely filing limit for claims?", claim_id=claim_id)
    pages = [s for s in answer["sources"] if s["source_type"] == "payer_document"]
    assert pages and pages[0]["reference_id"] == "DOC-001 p.2"
    assert pages[0]["title"] == "Medicare provider manual, page 2"


def test_another_payers_document_isnt_used(client, today):
    upload(client, payer_id="PAY002", title="Blue Cross manual")
    claim_id = create(client).json()["claim"]["claim_id"]  # billed to PAY001
    answer = ask(client, "How many days do we have to file claims?", claim_id=claim_id)
    assert not [s for s in answer["sources"] if s["source_type"] == "payer_document"]


def test_a_new_document_is_searchable_at_once_and_gone_when_deleted(client):
    question = "What does Medicare FFS say about filing claims within 365 days?"
    assert not [s for s in ask(client, question)["sources"] if s["source_type"] == "payer_document"]
    upload(client)
    assert [s for s in ask(client, question)["sources"] if s["source_type"] == "payer_document"]
    client.delete(f"{DOCS}/DOC-001")
    assert not [s for s in ask(client, question)["sources"] if s["source_type"] == "payer_document"]


def test_a_scanned_pdf_is_kept_but_has_nothing_to_search(client):
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.rect(72, 600, 200, 100)  # a drawing, no text
    page.showPage()
    page.save()
    document = upload(client, buffer.getvalue(), "scan.pdf").json()
    assert (document["pages"], document["pages_with_text"]) == (1, 0)
