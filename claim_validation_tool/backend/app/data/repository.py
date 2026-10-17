"""In-memory data access layer backed by the synthetic CSVs in Data/raw_data/.

Tables are loaded once into pandas DataFrames. Filtering, sorting, and pagination
run on the DataFrames; only the rows being returned are converted to Pydantic
models, so listing a page of claims never materializes all 120K records.
"""

import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd

from app.data.corrections import get_correction_store
from app.data.new_claims import NewClaimStore, get_new_claim_store
from app.models.aifix import CORRECTABLE_FIELDS
from app.models.rule import RULE_FIELDS, parse_condition_value
from app.models import (
    AT_RISK_STATUSES,
    EdiFile,
    Claim,
    ClaimDetail,
    ClaimLine,
    ClaimQuery,
    ClaimStatus,
    Denial,
    Department,
    Facility,
    Page,
    Patient,
    PatientQuery,
    PatientSummary,
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


def _today() -> date:
    """Today's date; a function so tests can pin it."""
    return date.today()


def _read_table(data_dir: Path, name: str) -> pd.DataFrame:
    df = pd.read_csv(data_dir / f"{name}.csv", dtype=str, keep_default_na=False)
    df = df.astype(_NUMERIC_COLUMNS.get(name, {}))
    for column in _BOOL_COLUMNS.get(name, []):
        df[column] = df[column].astype("int64").astype(bool)
    return df


class ClaimsRepository:
    def __init__(
        self, data_dir: Path = DEFAULT_DATA_DIR, new_claims: NewClaimStore | None = None
    ) -> None:
        """`new_claims` saves claims entered in the app; they are replayed here on startup."""
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

        # Only manually entered claims can be pending, or carry more than one diagnosis
        # or payer on the header; the source data is single-payer and adjudicated
        self._claims["is_overdue"] = False
        self._claims["additional_icd10"] = ""
        self._claims["other_payer_ids"] = ""
        self._pending_ids: set[str] = set()
        self._draft_ids: set[str] = set()
        # What claims entered in the app carry beyond the source columns (billing details
        # and line revenue codes for the 837), and the 837 each was submitted with
        self._billing: dict[str, dict[str, Any]] = {}
        self._revenue_codes: dict[str, list[str | None]] = {}
        self._edi: dict[str, EdiFile] = {}

        # AI Fix corrections are layered over these columns; keep the originals to restore
        self._claims["has_corrections"] = False
        self._original = self._claims[list(CORRECTABLE_FIELDS)].copy()
        self._corrected_ids: set[str] = set()
        self._overlay_lock = Lock()
        # Bumped whenever the overlay changes, so caches of claim-derived results can expire
        self.version = 0

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
        self._departments = [
            Department.model_validate(row)
            for row in _read_table(data_dir, "dim_departments").to_dict("records")
        ]
        self._facilities = {
            row["facility_id"]: Facility.model_validate(row)
            for row in _read_table(data_dir, "dim_facilities").to_dict("records")
        }

        # Registered patients. Claims can only be entered for these.
        self._patients = _read_table(data_dir, "dim_patients")
        self._patients["search_name"] = (
            self._patients["first_name"] + " " + self._patients["last_name"]
        ).str.lower()
        self._patient_pos = pd.Index(self._patients["patient_id"]).get_indexer
        self._claims_per_patient = self._claims["patient_id"].value_counts()
        self._denials_per_patient = self._denials["claim_id"].map(
            self._claims.set_index("claim_id")["patient_id"]
        ).value_counts()
        primary_payer = self._patients.set_index("patient_id")["primary_payer_id"]
        claim_primary = self._claims["patient_id"].map(primary_payer)
        self._claims["payer_is_patient_primary"] = self._claims["payer_id"] == claim_primary
        # Billed to the primary, or listing it as other coverage (secondary billing)
        self._claims["patient_primary_on_claim"] = self._claims["payer_is_patient_primary"] | pd.Series(
            [
                primary in others.split("|")
                for primary, others in zip(claim_primary, self._claims["other_payer_ids"])
            ],
            index=self._claims.index,
        )

        # Claims entered in the app, replayed in order with the dates they were submitted
        self._new_claims = None
        for record in (new_claims.records() if new_claims else []):
            claim_id = record["fields"]["claim_id"]
            self.add_claim(record["fields"], record["lines"])
            if record["submitted_on"]:
                self.submit_claim(claim_id, on=date.fromisoformat(record["submitted_on"]))
            if record.get("edi"):
                self._edi[claim_id] = EdiFile.model_validate(record["edi"]["summary"])
        self._new_claims = new_claims

    # --- Corrections overlay ------------------------------------------------

    def apply_overrides(self, overrides: dict[str, dict[str, str]]) -> None:
        """Layer corrected field values ({claim_id: {field: value}}) over the source claims.

        Replaces any previous overlay: claims no longer in `overrides` get their
        original values back. Values are strings, typed per the rule field catalog.
        """
        with self._overlay_lock:
            for claim_id in self._corrected_ids - overrides.keys():
                pos = self._claim_pos([claim_id])[0]
                if pos == -1:
                    continue
                for field in CORRECTABLE_FIELDS:
                    self._claims.loc[pos, field] = self._original.loc[pos, field]
                self._claims.loc[pos, "has_corrections"] = False
            for claim_id, fields in overrides.items():
                pos = self._claim_pos([claim_id])[0]
                if pos == -1:
                    continue
                for field in CORRECTABLE_FIELDS:
                    value: Any = self._original.loc[pos, field]
                    if field in fields:
                        value = parse_condition_value(RULE_FIELDS[field], fields[field])
                    self._claims.loc[pos, field] = value
                self._claims.loc[pos, "has_corrections"] = True
            self._corrected_ids = set(overrides)
            self.version += 1

    # --- Claims -------------------------------------------------------------

    def list_claims(self, query: ClaimQuery, statuses: pd.DataFrame | None = None) -> Page[Claim]:
        """`statuses` (StatusSnapshot: status and risk_score by claim_id) is needed to filter
        on `needs_attention` or sort by `risk_score`."""
        self._age_open_claims()
        df = self._filter_claims(query)
        if statuses is not None:
            df = df.assign(risk_score=df["claim_id"].map(statuses["risk_score"]).fillna(0))
            if query.needs_attention is not None:
                at_risk = df["claim_id"].map(statuses["status"]).isin(AT_RISK_STATUSES)
                df = df[at_risk if query.needs_attention else ~at_risk]
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
        self._age_open_claims()
        pos = self._claim_pos([claim_id])[0]
        if pos == -1:
            return None
        row = self._claims.iloc[pos].to_dict()
        lines = self._rows(self._lines, self._lines_by_claim.get(claim_id))
        denials = self._rows(self._denials, self._denials_by_claim.get(claim_id))
        lines = sorted(lines, key=lambda line: line["line_number"])
        for line, revenue_code in zip(lines, self._revenue_codes.get(claim_id, [])):
            line["revenue_code"] = revenue_code
        return ClaimDetail.model_validate(
            {
                **row,
                "lines": lines,
                "denials": denials,
                "patient": self._patient(row["patient_id"]),
                "payer": self._payers.get(row["payer_id"]),
                "provider": self._providers.get(row["provider_id"]),
                "billing": self._billing.get(claim_id),
                "edi": self._edi.get(claim_id),
            }
        )

    def claims_frame(self, claim_ids: list[str] | None = None) -> pd.DataFrame:
        """Typed claim rows (plus derived columns) for the validation engine.

        With `claim_ids`, returns those claims in the order given, skipping unknown IDs.
        Without, returns every claim. Callers must not mutate the result.
        """
        self._age_open_claims()
        if claim_ids is None:
            return self._claims
        positions = self._claim_pos(claim_ids)
        return self._claims.iloc[positions[positions != -1]]

    def add_claim(self, fields: dict[str, Any], lines: list[dict[str, Any]]) -> ClaimDetail:
        """Append a new claim and its service lines to the in-memory data.

        `fields` holds every fact_claims column (dates as ISO strings; additional_icd10
        and other_payer_ids as lists). `lines` hold cpt_code, cpt_category, modifier,
        units, charge_amount, and icd10_pointer; IDs and numbering are assigned here.
        With a NewClaimStore the claim is saved, so it survives restarts. Raises ValueError
        if the claim_id is taken or the patient isn't registered.
        """
        claim_id = fields["claim_id"]
        patient = self._patient(fields["patient_id"])
        if patient is None:
            raise ValueError(f"Patient {fields['patient_id']} is not registered")
        prior, prior_preventable = self._prior_denials(
            fields["patient_id"], fields["submission_date"]
        )
        row = {
            **fields,
            "pa_number": fields.get("pa_number") or "",  # source data stores blanks as ""
            "additional_icd10": "|".join(fields.get("additional_icd10", [])),
            "other_payer_ids": "|".join(fields.get("other_payer_ids", [])),
            "days_to_submission": (
                date.fromisoformat(fields["submission_date"])
                - date.fromisoformat(fields["service_date"])
            ).days,
            "has_prior_denial": prior,
            "has_prior_preventable_denial": prior_preventable,
            "payer_is_patient_primary": fields["payer_id"] == patient.primary_payer_id,
            "patient_primary_on_claim": patient.primary_payer_id
            in [fields["payer_id"], *fields.get("other_payer_ids", [])],
            "has_corrections": False,
            "is_overdue": False,
        }
        with self._overlay_lock:
            if self._claim_pos([claim_id])[0] != -1:
                raise ValueError(f"Claim {claim_id} already exists")
            new = pd.DataFrame([row], columns=self._claims.columns).astype(
                self._claims.dtypes.to_dict()
            )
            self._claims = pd.concat([self._claims, new], ignore_index=True)
            self._original = pd.concat(
                [self._original, new[list(CORRECTABLE_FIELDS)]], ignore_index=True
            )
            self._claim_pos = pd.Index(self._claims["claim_id"]).get_indexer
            self._append_lines(claim_id, lines)
            self._claims_per_patient[fields["patient_id"]] = (
                self._claims_per_patient.get(fields["patient_id"], 0) + 1
            )
            if fields["status"] == ClaimStatus.PENDING:
                self._pending_ids.add(claim_id)
            elif fields["status"] == ClaimStatus.DRAFT:
                self._draft_ids.add(claim_id)
            self.version += 1
        if fields.get("billing"):
            self._billing[claim_id] = fields["billing"]
        self._revenue_codes[claim_id] = [line.get("revenue_code") for line in lines]
        if self._new_claims is not None:
            self._new_claims.add(fields, lines)
        claim = self.get_claim(claim_id)
        assert claim is not None
        return claim

    def submission_frame(self, claim_id: str) -> pd.DataFrame:
        """The claim as it would be if submitted today, for the final rule check.

        A draft carries its planned submission date; the rules must judge the date it
        actually goes out (e.g. Timely Filing Risk), and the denials known by then.
        """
        today = _today()
        frame = self.claims_frame([claim_id]).copy()
        if frame.empty:
            return frame
        row = frame.iloc[0]
        frame["submission_date"] = today.isoformat()
        frame["days_to_submission"] = (today - date.fromisoformat(row["service_date"])).days
        frame["days_in_ar"] = 0
        prior, prior_preventable = self._prior_denials(row["patient_id"], today.isoformat())
        frame["has_prior_denial"] = prior
        frame["has_prior_preventable_denial"] = prior_preventable
        return frame

    def submit_claim(
        self,
        claim_id: str,
        on: date | None = None,
        edi: tuple[str, EdiFile] | None = None,
    ) -> ClaimDetail:
        """Mark a Draft as submitted `on` a date (today by default): it becomes Pending and
        starts aging in AR.

        Raises LookupError for an unknown claim, ValueError if it isn't a Draft or its
        service date is still in the future.
        """
        day = on or _today()
        with self._overlay_lock:
            pos = self._claim_pos([claim_id])[0]
            if pos == -1:
                raise LookupError(f"Claim {claim_id} not found")
            row = self._claims.iloc[pos]
            if row["status"] != ClaimStatus.DRAFT:
                raise ValueError(f"Only draft claims can be submitted; {claim_id} is {row['status']}")
            if row["service_date"] > day.isoformat():
                raise ValueError("A claim can't be submitted before its service date")
            self._claims.loc[pos, "status"] = ClaimStatus.PENDING.value
            self._claims.loc[pos, "submission_date"] = day.isoformat()
            self._claims.loc[pos, "days_to_submission"] = (
                day - date.fromisoformat(row["service_date"])
            ).days
            self._claims.loc[pos, "days_in_ar"] = 0
            prior, prior_preventable = self._prior_denials(row["patient_id"], day.isoformat())
            self._claims.loc[pos, "has_prior_denial"] = prior
            self._claims.loc[pos, "has_prior_preventable_denial"] = prior_preventable
            self._draft_ids.discard(claim_id)
            self._pending_ids.add(claim_id)
            self.version += 1
        if edi is not None:
            self._edi[claim_id] = edi[1]
        if self._new_claims is not None and on is None:
            saved = {"text": edi[0], "summary": edi[1].model_dump(mode="json")} if edi else None
            self._new_claims.mark_submitted(claim_id, day, saved)
        claim = self.get_claim(claim_id)
        assert claim is not None
        return claim

    def next_control_number(self) -> int:
        """Interchange control number for the next 837 (1, 2, … without a store)."""
        if self._new_claims is not None:
            return self._new_claims.next_control_number()
        self._control = getattr(self, "_control", 0) + 1
        return self._control

    def edi_text(self, claim_id: str) -> str | None:
        """The 837 a claim was submitted with, if it was submitted from the app."""
        return self._new_claims.edi_text(claim_id) if self._new_claims is not None else None

    def denials_frame(self) -> pd.DataFrame:
        """All denials, unfiltered. Treat as read-only."""
        return self._denials

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

    def list_departments(self) -> list[Department]:
        return self._departments

    def list_facilities(self) -> list[Facility]:
        return list(self._facilities.values())

    def get_facility(self, facility_id: str) -> Facility | None:
        return self._facilities.get(facility_id)

    # --- Patients -----------------------------------------------------------

    def list_patients(self, query: PatientQuery) -> Page[PatientSummary]:
        """Registered patients matching an ID prefix or every word of the search."""
        df = self._patients
        order = ["last_name", "first_name", "patient_id"]
        term = (query.search or "").strip().lower()
        if re.fullmatch(r"pat\d*", term):  # an ID, not a name like "Patricia"
            df = df[df["patient_id"].str.lower().str.startswith(term)]
            order = ["patient_id"]
        elif term:
            mask = pd.Series(True, index=df.index)
            for word in term.split():
                mask &= df["search_name"].str.contains(word, regex=False)
            df = df[mask]
        df = df.sort_values(order)
        start = (query.page - 1) * query.page_size
        rows = df.iloc[start : start + query.page_size]
        return Page[PatientSummary](
            items=[self._patient_summary(row) for row in rows.to_dict("records")],
            total=len(df),
            page=query.page,
            page_size=query.page_size,
        )

    def get_patient(self, patient_id: str) -> PatientSummary | None:
        pos = self._patient_pos([patient_id])[0]
        if pos == -1:
            return None
        return self._patient_summary(self._patients.iloc[pos].to_dict())

    def person_names(self) -> list[tuple[str, str]]:
        """(first, last) names of every patient and provider, for masking them in free text."""
        names = list(zip(self._patients["first_name"], self._patients["last_name"]))
        for provider in self._providers.values():
            words = [w for w in provider.provider_name.split() if w.rstrip(".") not in ("Dr", provider.credential)]
            if len(words) >= 2:
                names.append((words[0], words[-1]))
        return names

    # --- Internals ----------------------------------------------------------

    def _patient(self, patient_id: str) -> Patient | None:
        pos = self._patient_pos([patient_id])[0]
        return None if pos == -1 else Patient.model_validate(self._patients.iloc[pos].to_dict())

    def _patient_summary(self, row: dict[str, Any]) -> PatientSummary:
        patient_id = row["patient_id"]
        return PatientSummary.model_validate(
            {
                **row,
                "claim_count": int(self._claims_per_patient.get(patient_id, 0)),
                "denial_count": int(self._denials_per_patient.get(patient_id, 0)),
            }
        )

    def _prior_denials(self, patient_id: str, submission_date: str) -> tuple[bool, bool]:
        """(any, any preventable) denial of this patient's claims issued before `submission_date`."""
        claim_ids = self._claims.loc[self._claims["patient_id"] == patient_id, "claim_id"]
        denials = self._denials[self._denials["claim_id"].isin(claim_ids)]
        earlier = denials[denials["denial_date"] < submission_date]
        return bool(len(earlier)), bool(earlier["is_preventable"].any())

    def _append_lines(self, claim_id: str, lines: list[dict[str, Any]]) -> None:
        """Add a new claim's service lines. Caller holds the overlay lock."""
        next_number = int(self._lines["line_id"].str.removeprefix("LN").astype("int64").max()) + 1
        rows = [
            {
                **line,
                "line_id": f"LN{next_number + index:08d}",
                "claim_id": claim_id,
                "line_number": index + 1,
                "modifier": line.get("modifier") or "",
                "allowed_amount": 0.0,
                "paid_amount": 0.0,
            }
            for index, line in enumerate(lines)
        ]
        new = pd.DataFrame(rows, columns=self._lines.columns).astype(self._lines.dtypes.to_dict())
        self._lines = pd.concat([self._lines, new], ignore_index=True)
        self._lines_by_claim = self._lines.groupby("claim_id", sort=False).indices

    def _age_open_claims(self) -> None:
        """Bring drafts and pending claims up to today; runs before every read.

        A draft whose planned submission date has passed can now go out no earlier than
        today, so its days to submission (and the denials known by then) move with the
        calendar. Pending claims age in AR and turn overdue. Only those rows are touched,
        and `version` is bumped only when a value actually changes.
        """
        if not self._pending_ids and not self._draft_ids:
            return
        today = _today()
        with self._overlay_lock:
            changed = self._age_drafts(today)
            changed = self._age_pending(today) or changed
            if changed:
                self.version += 1

    def _age_drafts(self, today: date) -> bool:
        """Move past planned submission dates up to today. Caller holds the lock."""
        if not self._draft_ids:
            return False
        rows = self._claims.iloc[self._claim_pos(sorted(self._draft_ids))]
        late = rows[rows["submission_date"] < today.isoformat()]
        for index, row in late.iterrows():
            prior, prior_preventable = self._prior_denials(row["patient_id"], today.isoformat())
            self._claims.loc[index, "submission_date"] = today.isoformat()
            self._claims.loc[index, "days_to_submission"] = (
                today - date.fromisoformat(row["service_date"])
            ).days
            self._claims.loc[index, "has_prior_denial"] = prior
            self._claims.loc[index, "has_prior_preventable_denial"] = prior_preventable
        return not late.empty

    def _age_pending(self, today: date) -> bool:
        """Days in AR and the overdue flag for pending claims. Caller holds the lock."""
        if not self._pending_ids:
            return False
        positions = self._claim_pos(sorted(self._pending_ids))
        rows = self._claims.iloc[positions]
        days = rows["submission_date"].map(
            lambda submitted: max((today - date.fromisoformat(submitted)).days, 0)
        )
        limits = rows["payer_id"].map(
            lambda payer_id: self._payers[payer_id].avg_days_to_pay
            if payer_id in self._payers
            else None
        )
        overdue = limits.notna() & (days > limits.fillna(0))
        if days.equals(rows["days_in_ar"]) and overdue.equals(rows["is_overdue"]):
            return False
        self._claims.loc[rows.index, "days_in_ar"] = days.astype("int64")
        self._claims.loc[rows.index, "is_overdue"] = overdue.astype(bool)
        return True

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
        if not q.include_drafts:
            mask &= df["status"] != ClaimStatus.DRAFT
        if q.is_clean_claim is not None:
            mask &= df["is_clean_claim"] == q.is_clean_claim
        if q.overdue is not None:
            mask &= df["is_overdue"] == q.overdue
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
    repo = ClaimsRepository(data_dir, get_new_claim_store())
    corrections = get_correction_store()
    # Drop corrections whose claim no longer exists (e.g. the new-claims file was removed),
    # so a new claim reusing the ID doesn't inherit them
    for claim_id in repo.missing_claim_ids(list(corrections.overrides())):
        corrections.clear_claim(claim_id)
    repo.apply_overrides(corrections.overrides())
    return repo
