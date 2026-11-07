"""Coding checks on service lines (NCCI edits, MUE limits, LCD/NCD coverage, and whether a
line's diagnosis fits its procedure): findings on claims entered here, with AI Fix
suggestions that name the lines and the reference record."""

import json

from app.data.coding_edits import CodingEdits, icd10_chapter
from app.data.rules import RuleRepository
from app.data.seed_rules import CODING_RULES, DEFAULT_RULES, MISMATCH_RULES, SEED_VERSION
from app.tests.conftest import FIXTURES_DIR
from app.tests.test_claim_entry import create

EDITS = CodingEdits.load(FIXTURES_DIR)


def line(cpt, modifier="", units=1, dx=None):
    return {"cpt_code": cpt, "modifier": modifier, "units": units, "icd10_pointer": dx}


NO_FLAGS = {
    "ncci_conflict": False,
    "mue_exceeded": False,
    "diagnosis_not_covered": False,
    "diagnosis_procedure_mismatch": False,
}


def rule_names(res) -> set[str]:
    return {f["rule_name"] for f in res.json()["validation"]["findings"]}


# --- The checks ----------------------------------------------------------------


def test_ncci_pair_on_one_claim_is_a_conflict_on_the_column_2_line():
    result = EDITS.check([line("99284"), line("99283")], ["I10"], "2026-01-05")
    [conflict] = result.ncci
    assert (conflict.edit_id, conflict.column_2_cpt, conflict.line_number) == ("PTP0003", "99283", 2)
    assert not conflict.modifier_allowed
    assert result.flags() == {**NO_FLAGS, "ncci_conflict": True}


def test_a_distinct_service_modifier_bypasses_only_edits_that_allow_one():
    # 93458 / 93000 has modifier indicator 1
    assert EDITS.check([line("93458"), line("93000")], ["I48.91"], "2026-01-05").ncci
    assert not EDITS.check([line("93458"), line("93000", "59")], ["I48.91"], "2026-01-05").ncci
    assert not EDITS.check([line("93458"), line("93000", "xs")], ["I48.91"], "2026-01-05").ncci
    assert EDITS.check([line("93458"), line("93000", "25")], ["I48.91"], "2026-01-05").ncci
    # 99284 / 99283 has indicator 0: nothing bypasses it
    assert EDITS.check([line("99284"), line("99283", "59")], ["I10"], "2026-01-05").ncci


def test_an_edit_applies_only_from_its_effective_date():
    assert not EDITS.check([line("99284"), line("99283")], ["I10"], "2023-12-31").ncci


def test_units_of_a_code_add_up_across_lines_against_the_mue():
    assert not EDITS.check([line("99213")], ["I10"], "2026-01-05").mue
    [excess] = EDITS.check([line("99213"), line("99213")], ["I10"], "2026-01-05").mue
    assert (excess.cpt_code, excess.units, excess.limit) == ("99213", 2, 1)
    assert EDITS.check([line("99213", units=3)], ["I10"], "2026-01-05").mue[0].units == 3


def test_a_policy_is_met_by_the_diagnosis_the_line_points_to():
    [uncovered] = EDITS.check([line("43239", dx="E11.65")], ["E11.65"], "2026-01-05").uncovered
    assert (uncovered.policy_id, uncovered.cpt_code, uncovered.line_number) == ("LCD-L33631", "43239", 1)
    assert uncovered.diagnosis == "E11.65"
    assert not EDITS.check([line("43239", dx="K21.0")], ["E11.65", "K21.0"], "2026-01-05").uncovered
    # A covered diagnosis elsewhere on the claim doesn't support a line pointing at another
    assert EDITS.check([line("43239", dx="E11.65")], ["E11.65", "K21.0"], "2026-01-05").uncovered
    # A code without a policy has nothing to meet
    assert not EDITS.check([line("99213", dx="E11.65")], ["E11.65"], "2026-01-05").uncovered


def test_a_pointer_to_a_code_no_longer_on_the_claim_reads_as_the_primary():
    # AI Fix corrected the primary from R10.9 to K21.0; the line still says R10.9
    assert not EDITS.check([line("43239", dx="R10.9")], ["K21.0"], "2026-01-05").uncovered
    assert EDITS.check([line("43239")], ["E11.65"], "2026-01-05").uncovered


