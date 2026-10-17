"""Validation status and risk score for every claim, cached between requests.

Validating all 120K claims takes about a second, so the result is kept until the
rules or the corrections overlay change.
"""

from functools import lru_cache
from threading import Lock

import pandas as pd

from app.data import ClaimsRepository
from app.models import Rule
from app.services.validation_engine import validate_claims


class StatusSnapshot:
    def __init__(self) -> None:
        self._key: tuple | None = None
        self._frame: pd.DataFrame | None = None
        self._lock = Lock()

    def get(self, claims: ClaimsRepository, rules: list[Rule]) -> pd.DataFrame:
        """Frame indexed by claim_id with `status` and `risk_score` columns, for every claim
        in the organisation (a ScopedClaims passes its whole organisation's repository; the
        callers then only look up the claims they can see)."""
        claims = getattr(claims, "base", claims)
        key = (
            id(claims),
            claims.version,
            tuple((rule.id, rule.updated_at, rule.enabled) for rule in rules),
        )
        with self._lock:
            if key != self._key or self._frame is None:
                results = validate_claims(claims.claims_frame(), rules)
                self._frame = pd.DataFrame(
                    {
                        "status": [result.status.value for result in results],
                        "risk_score": [result.risk_score for result in results],
                    },
                    index=pd.Index([result.claim_id for result in results], name="claim_id"),
                )
                self._key = key
            return self._frame


@lru_cache(maxsize=None)
def get_status_snapshot(org_id: str) -> StatusSnapshot:
    """The organisation's cached validation of every claim."""
    return StatusSnapshot()
