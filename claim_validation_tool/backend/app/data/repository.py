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
        "days_to_denial": "int64",
    },
}

# 0/1 flag columns, loaded as real booleans
_BOOL_COLUMNS: dict[str, list[str]] = {
    "fact_claims": ["is_clean_claim", "pa_required", "pa_obtained"],
    "fact_denials": ["is_preventable"],
}


def _read_table(data_dir: Path, name: str) -> pd.DataFrame:
    df = pd.read_csv(data_dir / f"{name}.csv", dtype=str, keep_default_na=False)
    df = df.astype(_NUMERIC_COLUMNS.get(name, {}))
    for column in _BOOL_COLUMNS.get(name, []):
        df[column] = df[column].astype("int64").astype(bool)
    return df


class ClaimsRepository:
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        self.data_dir = data_dir
        self._claims = _read_table(data_dir, "fact_claims")
        self._lines = _read_table(data_dir, "fact_claim_lines")
        self._denials = _read_table(data_dir, "fact_denials")

        # Derived columns used by validation rules and risk scoring
        self._claims["days_to_submission"] = (
            pd.to_datetime(self._claims["submission_date"])
            - pd.to_datetime(self._claims["service_date"])
        ).dt.days
        self._add_prior_denial_flags()

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

    def claims_frame(self, claim_ids: list[str] | None = None) -> pd.DataFrame:
        """Typed claim rows (plus derived columns) for the validation engine.

        With `claim_ids`, returns those claims in the order given, skipping unknown IDs.
        Without, returns every claim. Callers must not mutate the result.
        """
        if claim_ids is None:
            return self._claims
        positions = self._claim_pos(claim_ids)
        return self._claims.iloc[positions[positions != -1]]

    def missing_claim_ids(self, claim_ids: list[str]) -> list[str]:
        positions = self._claim_pos(claim_ids)
        return [claim_id for claim_id, pos in zip(claim_ids, positions) if pos == -1]

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

    def _add_prior_denial_flags(self) -> None:
        """Flag claims whose patient had a denial issued before this claim was submitted.

        Only denials known at submission time count, so a claim's own denial (always
        dated after its submission) never feeds its own risk score.
        """
        denials = self._denials.merge(
            self._claims[["claim_id", "patient_id"]], on="claim_id", how="inner"
        )
        for column, rows in (
            ("has_prior_denial", denials),
            ("has_prior_preventable_denial", denials[denials["is_preventable"]]),
        ):
            first_denial = rows.groupby("patient_id")["denial_date"].min()
            first_for_claim = self._claims["patient_id"].map(first_denial)
            # ISO dates compare correctly as text; patients with no denials map to NaN -> False
            self._claims[column] = (
                first_for_claim.notna() & (first_for_claim < self._claims["submission_date"])
            )

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
            mask &= df["is_clean_claim"] == q.is_clean_claim
        if q.missing_prior_auth is not None:
            missing = df["pa_required"] & ~df["pa_obtained"]
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
