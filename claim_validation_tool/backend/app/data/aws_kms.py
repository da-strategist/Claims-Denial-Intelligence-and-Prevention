"""AWS Key Management Service as the key provider (RCM_KEY_PROVIDER=aws-kms).

The master key is a KMS key that never leaves AWS: each organisation's data key is sent to
KMS to be locked (Encrypt) when it's created or re-wrapped, and to be unlocked (Decrypt) once
when the API first opens that organisation. Every call is in AWS CloudTrail.

Settings:
    RCM_KMS_KEY_ID   the KMS key: its ARN, ID, or alias (e.g. alias/vericlaim-pilot)
    AWS_REGION       where the key is (or the server's default region)

Credentials come the usual AWS way; on EC2 that's the instance's IAM role, which needs only
kms:Encrypt, kms:Decrypt and kms:DescribeKey on this one key. Turn on automatic key rotation
in KMS: older key material still unlocks what it locked, so nothing has to be re-wrapped.
Moving to a new KMS key: set RCM_KMS_KEY_ID to it (the old key stays usable to IAM), run
`python -m app.orgs rotate-key`, then disable the old key.
"""

import os

from app.data.key_providers import KeyProviderError

NAME = "aws-kms"
KEY_ID_ENV = "RCM_KMS_KEY_ID"
# Bound into every wrapped data key: KMS won't unlock it for any other purpose
CONTEXT = {"purpose": "rcm-organisation-data-key"}


class AwsKmsKeyProvider:
    name = NAME

    def __init__(self, key_id: str, client=None) -> None:
        self.key_id = key_id
        if client is None:
            import boto3  # only needed when this provider is in use

            client = boto3.client("kms", region_name=os.environ.get("AWS_REGION") or None)
        self._kms = client
        self._key_arn: str | None = None

    @classmethod
    def from_env(cls) -> "AwsKmsKeyProvider | None":
        key_id = os.environ.get(KEY_ID_ENV, "").strip()
        return cls(key_id) if key_id else None

    def _call(self, action: str, **params) -> dict:
        try:
            return getattr(self._kms, action)(**params)
        except Exception as err:  # botocore raises ClientError, NoCredentialsError, …
            raise KeyProviderError(f"AWS KMS {action} failed: {err}") from None

    @property
    def key_arn(self) -> str:
        """The configured key's full ARN (an alias or ID is resolved once)."""
        if self._key_arn is None:
            self._key_arn = self._call("describe_key", KeyId=self.key_id)["KeyMetadata"]["Arn"]
        return self._key_arn

    def wrap(self, data_key: bytes) -> bytes:
        return self._call("encrypt", KeyId=self.key_id, Plaintext=data_key, EncryptionContext=CONTEXT)[
            "CiphertextBlob"
        ]

    def unwrap(self, wrapped: bytes) -> bytes:
        # No KeyId: KMS reads it from the wrapped key, so data keys locked by an earlier KMS
        # key still open during a move to a new one
        return self._call("decrypt", CiphertextBlob=wrapped, EncryptionContext=CONTEXT)["Plaintext"]

    def is_current(self, wrapped: bytes) -> bool:
        """Locked by the configured KMS key (rather than one being moved away from)."""
        return self._call("decrypt", CiphertextBlob=wrapped, EncryptionContext=CONTEXT)["KeyId"] == self.key_arn