def test_icd10_chapters_come_from_the_code_itself():
    assert icd10_chapter("I48.91") == "Circulatory"
    assert icd10_chapter("d25.9") == "Neoplasm" and icd10_chapter("D64.9") == "Blood"
    assert icd10_chapter("S72.001A") == "Injury" and icd10_chapter("T81.4XXA") == "Injury"
    assert icd10_chapter("O9A.11") == "Pregnancy" and icd10_chapter("Z51.11") == "Health factors"
    assert icd10_chapter("") is None and icd10_chapter("123") is None


def test_a_specialty_procedure_needs_a_diagnosis_from_a_related_chapter():
    [mismatch] = EDITS.check([line("93000", dx="F41.1")], ["F41.1"], "2026-01-05").mismatched
    assert (mismatch.line_number, mismatch.category, mismatch.chapter) == (1, "Cardiology", "Mental")
    assert mismatch.expected == ("Circulatory",)
    assert not EDITS.check([line("93000", dx="I48.91")], ["I48.91"], "2026-01-05").mismatched
    # Symptoms and encounter reasons support any procedure
    assert not EDITS.check([line("93000", dx="R07.9")], ["R07.9"], "2026-01-05").mismatched
    assert not EDITS.check([line("93000", dx="Z01.818")], ["Z01.818"], "2026-01-05").mismatched
    # Office visits go with any diagnosis
    assert not EDITS.check([line("99213", dx="F41.1")], ["F41.1"], "2026-01-05").mismatched


def test_a_procedure_with_a_policy_is_judged_by_the_policy_only():
    result = EDITS.check([line("43239", dx="F41.1")], ["F41.1"], "2026-01-05")
    assert result.uncovered and not result.mismatched


def test_missing_reference_tables_check_nothing(tmp_path):
    edits = CodingEdits.load(tmp_path)
    assert edits.check([line("99284"), line("99283", units=5)], ["F41.1"], "2026-01-05").flags() == NO_FLAGS


# --- On claims ------------------------------------------------------------------


def test_each_check_is_an_error_on_a_new_claim(client):
    ncci = create(
        client,
        diagnoses=["E11.65"],
        lines=[{"cpt_code": "99284", "icd10_pointer": "E11.65"}, {"cpt_code": "99283", "icd10_pointer": "E11.65"}],
    )
    assert ncci.status_code == 201, ncci.text
    assert "NCCI Procedure-to-Procedure Edit" in rule_names(ncci)
    assert ncci.json()["validation"]["status"] in ("error", "aifix")

    mue = create(client, lines=[{"cpt_code": "99213", "icd10_pointer": "E11.65", "units": 2}])
    assert "Units Exceed MUE Limit" in rule_names(mue)

    uncovered = create(client, lines=[{"cpt_code": "43239", "icd10_pointer": "E11.65"}])
    assert "Diagnosis Not Covered (LCD/NCD)" in rule_names(uncovered)

    mismatch = create(client, diagnoses=["E11.65"], lines=[{"cpt_code": "93000", "icd10_pointer": "E11.65"}])
    assert "Diagnosis Doesn't Match Procedure" in rule_names(mismatch)
    assert mismatch.json()["validation"]["status"] == "warning"

    clean = create(client)
    assert not rule_names(clean) & {r.name for r in [*CODING_RULES, *MISMATCH_RULES]}


def test_source_claims_are_not_coding_checked(repo):
    frame = repo.claims_frame()
    assert not frame[list(NO_FLAGS)].any().any()


def test_the_checks_are_blocking_until_the_line_is_corrected(client):
    body = {
        "diagnoses": ["E11.65"],
        "lines": [{"cpt_code": "99213", "icd10_pointer": "E11.65", "units": 2}],
    }
    claim_id = create(client, **body).json()["claim"]["claim_id"]
    refused = client.post(f"/api/claims/{claim_id}/submit")
    assert refused.status_code == 422 and "Units Exceed MUE Limit" in refused.text

    corrected = client.get(f"/api/claims/{claim_id}").json()
    from app.tests.test_claim_entry import NEW_CLAIM

    res = client.put(
        f"/api/claims/{claim_id}",
        json={**NEW_CLAIM, "lines": [{"cpt_code": "99213", "icd10_pointer": "E11.65", "units": 1}]},
    )
    assert res.status_code == 200, res.text
    assert "Units Exceed MUE Limit" not in rule_names(res)
    assert corrected["claim_id"] == claim_id


