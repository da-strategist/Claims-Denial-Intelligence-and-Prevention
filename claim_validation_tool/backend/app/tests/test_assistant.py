"""Clarification assistant: what's shared, what's retrieved, and how answers cite sources.

CLM0000002 (PAT000002, PAY002 Blue Cross NC, denied) bills CPT 99284 and 43239 (upper GI
endoscopy) for K21.0, which LCD-L33631 covers, and was denied with CARC 197 / RARC N362.
"""

from types import SimpleNamespace

import pytest

from app.data.knowledge import KnowledgeBase
from app.main import app
from app.models import AssistantMode, ClaimFacts, ClarificationTopic
from app.services import assistant
from app.services.assistant import (
    NO_SOURCES,
    AssistantUnavailable,
    ClaudeWriter,
    Retriever,
    build_prompt,
    claim_facts,
    cited_labels,
    get_answer_writer,
    scrub_question,
)
from app.data.repository import DEFAULT_DATA_DIR
from app.evals.assistant import evaluate
from app.evals.assistant_cases import CASES
from app.tests.conftest import FIXTURES_DIR

CLAIM = "CLM0000002"


@pytest.fixture(scope="module")
def retriever():
    return Retriever(KnowledgeBase.load(FIXTURES_DIR))


def facts(**changes) -> ClaimFacts:
    base = {
        "claim_type": "Professional",
        "place_of_service": "11",
        "service_month": "2025-03",
        "status": "Draft",
        "payer_id": "PAY001",
        "payer_name": "Medicare FFS",
        "payer_type": "Medicare",
        "primary_icd10": "I10",
        "lines": [],
        "total_charge": 100.0,
        "total_paid": 0.0,
        "days_in_ar": 0,
        "pa_required": False,
        "pa_obtained": False,
        "has_pa_number": False,
    }
    return ClaimFacts(**{**base, **changes})


def line(cpt, units=1, category="E&M", icd10="I10"):
    return {
        "cpt_code": cpt,
        "cpt_category": category,
        "modifier": None,
        "units": units,
        "charge_amount": 100.0,
        "icd10_pointer": icd10,
    }


def ranked(matches):
    return [m.source.reference_id for m in matches]


# --- What's shared ----------------------------------------------------------------------


def test_claim_facts_share_codes_and_amounts_only(repo):
    claim = repo.get_claim(CLAIM)
    shared = claim_facts(claim)
    assert [(l.cpt_code, l.icd10_pointer) for l in shared.lines] == [
        ("99284", "K21.0"),
        ("43239", "K21.0"),
    ]
    assert (shared.service_month, shared.payer_name) == ("2025-02", "Blue Cross NC")
    assert [(d.carc_code, d.rarc_code) for d in shared.denials] == [("197", "N362")]

    prompt = build_prompt("Why was this denied?", shared, [])
    identifiers = [
        claim.claim_id,
        claim.patient_id,
        claim.provider_id,
        claim.provider.provider_name,
        claim.provider.npi,
        claim.patient.first_name,
        claim.patient.last_name,
        claim.patient.zip_code,
        str(claim.service_date),
        str(claim.submission_date),
        "denial_reason_text",
        "age",
        "gender",
    ]
    leaked = [value for value in identifiers if value and value in prompt]
    assert leaked == []


def test_questions_are_scrubbed_of_identifiers():
    question = "PAT000002 claim CLM0000002 seen 2025-02-15 (also 2/15/25), NPI 1000000002?"
    assert scrub_question(question) == (
        "[patient] claim [claim] seen [date] (also [date]), NPI [number]?"
    )


# --- Retrieval -----------------------------------------------------------------------------


def test_medical_necessity_finds_the_coverage_policy_for_the_claim(repo, retriever):
    shared = claim_facts(repo.get_claim(CLAIM))
    matches = retriever.retrieve(
        "Is this procedure medically necessary?", shared, ClarificationTopic.MEDICAL_NECESSITY
    )
    top = matches[0]
    assert top.source.reference_id == "LCD-L33631"
    assert top.reason == "Covers billed CPT 43239; claim diagnosis K21.0 is on its covered list"


