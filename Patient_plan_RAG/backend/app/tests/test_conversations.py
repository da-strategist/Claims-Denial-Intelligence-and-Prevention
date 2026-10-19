"""Multi-turn chat: conversation store, follow-up retrieval, and the API flow."""

import re
from pathlib import Path

import pytest

from backend.app.services import conversations
from backend.app.services.conversations import ConversationStore, Turn
from backend.app.services.document_processor import chunk_text, extract_text_from_pdf
from backend.app.services.rag import retrieval_query
from backend.app.services.retrieval import retrieve

POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"


# ── Store ────────────────────────────────────────────────────────────

def test_same_id_returns_same_conversation_and_keeps_policy():
    store = ConversationStore()
    conv = store.get_or_create(None, "pol1")
    assert store.get_or_create(conv.id, None) is conv
    assert store.get_or_create(conv.id, "pol1") is conv
    assert conv.policy_id == "pol1"


def test_unknown_id_or_policy_switch_starts_new_conversation():
    store = ConversationStore()
    conv = store.get_or_create(None, "pol1")
    assert store.get_or_create("doesnotexist", "pol1").id not in (conv.id, "doesnotexist")
    assert store.get_or_create(conv.id, "pol2").id != conv.id


def test_turns_are_capped():
    store = ConversationStore(max_turns=3)
    conv = store.get_or_create(None, None)
    for i in range(5):
        store.add_turn(conv, f"q{i}", f"a{i}")
    assert [t.question for t in conv.turns] == ["q2", "q3", "q4"]


def test_idle_conversations_expire(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(conversations.time, "monotonic", lambda: now[0])
    store = ConversationStore(ttl_seconds=60)
    conv = store.get_or_create(None, None)
    now[0] += 61
    assert store.get_or_create(conv.id, None).id != conv.id


def test_oldest_conversations_are_evicted():
    store = ConversationStore(max_conversations=2)
    first = store.get_or_create(None, None)
    store.get_or_create(None, None)
    store.get_or_create(None, None)
    assert store.get_or_create(first.id, None).id != first.id


# ── Follow-up retrieval ──────────────────────────────────────────────

def test_referring_follow_up_includes_previous_question():
    history = [Turn("Is physical therapy covered?", "...")]
    assert retrieval_query("How many visits does it include?", history) == \
        "Is physical therapy covered? How many visits does it include?"


@pytest.mark.parametrize("question", ["What about acupuncture?", "Is hospice covered?"])
def test_self_contained_question_is_searched_as_is(question):
    assert retrieval_query(question, [Turn("Is an MRI covered?", "...")]) == question


def test_no_history_means_no_change():
    assert retrieval_query("Does it need approval?", []) == "Does it need approval?"


# (policy, first question, follow-up, phrase the follow-up's top hit must contain)
# Each follow-up fails without the conversation context (checked below).
FOLLOW_UPS = [
    ("apex_health_gold_ppo_2025.pdf", "Are hearing aids covered?",
     "Is that the case for children too?", "Hearing aids for adults over age 18"),
    ("apex_health_gold_ppo_2025.pdf", "What does the plan pay for skilled nursing?",
     "How many days does it cover?", "limited to 60 days per calendar year"),
    ("summit_care_silver_hmo_2026.pdf", "Is physical therapy covered?",
     "How many visits does it include?", "up to 20 combined visits"),
]


def _norm(s):
    return re.sub(r"\s+", " ", s)


@pytest.mark.parametrize("policy,first,follow_up,phrase", FOLLOW_UPS)
def test_context_makes_follow_up_find_the_answer(policy, first, follow_up, phrase):
    if not (POLICY_DIR / policy).exists():
        pytest.skip(f"{policy} missing")
    chunks = chunk_text(extract_text_from_pdf(POLICY_DIR / policy), "x")

    def top_has_phrase(query):
        hits = retrieve(query, chunks, 1)
        return bool(hits) and _norm(phrase) in _norm(hits[0][0].content)

    assert not top_has_phrase(follow_up), "case no longer needs context; pick another"
    assert top_has_phrase(retrieval_query(follow_up, [Turn(first, "")]))


# ── API ──────────────────────────────────────────────────────────────

def _ask(client, question, **kw):
    return client.post("/api/chat", json={"question": question, **kw}).json()


def test_conversation_id_is_reused_and_policy_remembered(client, doc_id):
    first = _ask(client, "Are hearing aids covered?", policy_id=doc_id)
    follow = _ask(client, "Is that the case for children too?",
                  conversation_id=first["conversation_id"])
    assert follow["conversation_id"] == first["conversation_id"]
    assert {c["document_id"] for c in follow["citations"]} == {doc_id}
    assert follow["citations"][0]["section"] == "EXCLUSIONS AND LIMITATIONS"
    assert follow["disclaimer"]


def test_new_conversation_each_time_without_id(client):
    a = _ask(client, "Is acupuncture covered?")["conversation_id"]
    b = _ask(client, "Is acupuncture covered?")["conversation_id"]
    assert a != b


def test_unknown_conversation_id_gets_a_fresh_one(client):
    resp = _ask(client, "Is acupuncture covered?", conversation_id="stale1234567")
    assert resp["conversation_id"] != "stale1234567"


def test_history_is_stored_server_side(client, doc_id):
    cid = _ask(client, "Is an MRI covered?", policy_id=doc_id)["conversation_id"]
    _ask(client, "Does it need prior authorization?", conversation_id=cid)
    conv = conversations.store.get_or_create(cid, None, owner="admin@example.com")
    assert [t.question for t in conv.turns] == [
        "Is an MRI covered?", "Does it need prior authorization?"]
