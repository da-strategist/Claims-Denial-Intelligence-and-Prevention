"""Phase D: encryption at rest per organisation, data export, deletion (crypto-shredding),
and business associate agreements. Every API test runs encrypted (conftest sets
RCM_MASTER_KEY); these check what's on disk and the edges."""

import hashlib
import io
import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.data import secure_files
from app.data.audit import AuditLog
from app.data.corrections import get_correction_store
from app.data.new_claims import get_new_claim_store
from app.data.org_lifecycle import encrypt_organisation, rotate_master_key
from app.data.repository import get_repository
from app.data.orgs import get_org_registry, org_cipher_for
from app.data.key_providers import KeyProviderError, register, unregister
from app.data.secure_files import EncryptionError, data_key_provider, is_encrypted, org_cipher
from app.models import Role
from app.tests.conftest import TEST_MASTER_KEY, TestClient, org_folder, sign_in, use_data_dir
from app.tests.test_claim_entry import create

LAKESIDE_DRAFT = {"patient_id": "PAT900001"}
PHI = ["PAT000003", "12 Oak St", "MBR123456", "1976-05-02"]


def disk_text(org: str = "meridian") -> str:
    """Everything in the organisation's folder, as stored."""
    return "".join(
        p.read_bytes().decode(errors="replace") for p in org_folder(org).rglob("*") if p.is_file()
    )


def test_patient_data_is_never_on_disk_in_plain_text(client):
    assert create(client).status_code == 201
    draft = {"patient_id": "PAT000003", "billing": {"patient_address": {"line1": "12 Oak St"}}}
    assert client.post("/api/drafts", json=draft).status_code == 201
    stored = disk_text()
    for value in PHI:
        assert value not in stored, value
    folder = org_folder()
    for name in ("new_claims.json", "claim_drafts.json", "patient_registrations.json"):
        assert is_encrypted((folder / name).read_bytes()), name
    lines = (folder / "logs/audit.jsonl").read_bytes().splitlines()
    assert lines and all(is_encrypted(line) for line in lines)
    # …and it all reads back, with the audit chain intact
    assert client.get("/api/claims", params={"query": "PAT000003"}).json()["total"] >= 1
    assert client.get("/api/audit/verify").json()["ok"] is True
    # Settings without PHI stay readable
    client.patch("/api/rules/RULE-001", json={"enabled": False})
    assert json.loads((folder / "rules.json").read_text())


def test_each_organisation_has_its_own_key(client):
    create(client)
    sign_in(client, Role.BILLER, "lakeside")
    assert client.post("/api/drafts", json=LAKESIDE_DRAFT).status_code == 201
    meridian, lakeside = org_cipher_for("meridian"), org_cipher_for("lakeside")
    stored = (org_folder("lakeside") / "claim_drafts.json").read_bytes()
    assert json.loads(lakeside.decrypt(stored))["drafts"]
    with pytest.raises(InvalidToken):
        meridian.decrypt(stored)
    # The data keys are stored wrapped: the file isn't the key
    wrapped = (org_folder("meridian") / "data_key.enc").read_bytes()
    assert Fernet(TEST_MASTER_KEY).decrypt(wrapped) != wrapped


def test_encrypted_data_needs_the_right_master_key(client, monkeypatch):
    create(client)
    folder = org_folder()
    monkeypatch.delenv("RCM_MASTER_KEY")
    org_cipher.cache_clear()
    with pytest.raises(EncryptionError, match="set RCM_MASTER_KEY"):
        org_cipher(folder)
    monkeypatch.setenv("RCM_MASTER_KEY", Fernet.generate_key().decode())
    with pytest.raises(EncryptionError, match="doesn't unlock"):
        org_cipher(folder)
    # A rotated key list still opens it while the old key is in the list
    monkeypatch.setenv("RCM_MASTER_KEY", f"{Fernet.generate_key().decode()},{TEST_MASTER_KEY}")
    assert org_cipher(folder) is not None


