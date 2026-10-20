"""In-memory conversation history for multi-turn chat.

History is kept server-side (not sent by the client) so it only ever holds
what this app actually said; in live mode a client-supplied history could
inject forged assistant turns into the model's context.

Prototype-grade, like rate_limit.py: state is per process and lost on
restart. Conversations expire after TTL_SECONDS idle and the oldest are
evicted beyond MAX_CONVERSATIONS.
"""

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

MAX_CONVERSATIONS = 500
MAX_TURNS = 10
TTL_SECONDS = 3600


@dataclass
class Turn:
    question: str
    answer: str


@dataclass
class Conversation:
    id: str
    policy_id: str | None
    owner: str | None = None
    patient_id: str | None = None
    turns: list[Turn] = field(default_factory=list)
    updated: float = field(default_factory=lambda: time.monotonic())


class ConversationStore:
    def __init__(self, max_conversations=MAX_CONVERSATIONS, max_turns=MAX_TURNS,
                 ttl_seconds=TTL_SECONDS):
        self.max_conversations = max_conversations
        self.max_turns = max_turns
        self.ttl = ttl_seconds
        self._items: OrderedDict[str, Conversation] = OrderedDict()

    def _expire(self) -> None:
        now = time.monotonic()
        for cid in [c.id for c in self._items.values() if now - c.updated > self.ttl]:
            del self._items[cid]

    def get_or_create(self, conversation_id: str | None, policy_id: str | None,
                      owner: str | None = None, patient_id: str | None = None) -> Conversation:
        """The live conversation for this ID, else a new one with a fresh ID.

        A conversation belongs to the user who started it (someone else's ID
        starts a new conversation) and stays scoped to one policy and one
        patient: switching either starts a new conversation rather than
        mixing two plans or two patients.
        """
        self._expire()
        conv = self._items.get(conversation_id or "")
        if (conv and conv.owner == owner and conv.patient_id == patient_id
                and (policy_id is None or policy_id == conv.policy_id)):
            self._items.move_to_end(conv.id)
            return conv
        conv = Conversation(id=uuid.uuid4().hex[:12], policy_id=policy_id, owner=owner,
                            patient_id=patient_id)
        self._items[conv.id] = conv
        while len(self._items) > self.max_conversations:
            self._items.popitem(last=False)
        return conv

    def add_turn(self, conv: Conversation, question: str, answer: str) -> None:
        conv.turns.append(Turn(question, answer))
        del conv.turns[:-self.max_turns]
        conv.updated = time.monotonic()

    def reset(self) -> None:
        self._items.clear()


store = ConversationStore()
