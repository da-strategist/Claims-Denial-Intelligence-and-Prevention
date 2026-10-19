"""Which documents a user may see.

- admin: every document
- member: staff plans assigned to them (owner is None and the ID is in
  user.plan_ids) plus documents they uploaded themselves (owner == username)

A document the user may not see is reported as "not found", exactly like a
missing one, so members cannot probe for other plans' IDs.
"""

from fastapi import HTTPException

from .users import Role, User


def can_access(user: User, entry: dict) -> bool:
    if user.role is Role.ADMIN:
        return True
    owner = entry.get("owner")
    if owner is not None:
        return owner == user.username
    return entry["document_id"] in user.plan_ids


def accessible_ids(user: User, registry: list[dict]) -> set[str]:
    return {e["document_id"] for e in registry if can_access(user, e)}


def entry_or_404(user: User, registry: list[dict], document_id: str) -> dict:
    for entry in registry:
        if entry["document_id"] == document_id and can_access(user, entry):
            return entry
    raise HTTPException(404, "Document not found")