def test_existing_plain_files_are_read_then_encrypted_in_place(anon_client, tmp_path):
    # An install from before encryption: plain files, and Lakeside's tables in its own folder
    folder = org_folder("lakeside")
    shutil.copytree(get_org_registry().data_dir("lakeside"), folder / "data")
    use_data_dir("lakeside", folder / "data")
    (folder / "new_claims.json").write_text(json.dumps({"claims": [], "next_control_number": 7}))
    AuditLog(folder / "logs/audit.jsonl").record(username="x", role=None, action="GET /", status_code=200)

    done = encrypt_organisation("lakeside")
    assert "encrypted lakeside/new_claims.json" in done
    assert "encrypted fact_claims.csv -> fact_claims.csv.enc" in done
    assert not (folder / "data/fact_claims.csv").exists()
    assert is_encrypted((folder / "data/dim_patients.csv.enc").read_bytes())
    assert (folder / "data/dim_cpt_codes.csv").exists()  # shared code sets stay as they are
    assert encrypt_organisation("lakeside") == []  # nothing left to do
    assert AuditLog(folder / "logs/audit.jsonl", org_cipher_for("lakeside")).verify().ok
    # Meridian's claims folder is outside its folder: reported, not touched
    assert any("outside meridian's folder" in line for line in encrypt_organisation("meridian"))

    sign_in(anon_client, Role.BILLER, "lakeside")
    assert anon_client.get("/api/claims").json()["total"] == 10  # decrypted on load


def test_production_needs_a_master_key(anon_client, monkeypatch):
    monkeypatch.setenv("RCM_ENVIRONMENT", "production")
    monkeypatch.delenv("RCM_MASTER_KEY")
    with pytest.raises(RuntimeError, match="needs RCM_MASTER_KEY"):
        with TestClient(anon_client.app):
            pass


def test_admins_export_everything_decrypted_with_a_manifest(client):
    claim_id = create(client).json()["claim"]["claim_id"]
    res = client.get("/api/organisation/export")
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["organisation"]["id"] == "meridian" and manifest["exported_by"] == "admin1"
    for entry in manifest["files"]:
        assert hashlib.sha256(zf.read(entry["path"])).hexdigest() == entry["sha256"]
    names = set(zf.namelist())
    assert {"app/new_claims.json", "data/fact_claims.csv", "accounts.json", "app/audit.jsonl"} <= names
    assert claim_id in zf.read("app/new_claims.json").decode()
    assert "password" not in zf.read("accounts.json").decode()
    assert not any(name.startswith("data/dim_cpt") for name in names)  # shared code sets
    # Recorded, with what it held
    (event,) = [e for e in client.get("/api/audit").json() if e["action"] == "GET /api/organisation/export"]
    assert event["detail"]["files"] == len(manifest["files"])


def test_only_administrators_export(client):
    for role in (Role.BILLER, Role.ANALYST):
        sign_in(client, role)
        assert client.get("/api/organisation/export").status_code == 403
    sign_in(client, Role.PLATFORM)
    client.post(
        "/api/platform/organisations/meridian/emergency-access",
        json={"reason": "Ticket 4471: claims page fails to load", "minutes": 30},
    )
    assert client.get("/api/organisation/export").status_code == 403  # emergency is look-only


