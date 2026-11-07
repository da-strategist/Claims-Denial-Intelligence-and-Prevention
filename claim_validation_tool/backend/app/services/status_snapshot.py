"""Validation status and risk score for every claim, cached between requests.

Validating all 120K claims takes about a second (far longer on a small shared CPU), so
it is done once; after that only the claims that changed are validated again. A rule
change, or a cache too far behind the claims, validates everything.
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
        self._version = 0
        self._frame: pd.DataFrame | None = None
        self._lock = Lock()

    def get(self, claims: ClaimsRepository, rules: list[Rule]) -> pd.DataFrame:
        """Frame indexed by claim_id with `status` and `risk_score` columns, for every claim
        in the organisation (a ScopedClaims passes its whole organisation's repository; the
        callers then only look up the claims they can see)."""
        claims = getattr(claims, "base", claims)
        key = (id(claims), tuple((rule.id, rule.updated_at, rule.enabled) for rule in rules))
        with self._lock:
            if self._frame is not None and key == self._key:
                version, changed = claims.changed_since(self._version)
                if changed is not None:
                    if changed:
                        self._frame = _updated(self._frame, claims.claims_frame(sorted(changed)), rules)
                    self._version = version
                    return self._frame
            every = claims.claims_frame()  # brings open claims up to date first
            # A change while validating is picked up next time
            version = claims.version
            self._frame = _frame(validate_claims(every, rules))
            self._key, self._version = key, version
            return self._frame


def _frame(results: list) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "status": [result.status.value for result in results],
            "risk_score": [result.risk_score for result in results],
        },
        index=pd.Index([result.claim_id for result in results], name="claim_id"),
    )


def _updated(frame: pd.DataFrame, changed: pd.DataFrame, rules: list[Rule]) -> pd.DataFrame:
    """`frame` with the changed claims validated again (new claims added at the end).
    A new frame, since callers may still hold the old one."""
    update = _frame(validate_claims(changed, rules))
    known = update.index.isin(frame.index)
    frame = frame.copy()
    frame.loc[update.index[known]] = update[known]
    return pd.concat([frame, update[~known]]) if (~known).any() else frame


@lru_cache(maxsize=None)
def get_status_snapshot(org_id: str) -> StatusSnapshot:
    """The organisation's cached validation of every claim."""
    return StatusSnapshot()
