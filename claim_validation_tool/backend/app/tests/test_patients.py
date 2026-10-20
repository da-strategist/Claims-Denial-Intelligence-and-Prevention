"""Registered patients and the reference lists the claim-entry form uses."""


def search(client, term, **params):
    return client.get("/api/patients", params={"search": term, **params}).json()


def test_search_by_name_words_in_any_order(client):
    body = search(client, "sanchez karen")
    # Two registered patients share the name; age and history tell them apart
    assert [(p["patient_id"], p["age"], p["claim_count"], p["denial_count"]) for p in body["items"]] == [
        ("PAT000002", 92, 2, 1),
        ("PAT000004", 35, 0, 0),
    ]


def test_search_by_id_prefix(client):
    assert [p["patient_id"] for p in search(client, "pat00000")["items"]] == [
        "PAT000001",
        "PAT000002",
        "PAT000003",
        "PAT000004",
    ]
    assert search(client, "PAT000001")["total"] == 1


def test_name_starting_with_pat_is_a_name_search(client):
    # "Pat..." names (Patricia, Patrick) mustn't be mistaken for patient IDs
    assert search(client, "pat")["total"] == 4  # bare prefix: every ID
    assert search(client, "patricia")["total"] == 0


def test_name_search_is_sorted_by_name(client):
    assert [p["last_name"] for p in client.get("/api/patients").json()["items"]] == [
        "Davis",
        "Garcia",
        "Sanchez",
        "Sanchez",
    ]


def test_no_search_lists_everyone_paged(client):
    body = client.get("/api/patients", params={"page_size": 2}).json()
    assert (body["total"], len(body["items"]), body["pages"]) == (4, 2, 2)


def test_get_patient(client):
    patient = client.get("/api/patients/PAT000001").json()
    assert (patient["first_name"], patient["primary_payer_id"]) == ("William", "PAY001")
    assert client.get("/api/patients/PAT999999").status_code == 404
    assert client.get("/api/patients/nope").status_code == 422


def test_claim_detail_includes_patient(client):
    assert client.get("/api/claims/CLM0000003").json()["patient"]["last_name"] == "Sanchez"


def test_reference_lists(client):
    assert [p["provider_id"] for p in client.get("/api/providers").json()] == ["PROV001", "PROV002"]
    assert [f["facility_id"] for f in client.get("/api/facilities").json()] == ["FAC001", "FAC002"]
    procedures = {c["cpt_code"]: c for c in client.get("/api/codes/procedures").json()}
    assert procedures["43239"]["standard_charge"] == 1800.0
    diagnoses = [c["icd10_code"] for c in client.get("/api/codes/diagnoses").json()]
    assert "E11.65" in diagnoses