def test_uncovered_diagnosis_is_called_out(retriever):
    shared = facts(lines=[line("43239", category="Surgery", icd10="I10")])
    topic = ClarificationTopic.MEDICAL_NECESSITY
    [top, *_] = retriever.retrieve("medical necessity", shared, topic)
    assert top.source.reference_id == "LCD-L33631"
    assert "none of the claim's diagnoses (I10) are on its covered list" in top.reason


def test_appeal_starts_from_the_denial_codes(repo, retriever):
    shared = claim_facts(repo.get_claim(CLAIM))
    matches = retriever.retrieve("Draft appeal wording", shared, ClarificationTopic.APPEAL)
    assert ranked(matches)[:2] == ["197", "N362"]
    assert matches[0].reason == "On the claim's denial"


def test_prior_auth_brings_the_payer_and_its_contracts(repo, retriever):
    shared = claim_facts(repo.get_claim(CLAIM))
    matches = retriever.retrieve(
        "What are this payer's authorization terms?", shared, ClarificationTopic.PAYER_PRIOR_AUTH
    )
    # The payer, the authorization denial codes, then its contracts for the billed services
    assert ranked(matches)[:5] == ["PAY002", "N362", "197", "CON0004", "CON0003"]
    assert "PAY001" not in ranked(matches)  # another payer's profile doesn't apply


def test_ncci_edit_when_both_codes_are_billed(retriever):
    shared = facts(lines=[line("43239", category="Surgery"), line("43235", category="Surgery")])
    [top, *_] = retriever.retrieve("Can these be billed together?", shared)
    assert top.source.reference_id == "PTP0013"
    assert top.reason == "The claim bills both CPT 43239 and 43235"


def test_units_over_the_mue_limit(retriever):
    shared = facts(lines=[line("99213", units=3)])
    matches = retriever.retrieve("Units?", shared, ClarificationTopic.NCCI_MODIFIERS)
    assert matches[0].source.reference_id == "MUE0001"
    assert matches[0].reason == "The claim bills 3 units of CPT 99213; the limit is 1"


def test_codes_named_in_a_question_without_a_claim(retriever):
    matches = retriever.retrieve("Can 93458 and 93000 be billed on the same day with modifier 59?")
    assert matches[0].source.reference_id == "PTP0010"
    assert matches[0].reason.startswith("Named in the question: 93000, 93458")
    carc = retriever.retrieve("What does CO-197 mean?")
    assert carc[0].source.reference_id == "197"


def test_a_named_payer_brings_the_contract_for_the_service_asked_about(retriever):
    matches = retriever.retrieve("What does Blue Cross NC pay for surgery?")
    # Its other contracts (E&M, Lab) rank after the payer profile
    assert ranked(matches) == ["CON0004", "PAY002", "CON0005", "CON0003"]
    assert matches[0].reason == "Named in the question: PAY002, Surgery"
    assert matches[2].reason == "Contract of PAY002, named in the question"


def test_keyword_search_for_free_typed_questions(retriever):
    matches = retriever.retrieve("total knee arthroplasty conservative treatment")
    assert matches[0].source.reference_id == "LCD-L33789"
    assert matches[0].reason == "Matches the question's wording"


def test_unrelated_question_retrieves_nothing(retriever):
    assert retriever.retrieve("hello there") == []


# --- Answers ------------------------------------------------------------------------------


def test_cited_labels_accept_grouped_citations():
    assert cited_labels("Denied [S1]. See [S2, S4] and [S3;S5]. Not [X1].") == {
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
    }


def ask(client, **body):
    return client.post("/api/assistant", json={"question": "Why was this claim denied?", **body})


def test_without_an_api_key_the_sources_are_returned(client):
    res = ask(client, claim_id=CLAIM, topic="appeal")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "retrieval"
    assert body["model"] is None
    assert "ANTHROPIC_API_KEY" in body["notice"]
    assert [s["reference_id"] for s in body["sources"][:2]] == ["197", "N362"]
    assert all(s["cited"] for s in body["sources"])  # the summary cites each one
    assert body["claim_facts"]["payer_name"] == "Blue Cross NC"
    assert "patient_id" not in body["claim_facts"]


class FakeClaude:
    mode = AssistantMode.CLAUDE
    model = "claude-test"

    def __init__(self, answer="Authorization was missing [S1][S2]. Appeal with the auth [S1]."):
        self.answer = answer
        self.prompts = []

    def write(self, question, facts, sources):
        self.prompts.append(build_prompt(question, facts, sources))
        return self.answer