def test_deleting_an_organisation_shreds_its_key_folder_and_accounts(client):
    sign_in(client, Role.BILLER, "lakeside")
    assert client.post("/api/drafts", json=LAKESIDE_DRAFT).status_code == 201
    folder = org_folder("lakeside")
    backup = (folder / "claim_drafts.json").read_bytes()  # e.g. a copy in last night's backup

    sign_in(client, Role.PLATFORM)
    url = "/api/platform/organisations/lakeside/delete"
    assert client.post(url, json={"confirm": "lakeside"}).status_code == 409  # suspend first
    client.post("/api/platform/organisations/lakeside/suspend")
    assert client.post(url, json={"confirm": "Lakeside"}).status_code == 422  # typed exactly
    res = client.post(url, json={"confirm": "lakeside"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["organisation"]["status"] == "deleted" and body["organisation"]["accounts"] == 0
    assert any("data key" in line for line in body["done"])
    assert any("did not delete" in line for line in body["done"])  # its CSVs are outside

    assert not folder.exists()
    with pytest.raises(InvalidToken):  # the master key alone can't read the backup copy
        Fernet(TEST_MASTER_KEY).decrypt(backup)
    with TestClient(client.app) as old:
        res = old.post("/api/auth/login", json={"username": "admin2", "password": "Fixture-password-1"})
        assert res.status_code == 401
    # The record stays, so the ID isn't reused, and nothing more can be done to it
    assert client.post("/api/platform/organisations", json={"id": "lakeside", "name": "Lakeside again"}).status_code == 409
    assert client.post("/api/platform/organisations/lakeside/reactivate").status_code == 409
    sign_in(client, Role.ADMIN)
    assert client.get("/api/claims").status_code == 200  # Meridian carries on


BAA = {"signed_on": "2026-10-01", "reference": "BAA-2026-014", "signatory": "Dr. Ada Obi, CEO"}


def test_without_a_baa_production_sign_in_is_blocked(client, monkeypatch):
    monkeypatch.setenv("RCM_ENVIRONMENT", "production")
    monkeypatch.setenv("RCM_COOKIE_SECURE", "1")
    login = {"username": "admin2", "password": "Fixture-password-1"}
    with TestClient(client.app) as lakeside:
        res = lakeside.post("/api/auth/login", json=login)
        assert res.status_code == 403 and "business associate agreement" in res.text

    sign_in(client, Role.PLATFORM)
    info = client.post("/api/platform/organisations/lakeside/baa", json=BAA).json()
    assert info["baa"]["reference"] == "BAA-2026-014" and info["baa"]["recorded_by"] == "platform1"
    assert client.post("/api/platform/organisations/lakeside/baa", json={**BAA, "reference": ""}).status_code == 422
    with TestClient(client.app) as lakeside:
        assert lakeside.post("/api/auth/login", json=login).status_code == 200


def test_outside_production_a_missing_baa_is_only_flagged(client):
    sign_in(client, Role.PLATFORM)
    orgs = client.get("/api/platform/organisations").json()
    assert all(o["baa"] is None for o in orgs)
    sign_in(client, Role.ADMIN, "lakeside")
    assert client.get("/api/claims").status_code == 200


def test_secure_files_round_trip(tmp_path):
    cipher = Fernet(Fernet.generate_key())
    path = tmp_path / "f.json"
    secure_files.write_text(path, '{"a": 1}', cipher)
    assert is_encrypted(path.read_bytes()) and path.stat().st_mode & 0o777 == 0o600
    assert secure_files.read_text(path, cipher) == '{"a": 1}'
    log = tmp_path / "log.jsonl"
    for n in range(3):
        secure_files.append_line(log, f'{{"seq": {n}}}', cipher)
    assert list(secure_files.iter_lines(log, cipher)) == ['{"seq": 0}', '{"seq": 1}', '{"seq": 2}']
    plain = tmp_path / "plain.json"
    plain.write_text("{}")
    assert secure_files.read_text(plain, cipher) == "{}"  # plain still reads (migration)
    with pytest.raises(EncryptionError):
        secure_files.read_text(path, None)


def test_a_deleted_organisation_never_comes_back(client):
    # Emergency access still open when the organisation is suspended and deleted
    sign_in(client, Role.PLATFORM)
    grant = client.post(
        "/api/platform/organisations/lakeside/emergency-access",
        json={"reason": "Ticket 4471: claims page fails to load", "minutes": 30},
    ).json()
    client.post("/api/platform/organisations/lakeside/suspend")
    done = client.post("/api/platform/organisations/lakeside/delete", json={"confirm": "lakeside"}).json()["done"]
    assert "ended 1 open emergency access grant(s)" in done
    folder = org_folder("lakeside")
    # Ending the grant again, or anything else touching its files, must not recreate them
    assert client.post(f"/api/platform/emergency-access/{grant['id']}/end").status_code == 200
    with pytest.raises(LookupError):
        org_cipher_for("lakeside")
    assert not folder.exists()


def test_rotating_the_master_key_lets_the_old_one_go(client, monkeypatch):
    claim_id = create(client).json()["claim"]["claim_id"]
    new_key = Fernet.generate_key().decode()
    monkeypatch.setenv("RCM_MASTER_KEY", f"{new_key},{TEST_MASTER_KEY}")
    from app import orgs as cli

    assert cli.main(["rotate-key"]) == 0
    assert rotate_master_key("meridian") is False  # already done
    monkeypatch.setenv("RCM_MASTER_KEY", new_key)  # the old key is gone
    for cache in (org_cipher, get_repository, get_new_claim_store, get_correction_store):
        cache.cache_clear()
    assert client.get(f"/api/claims/{claim_id}").status_code == 200


def test_concurrent_first_use_makes_one_data_key(tmp_path, monkeypatch):
    monkeypatch.setenv("RCM_MASTER_KEY", TEST_MASTER_KEY)
    folder = tmp_path / "neworg"
    org_cipher.cache_clear()
    with ThreadPoolExecutor(8) as pool:
        ciphers = list(pool.map(lambda _: org_cipher.__wrapped__(folder), range(16)))
    token = ciphers[0].encrypt(b"x")
    assert all(c.decrypt(token) == b"x" for c in ciphers)


def test_production_needs_https_cookies(anon_client, monkeypatch):
    monkeypatch.setenv("RCM_ENVIRONMENT", "production")
    monkeypatch.delenv("RCM_COOKIE_SECURE", raising=False)
    with pytest.raises(RuntimeError, match="RCM_COOKIE_SECURE"):
        with TestClient(anon_client.app):
            pass


class FakeKms:
    """Stands in for a cloud key service: its own master key, never in the environment."""

    name = "test-kms"

    def __init__(self, key: bytes) -> None:
        self._key, self.calls = Fernet(key), []

    def wrap(self, data_key: bytes) -> bytes:
        self.calls.append("wrap")
        return self._key.encrypt(data_key)

    def unwrap(self, wrapped: bytes) -> bytes:
        self.calls.append("unwrap")
        try:
            return self._key.decrypt(wrapped)
        except InvalidToken:
            raise KeyProviderError("test-kms doesn't unlock this data key") from None

    def is_current(self, wrapped: bytes) -> bool:
        return True


@pytest.fixture
def fake_kms():
    kms = FakeKms(Fernet.generate_key())
    register("test-kms", lambda: kms)
    yield kms
    unregister("test-kms")


def test_moving_the_master_key_to_another_provider(client, monkeypatch, fake_kms, capsys):
    from app import orgs as cli

    claim_id = create(client).json()["claim"]["claim_id"]
    assert data_key_provider(org_folder()) == "local"
    # Switch provider, keeping the local key so existing data keys still open, and re-wrap
    monkeypatch.setenv("RCM_KEY_PROVIDER", "test-kms")
    assert cli.main(["rotate-key"]) == 0
    assert "now held by test-kms" in capsys.readouterr().out
    assert data_key_provider(org_folder()) == "test-kms"
    # The local master key can go: everything still opens, through the key service
    monkeypatch.delenv("RCM_MASTER_KEY")
    for cache in (org_cipher, get_repository, get_new_claim_store, get_correction_store):
        cache.cache_clear()
    assert client.get(f"/api/claims/{claim_id}").status_code == 200
    assert "unwrap" in fake_kms.calls
    cli.main(["key-status"])
    assert "meridian       test-kms" in capsys.readouterr().out


def test_new_organisations_get_keys_from_the_active_provider(client, monkeypatch, fake_kms):
    monkeypatch.setenv("RCM_KEY_PROVIDER", "test-kms")
    org_cipher.cache_clear()
    sign_in(client, Role.PLATFORM)
    client.post("/api/platform/organisations", json={"id": "acme", "name": "Acme Health"})
    assert org_cipher_for("acme") is not None
    assert data_key_provider(org_folder("acme")) == "test-kms"
    assert json.loads((org_folder("acme") / "data_key.enc").read_text())["provider"] == "test-kms"


def test_a_key_held_by_a_provider_that_isnt_set_up_is_refused(client, monkeypatch, fake_kms):
    monkeypatch.setenv("RCM_KEY_PROVIDER", "test-kms")
    org_cipher.cache_clear()
    from app import orgs as cli

    cli.main(["rotate-key"])
    unregister("test-kms")
    monkeypatch.setenv("RCM_KEY_PROVIDER", "local")
    org_cipher.cache_clear()
    with pytest.raises(EncryptionError, match="test-kms"):
        org_cipher(org_folder())


@pytest.mark.parametrize(
    ("name", "message"),
    [("aws-kms", "AWS KMS \\(aws-kms\\) isn't built yet"), ("awskms", "Unknown key provider 'awskms'")],
)
def test_unbuilt_or_misspelt_providers_stop_startup(anon_client, monkeypatch, name, message):
    monkeypatch.setenv("RCM_KEY_PROVIDER", name)
    with pytest.raises(EncryptionError, match=message):
        with TestClient(anon_client.app):
            pass
