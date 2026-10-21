"""A question naming a plan ("…under Bronze HDHP 7000?") searches that plan
only, without its name pulling the title page to the top."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.services import rag
from backend.app.tests.conftest import POLICY_PDF, sign_in

NORTHWIND = POLICY_PDF.parent / "northwind_bronze_hdhp_2026.pdf"


def _upload(client, path):
    with path.open("rb") as f:
        r = client.post("/api/policies/upload", files={"file": (path.name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["document_id"]


@pytest.fixture
def alice(data_dirs):
    if not NORTHWIND.exists():
        pytest.skip("northwind policy missing")
    c = sign_in(TestClient(main.app), "alice@example.com")
    return c, _upload(c, POLICY_PDF), _upload(c, NORTHWIND)


def test_focus_on_named_plan_narrows_and_strips_the_name(alice):
    _, apex, northwind = alice
    query, doc = rag.focus_on_named_plan("What needs prior authorization under Bronze HDHP 7000?",
                                         None, {apex, northwind})
    assert (query.strip(), doc) == ("What needs prior authorization under ?", northwind)
    # no plan named: unchanged
    assert rag.focus_on_named_plan("What is my deductible?", None, {apex, northwind}) == \
        ("What is my deductible?", None)
    # a plan outside the user's scope is not matched
    assert rag.focus_on_named_plan("Bronze HDHP 7000?", None, {apex})[1] is None


def test_starter_style_question_is_answered_from_the_approval_section(alice):
    client, apex, northwind = alice
    question = "What needs prior authorization under Bronze HDHP 7000?"  # as the starters word it
    r = client.post("/api/chat", json={"question": question}).json()
    assert {c["document_id"] for c in r["citations"]} == {northwind}
    assert "PRECERTIFICATION" in r["citations"][0]["section"]
