from datetime import date

import pytest

from app.models import ClaimQuery, ClaimStatus, ClaimType


def claim_ids(repo, **params) -> list[str]:
    return [claim.claim_id for claim in repo.list_claims(ClaimQuery(**params)).items]


def test_list_defaults_to_newest_service_date_first(repo):
    # CLM0000003 and CLM0000004 share a service date; claim_id breaks the tie
    assert claim_ids(repo) == ["CLM0000003", "CLM0000004", "CLM0000002", "CLM0000001"]


def test_sort_ascending_by_charge(repo):
    assert claim_ids(repo, sort_by="total_charge", sort_desc=False) == [
        "CLM0000001",
        "CLM0000003",
        "CLM0000004",
        "CLM0000002",
    ]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"search": "clm0000002"}, {"CLM0000002"}),
        ({"search": "PAT000001"}, {"CLM0000001", "CLM0000004"}),
        ({"search": "K21"}, {"CLM0000002"}),
        ({"payer_id": "PAY001"}, {"CLM0000001", "CLM0000003"}),
        ({"provider_id": "PROV002"}, {"CLM0000002", "CLM0000004"}),
        ({"department_id": "DEPT05"}, {"CLM0000002", "CLM0000004"}),
        ({"status": ClaimStatus.DENIED}, {"CLM0000002", "CLM0000004"}),
        ({"claim_type": ClaimType.INSTITUTIONAL}, {"CLM0000002", "CLM0000003"}),
        ({"is_clean_claim": True}, {"CLM0000001", "CLM0000003"}),
        ({"is_clean_claim": False}, {"CLM0000002", "CLM0000004"}),
        ({"missing_prior_auth": True}, {"CLM0000002"}),
        ({"missing_prior_auth": False}, {"CLM0000001", "CLM0000003", "CLM0000004"}),
        (
            {"service_date_from": date(2025, 2, 15), "service_date_to": date(2025, 3, 19)},
            {"CLM0000002"},
        ),
        ({"min_charge": 800, "max_charge": 800}, {"CLM0000003", "CLM0000004"}),
        ({"payer_id": "PAY002", "status": ClaimStatus.PAID}, set()),
    ],
)
def test_filters(repo, params, expected):
    assert set(claim_ids(repo, **params)) == expected


def test_pagination(repo):
    page = repo.list_claims(ClaimQuery(page=2, page_size=3))
    assert page.total == 4
    assert page.pages == 2
    assert [claim.claim_id for claim in page.items] == ["CLM0000001"]


def test_page_past_end_is_empty(repo):
    page = repo.list_claims(ClaimQuery(page=5, page_size=3))
    assert page.items == []
    assert page.total == 4


def test_get_claim_detail(repo):
    claim = repo.get_claim("CLM0000002")
    assert [line.line_number for line in claim.lines] == [1, 2]
    assert [denial.denial_id for denial in claim.denials] == ["DEN0000001"]
    assert claim.payer.payer_name == "Blue Cross NC"
    assert claim.provider.provider_name == "Dr. Test Two"
    assert claim.missing_prior_auth


def test_get_claim_without_denials(repo):
    claim = repo.get_claim("CLM0000003")
    assert claim.denials == []
    assert claim.pa_number == "PA123456"
    assert not claim.missing_prior_auth


def test_get_unknown_claim_returns_none(repo):
    assert repo.get_claim("CLM9999999") is None


def test_prior_denial_flags_only_count_denials_known_at_submission(repo):
    flags = repo.claims_frame().set_index("claim_id")[
        ["has_prior_denial", "has_prior_preventable_denial"]
    ]
    # CLM0000002 and CLM0000004 are denied, but their own denials come after submission
    assert flags.loc["CLM0000001"].tolist() == [False, False]
    assert flags.loc["CLM0000002"].tolist() == [False, False]
    assert flags.loc["CLM0000003"].tolist() == [True, True]
    assert flags.loc["CLM0000004"].tolist() == [False, False]
