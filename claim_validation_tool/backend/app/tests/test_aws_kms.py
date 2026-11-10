"""The AWS KMS key provider, against a stand-in for the KMS client (no AWS account needed)."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.data import key_providers
from app.data.aws_kms import CONTEXT, AwsKmsKeyProvider
from app.data.key_providers import KeyProviderError
from app.data.secure_files import data_key_provider, org_cipher
from app.data.repository import get_repository
from app.tests.conftest import org_folder
from app.tests.test_claim_entry import create

ARN = "arn:aws:kms:us-east-1:111122223333:key/{}"


class FakeKmsClient:
    """Encrypt, Decrypt and DescribeKey as KMS does them: the wrapped key names the KMS key
    that locked it, and the encryption context must match."""

    def __init__(self):
        self.keys = {"alias/pilot": "k1", "alias/next": "k2"}
        self.material = {key: Fernet(Fernet.generate_key()) for key in ("k1", "k2")}
        self.calls = []

    def _key(self, key_id):
        key = self.keys.get(key_id, key_id.rsplit("/", 1)[-1])
        if key not in self.material:
            raise RuntimeError(f"NotFoundException: {key_id}")
        return key

    def describe_key(self, KeyId):
        self.calls.append("describe_key")
        return {"KeyMetadata": {"Arn": ARN.format(self._key(KeyId))}}

    def encrypt(self, KeyId, Plaintext, EncryptionContext):
        self.calls.append("encrypt")
        key = self._key(KeyId)
        return {"CiphertextBlob": key.encode() + b":" + self.material[key].encrypt(repr(EncryptionContext).encode() + b"|" + Plaintext)}

    def decrypt(self, CiphertextBlob, EncryptionContext):
        self.calls.append("decrypt")
        key, _, token = CiphertextBlob.partition(b":")
        try:
            context, _, plain = self.material[key.decode()].decrypt(token).partition(b"|")
        except (KeyError, InvalidToken):
            raise RuntimeError("InvalidCiphertextException") from None
        if context != repr(EncryptionContext).encode():
            raise RuntimeError("InvalidCiphertextException: encryption context")
        return {"Plaintext": plain, "KeyId": ARN.format(key.decode())}


@pytest.fixture
def kms(monkeypatch):
    client = FakeKmsClient()
    monkeypatch.setenv("RCM_KMS_KEY_ID", "alias/pilot")
    monkeypatch.setattr(AwsKmsKeyProvider, "from_env", classmethod(
        lambda cls: cls(key_providers.os.environ["RCM_KMS_KEY_ID"], client)
    ))
    return client


def test_wraps_and_unwraps_with_the_encryption_context(kms):
    provider = AwsKmsKeyProvider("alias/pilot", kms)
    data_key = Fernet.generate_key()
    wrapped = provider.wrap(data_key)
    assert data_key not in wrapped
    assert provider.unwrap(wrapped) == data_key
    assert provider.is_current(wrapped)
    with pytest.raises(RuntimeError, match="encryption context"):
        kms.decrypt(CiphertextBlob=wrapped, EncryptionContext={**CONTEXT, "purpose": "other"})


def test_kms_errors_become_key_provider_errors(kms):
    provider = AwsKmsKeyProvider("alias/missing", kms)
    with pytest.raises(KeyProviderError, match="AWS KMS encrypt failed"):
        provider.wrap(b"x")
    with pytest.raises(KeyProviderError, match="AWS KMS decrypt failed"):
        provider.unwrap(b"k1:not-a-token")


def test_an_organisation_moves_onto_kms_and_then_to_a_new_kms_key(client, monkeypatch, kms, capsys):
    from app import orgs as cli

    claim_id = create(client).json()["claim"]["claim_id"]
    monkeypatch.setenv("RCM_KEY_PROVIDER", "aws-kms")
    assert cli.main(["rotate-key"]) == 0
    assert data_key_provider(org_folder()) == "aws-kms"
    monkeypatch.delenv("RCM_MASTER_KEY")  # the local key can go
    for cache in (org_cipher, get_repository):
        cache.cache_clear()
    assert client.get(f"/api/claims/{claim_id}").status_code == 200

    # A new KMS key: re-wrap, and the data still opens
    monkeypatch.setenv("RCM_KMS_KEY_ID", "alias/next")
    capsys.readouterr()
    assert cli.main(["rotate-key"]) == 0
    assert "meridian: re-wrapped" in capsys.readouterr().out
    kms.material.pop("k1")  # the old key is disabled
    for cache in (org_cipher, get_repository):
        cache.cache_clear()
    assert client.get(f"/api/claims/{claim_id}").status_code == 200