def test_ai_fix_names_the_line_and_cites_the_edit(client):
    claim_id = create(
        client,
        lines=[{"cpt_code": "99284", "icd10_pointer": "E11.65"}, {"cpt_code": "99283", "icd10_pointer": "E11.65"}],
    ).json()["claim"]["claim_id"]
    fixes = client.get(f"/api/aifix/{claim_id}").json()
    [ncci] = [s for s in fixes["suggestions"] if s["title"].startswith("Remove CPT 99283")]
    assert "line 2" in ncci["title"]
    assert ncci["clarification_topic"] == "ncci_modifiers"
    assert any(c["source_type"] == "ncci_edit" and c["reference_id"] == "PTP0003" for c in ncci["citations"])


def test_ai_fix_points_the_line_at_a_covered_diagnosis_already_on_the_claim(client):
    claim_id = create(
        client,
        diagnoses=["E11.65", "K21.0"],
        lines=[
            {"cpt_code": "99213", "icd10_pointer": "K21.0"},
            {"cpt_code": "43239", "icd10_pointer": "E11.65"},
        ],
    ).json()["claim"]["claim_id"]
    fixes = client.get(f"/api/aifix/{claim_id}").json()["suggestions"]
    [coverage] = [s for s in fixes if s["title"] == "Point line 2 at K21.0"]
    assert coverage["action"] == "manual" and coverage["changes"] == []


def test_ai_fix_for_a_mismatch_suggests_the_fitting_diagnosis_on_the_claim(client):
    claim_id = create(
        client,
        diagnoses=["E11.65", "I10"],
        lines=[
            {"cpt_code": "99213", "icd10_pointer": "I10"},
            {"cpt_code": "93000", "icd10_pointer": "E11.65"},
        ],
    ).json()["claim"]["claim_id"]
    fixes = client.get(f"/api/aifix/{claim_id}").json()["suggestions"]
    [mismatch] = [s for s in fixes if s["title"] == "Check the diagnosis for line 2 (CPT 93000)"]
    assert mismatch["action"] == "clarify" and mismatch["clarification_topic"] == "medical_necessity"
    assert "If it was for I10, point line 2 at it" in mismatch["steps"]
    assert "for E11.65, an endocrine diagnosis" in mismatch["summary"]


def test_applying_a_covered_diagnosis_clears_the_coverage_error(client):
    claim_id = create(client, lines=[{"cpt_code": "43239", "icd10_pointer": "E11.65"}]).json()["claim"][
        "claim_id"
    ]
    fixes = client.get(f"/api/aifix/{claim_id}").json()
    [coverage] = [s for s in fixes["suggestions"] if "LCD-L33631" in s["title"]]
    [change] = coverage["changes"]
    assert change["field"] == "primary_icd10" and "K21.0" in change["options"]
    applied = client.post(
        f"/api/aifix/{claim_id}/apply",
        json={"suggestion_id": coverage["id"], "values": {"primary_icd10": "K21.0"}},
    )
    assert applied.status_code == 200, applied.text
    after = client.post("/api/validate", json={"claim_ids": [claim_id]}).json()
    names = {f["rule_name"] for result in after for f in result["findings"]} if isinstance(after, list) else {
        f["rule_name"] for result in after["results"] for f in result["findings"]
    }
    assert "Diagnosis Not Covered (LCD/NCD)" not in names


# --- Rules for organisations saved before the checks ------------------------------


def test_saved_rules_get_the_coding_rules_once(tmp_path):
    added = [*CODING_RULES, *MISMATCH_RULES]
    path = tmp_path / "rules.json"
    old = RuleRepository(seed=[r for r in DEFAULT_RULES if r not in added], path=path)
    payload = json.loads(path.read_text())
    payload.pop("seed_version")  # as written before seed versions existed
    path.write_text(json.dumps(payload))
    assert len(old.list()) == len(DEFAULT_RULES) - len(added)

    upgraded = RuleRepository(path=path)
    names = [r.name for r in upgraded.list()]
    assert names[-len(added):] == [r.name for r in added]
    assert json.loads(path.read_text())["seed_version"] == SEED_VERSION

    # An administrator's deletion sticks across restarts
    upgraded.delete(upgraded.list()[-1].id)
    assert len(RuleRepository(path=path).list()) == len(DEFAULT_RULES) - 1


def test_rules_saved_at_seed_version_2_get_only_the_mismatch_rule(tmp_path):
    path = tmp_path / "rules.json"
    RuleRepository(seed=[r for r in DEFAULT_RULES if r not in MISMATCH_RULES], path=path)
    payload = json.loads(path.read_text())
    payload["seed_version"] = 2
    path.write_text(json.dumps(payload))
    names = [r.name for r in RuleRepository(path=path).list()]
    assert names.count("NCCI Procedure-to-Procedure Edit") == 1
    assert names[-1] == "Diagnosis Doesn't Match Procedure"