@pytest.fixture
def fake_claude():
    writer = FakeClaude()
    app.dependency_overrides[get_answer_writer] = lambda: writer
    yield writer
    app.dependency_overrides.pop(get_answer_writer)


def test_claude_answers_from_the_retrieved_sources(client, fake_claude):
    body = ask(client, claim_id=CLAIM, topic="appeal", question="Why denied? PAT000002").json()
    assert (body["mode"], body["model"], body["notice"]) == ("claude", "claude-test", None)
    assert body["question"] == "Why denied? [patient]"
    assert [s["label"] for s in body["sources"] if s["cited"]] == ["S1", "S2"]
    [prompt] = fake_claude.prompts
    assert "[S1] CARC 197: Precertification/authorization absent" in prompt
    assert "PAT000002" not in prompt and "Karen" not in prompt


def test_falls_back_to_sources_when_claude_is_unreachable(client, fake_claude):
    def fail(*args):
        raise AssistantUnavailable("overloaded")

    fake_claude.write = fail
    body = ask(client, claim_id=CLAIM).json()
    assert body["mode"] == "retrieval"
    assert body["notice"] == (
        "Claude couldn't be reached (overloaded), so these are the matching sources."
    )
    assert body["answer"].startswith("The most relevant reference records")


def test_no_matching_source_skips_the_llm(client, fake_claude):
    body = ask(client, question="hello there").json()
    assert body["answer"] == NO_SOURCES
    assert body["sources"] == []
    assert fake_claude.prompts == []


def test_request_errors(client):
    assert ask(client, claim_id="CLM9999999").status_code == 404
    assert ask(client, question="?").status_code == 422
    assert ask(client, topic="billing").status_code == 422


def test_status_reports_mode_and_knowledge_base(client):
    body = client.get("/api/assistant/status").json()
    assert (body["mode"], body["model"]) == ("retrieval", None)
    assert body["sources"]["ncci_edit"] == 43
    assert body["sources"]["carc"] == 3


# --- Claude client ---------------------------------------------------------------------------


class FakeMessages:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", text="ignored"),
                SimpleNamespace(type="text", text=" CARC 197 means no authorization [S1]. "),
            ]
        )


def test_claude_writer_sends_system_prompt_and_numbered_sources(repo, retriever):
    writer = ClaudeWriter(model="claude-sonnet-5-5", api_key="test-key")
    writer._client = SimpleNamespace(messages=FakeMessages())
    shared = claim_facts(repo.get_claim(CLAIM))
    topic = ClarificationTopic.APPEAL
    result = assistant.answer_question("Why denied?", shared, topic, retriever, writer)

    assert result.answer == "CARC 197 means no authorization [S1]."
    assert (result.mode, result.model) == ("claude", "claude-sonnet-5-5")
    [call] = writer._client.messages.calls
    assert call["model"] == "claude-sonnet-5-5"
    assert "Answer using ONLY the numbered reference sources" in call["system"]
    content = call["messages"][0]["content"]
    assert content.index("<claim_facts>") < content.index("<sources>") < content.index("<question>")


def test_claude_writer_reports_api_errors_as_unavailable(retriever):
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    writer = ClaudeWriter(api_key="test-key")
    writer._client = SimpleNamespace(
        messages=FakeMessages(anthropic.APIConnectionError(request=request))
    )
    result = assistant.answer_question("What does CARC 197 mean?", None, None, retriever, writer)
    assert result.mode == "retrieval"
    assert result.notice.startswith("Claude couldn't be reached (Connection error.)")


# --- Evaluation set ------------------------------------------------------------------------


@pytest.mark.skipif(
    not (DEFAULT_DATA_DIR / "ref_ncci_ptp_edits.csv").exists(), reason="needs Data/raw_data"
)
def test_eval_set_retrieves_every_expected_source():
    """The retrieval half of `python -m app.evals.assistant`, against the real tables."""
    retriever = Retriever(KnowledgeBase.load(DEFAULT_DATA_DIR))
    results = [evaluate(case, retriever, None) for case in CASES]
    misses = {r.case.id: r.retrieved for r in results if not r.recall}
    assert misses == {}
