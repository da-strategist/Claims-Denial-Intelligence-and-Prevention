"""Where the master key lives: the providers that lock (wrap) and unlock (unwrap) each
organisation's data key (secure_files.py).

RCM_KEY_PROVIDER picks the provider that locks new and re-wrapped data keys:

    local           the master key is RCM_MASTER_KEY in the environment (.env). Built.
    aws-kms         AWS Key Management Service              } planned: add one at go-live
    azure-keyvault  Azure Key Vault                         } (DATA_SEGREGATION_PLAN.md
    gcp-kms         Google Cloud Key Management Service     }  §9.6)

With a cloud provider the master key never leaves the key service: the app sends it the
organisation's data key to lock or unlock, and every use is in the service's own audit
trail. Each wrapped data key records which provider locked it, so moving providers is: set
RCM_KEY_PROVIDER to the new one, keep the old one configured, run
`python -m app.orgs rotate-key` (every data key is re-locked by the new provider; no data
file changes), then remove the old provider's settings.

Adding a provider: a class with `name`, `wrap`, `unwrap`, and `is_current` (see
LocalKeyProvider), a factory returning it from its settings (or None when they aren't set),
and one `register(name, factory)` call.
"""

import os
from collections.abc import Callable
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

PROVIDER_ENV = "RCM_KEY_PROVIDER"
MASTER_KEY_ENV = "RCM_MASTER_KEY"
LOCAL = "local"

# Not built yet; named so a typo and a planned provider get different messages
PLANNED = {
    "aws-kms": "AWS KMS",
    "azure-keyvault": "Azure Key Vault",
    "gcp-kms": "Google Cloud KMS",
}


class KeyProviderError(RuntimeError):
    """A provider that isn't configured or built, or a data key it can't unlock."""


class KeyProvider(Protocol):
    name: str

    def wrap(self, data_key: bytes) -> bytes:
        """Lock a data key with the master key."""
        ...

    def unwrap(self, wrapped: bytes) -> bytes:
        """Unlock a data key; raises KeyProviderError if this master key didn't lock it."""
        ...

    def is_current(self, wrapped: bytes) -> bool:
        """Whether it was locked with this provider's current master key (rotation)."""
        ...


class LocalKeyProvider:
    """The master key in RCM_MASTER_KEY. Several may be given, comma-separated: the first
    locks, all of them unlock (so an old key can be retired with rotate-key)."""

    name = LOCAL

    def __init__(self, keys: list[str]) -> None:
        try:
            self._keys = [Fernet(key) for key in keys]
        except ValueError as err:
            raise KeyProviderError(f"{MASTER_KEY_ENV} is not a valid key: {err}") from None
        self._all = MultiFernet(self._keys)

    @classmethod
    def from_env(cls) -> "LocalKeyProvider | None":
        raw = os.environ.get(MASTER_KEY_ENV, "").strip()
        keys = [key.strip() for key in raw.split(",") if key.strip()]
        return cls(keys) if keys else None

    def wrap(self, data_key: bytes) -> bytes:
        return self._keys[0].encrypt(data_key)

    def unwrap(self, wrapped: bytes) -> bytes:
        try:
            return self._all.decrypt(wrapped)
        except InvalidToken:
            raise KeyProviderError(f"{MASTER_KEY_ENV} doesn't unlock this data key") from None

    def is_current(self, wrapped: bytes) -> bool:
        try:
            self._keys[0].decrypt(wrapped)
            return True
        except InvalidToken:
            return False


_FACTORIES: dict[str, Callable[[], KeyProvider | None]] = {LOCAL: LocalKeyProvider.from_env}


def register(name: str, factory: Callable[[], KeyProvider | None]) -> None:
    """Make a provider available by name (a new cloud provider, or a fake in tests)."""
    _FACTORIES[name] = factory


def unregister(name: str) -> None:
    _FACTORIES.pop(name, None)


def active_name() -> str:
    return os.environ.get(PROVIDER_ENV, "").strip().lower() or LOCAL


def provider(name: str) -> KeyProvider | None:
    """The named provider from its settings, or None if its settings aren't given."""
    factory = _FACTORIES.get(name)
    if factory is None:
        if name in PLANNED:
            raise KeyProviderError(
                f"{PLANNED[name]} ({name}) isn't built yet; see DATA_SEGREGATION_PLAN.md §9.6"
            )
        raise KeyProviderError(
            f"Unknown key provider {name!r}; choose one of: {', '.join([*_FACTORIES, *PLANNED])}"
        )
    return factory()


def active_provider() -> KeyProvider | None:
    """The provider that locks data keys (RCM_KEY_PROVIDER), or None when no master key
    is configured: then nothing is encrypted (development)."""
    chosen = provider(active_name())
    if chosen is None and active_name() != LOCAL:
        raise KeyProviderError(f"{PROVIDER_ENV}={active_name()} but its settings aren't given")
    return chosen


def new_local_master_key() -> str:
    return Fernet.generate_key().decode()
