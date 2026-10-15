"""In-memory data access layer backed by the synthetic CSVs in Data/raw_data/.

Tables are loaded once into pandas DataFrames. Filtering, sorting, and pagination
run on the DataFrames; only the rows being returned are converted to Pydantic
models, so listing a page of claims never materializes all 120K records.
"""

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.models import (
    Claim,
    ClaimDetail,
    ClaimLine,
    ClaimQuery,
    Denial,
    Page,
    Payer,
    Provider,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = PROJECT_ROOT / "Data" / "raw_data"

# Columns cast away from str so they can be filtered and sorted numerically.
# Date columns stay as ISO-8601 strings, which compare and sort correctly as text.
_NUMERIC_COLUMNS: dict[str, dict[str, str]] = {
    "fact_claims": {
        "total_charge": "float64",
        "total_allowed": "float64",
        "total_paid": "float64",
        "patient_responsibility": "float64",
        "days_in_ar": "int64",
        "is_clean_claim": "int64",
        "pa_required": "int64",
        "pa_obtained": "int64",
    },
    "fact_claim_lines": {
        "line_number": "int64",
        "units": "int64",
        "charge_amount": "float64",
        "allowed_amount": "float64",
        "paid_amount": "float64",
    },
    "fact_denials": {
        "denial_amount": "float64",
        "is_preventable": "int64",
        "days_to_denial": "int64",
    },
}


def _read_table(data_dir: Path, name: str) -> pd.DataFrame:
    df = pd.read_csv(data_dir / f"{name}.csv", dtype=str, keep_default_na=False)
    return df.astype(_NUMERIC_COLUMNS.get(name, {}))


class ClaimsRepository:
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        self.data_dir = data_dir
        self._claims = _read_table(data_dir, "fact_claims")
        self._lines = _read_table(data_dir, "fact_claim_lines")
        self._denials = _read_table(data_dir, "fact_denials")

        self._claim_pos = pd.Index(self._claims["claim_id"]).get_indexer
        self._lines_by_claim = self._lines.groupby("claim_id", sort=False).indices
        self._denials_by_claim = self._denials.groupby("claim_id", sort=False).indices

        self._payers = {
            row["payer_id"]: Payer.model_validate(row)
            for row in _read_table(data_dir, "dim_payers").to_dict("records")
        }
        self._providers = {
            row["provider_id"]: Provider.model_validate(row)
            for row in _read_table(data_dir, "dim_providers").to_dict("records")
        }

    # --- Claims -------------------------------------------------------------

    def list_claims(self, query: ClaimQuery) -> Page[Claim]:
        df = self._filter_claims(query)
        df = df.sort_values(
            [query.sort_by, "claim_id"],
            ascending=[not query.sort_desc, True],
            kind="stable",
        )
        start = (query.page - 1) * query.page_size
        rows = df.iloc[start : start + query.page_size].to_dict("records")
        return Page[Claim](
            items=[Claim.model_validate(row) for row in rows],
            total=len(df),
            page=query.page,
            page_size=query.page_size,
        )

    def get_claim(self, claim_id: str) -> ClaimDetail | None:
        pos = self._claim_pos([claim_id])[0]
        if pos == -1:
            return None
        row = self._claims.iloc[pos].to_dict()
        lines = self._rows(self._lines, self._lines_by_claim.get(claim_id))
        denials = self._rows(self._denials, self._denials_by_claim.get(claim_id))
        return ClaimDetail.model_validate(
            {
                **row,
                "lines": sorted(lines, key=lambda line: line["line_number"]),
                "denials": denials,
                "payer": self._payers.get(row["payer_id"]),
                "provider": self._providers.get(row["provider_id"]),
            }
        )

    def get_claim_lines(self, claim_id: str) -> list[ClaimLine]:
        rows = self._rows(self._lines, self._lines_by_claim.get(claim_id))
        return [ClaimLine.model_validate(row) for row in rows]

    def get_denials(self, claim_id: str) -> list[Denial]:
        rows = self._rows(self._denials, self._denials_by_claim.get(claim_id))
        return [Denial.model_validate(row) for row in rows]

    # --- Reference data -----------------------------------------------------

    def list_payers(self) -> list[Payer]:
        return list(self._payers.values())

    def get_payer(self, payer_id: str) -> Payer | None:
        return self._payers.get(payer_id)

    def list_providers(self) -> list[Provider]:
        return list(self._providers.values())

    def get_provider(self, provider_id: str) -> Provider | None:
        return self._providers.get(provider_id)

    # --- Internals ----------------------------------------------------------

    @staticmethod
    def _rows(df: pd.DataFrame, positions) -> list[dict]:
        if positions is None:
            return []
        return df.iloc[positions].to_dict("records")

    def _filter_claims(self, q: ClaimQuery) -> pd.DataFrame:
        df = self._claims
        mask = pd.Series(True, index=df.index)

        if q.search:
            term = q.search.strip()
            mask &= (
                df["claim_id"].str.contains(term, case=False, regex=False)
                | df["patient_id"].str.contains(term, case=False, regex=False)
                | df["primary_icd10"].str.contains(term, case=False, regex=False)
            )
        for column in ("payer_id", "provider_id", "department_id", "status", "claim_type"):
            value = getattr(q, column)
            if value is not None:
                mask &= df[column] == value
        if q.is_clean_claim is not None:
            mask &= df["is_clean_claim"] == int(q.is_clean_claim)
        if q.missing_prior_auth is not None:
            missing = (df["pa_required"] == 1) & (df["pa_obtained"] == 0)
            mask &= missing if q.missing_prior_auth else ~missing
        if q.service_date_from is not None:
            mask &= df["service_date"] >= q.service_date_from.isoformat()
        if q.service_date_to is not None:
            mask &= df["service_date"] <= q.service_date_to.isoformat()
        if q.min_charge is not None:
            mask &= df["total_charge"] >= q.min_charge
        if q.max_charge is not None:
            mask &= df["total_charge"] <= q.max_charge

        return df[mask]


@lru_cache(maxsize=1)
def get_repository() -> ClaimsRepository:
    """Process-wide repository, usable as a FastAPI dependency."""
    data_dir = Path(os.environ.get("RCM_DATA_DIR", DEFAULT_DATA_DIR))
    return ClaimsRepository(data_dir)
