"""Single sign-on: the identity providers an organisation's people can sign in through.

Each organisation may connect its own identity provider (Organisation.sso). Sign-in then
goes:

    GET /api/auth/sso/{org}/start      -> redirect to the provider's sign-in page
    GET /api/auth/sso/{org}/callback   <- the provider sends the person back; the app checks
                                          the response, finds the account whose SSO ID
                                          matches, and starts a session

Planned providers, not built yet (an organisation can't be connected to one until it is):

    oidc   OpenID Connect: Microsoft Entra ID, Okta, Google Workspace, Auth0, Keycloak, …
    saml   SAML 2.0: older setups such as ADFS

Adding one: a class with `name`, `authorization_url(...)`, and `complete(...)` (see
IdentityProvider), and one `register(name, provider)` call. Its secrets (e.g. an OIDC
client secret) come from the environment or a secret store, never from
organisations.json, which only holds non-secret settings (issuer URL, client ID).
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from threading import Lock
from typing import Protocol

PLANNED = {
    "oidc": "OpenID Connect (Microsoft Entra ID, Okta, Google Workspace, …)",
    "saml": "SAML 2.0",
}
STATE_LIFETIME = timedelta(minutes=10)


class IdentityProviderError(RuntimeError):
    """A provider that isn't built or set up, or a sign-in response it rejected."""


@dataclass(frozen=True)
class Identity:
    """Who the identity provider says signed in."""

    subject: str  # matched (case-insensitively) to an account's SSO ID
    email: str | None = None


class IdentityProvider(Protocol):
    name: str

    def authorization_url(
        self, settings: dict[str, str], *, state: str, nonce: str, redirect_uri: str
    ) -> str:
        """Where to send the person to sign in."""
        ...

    def complete(
        self, settings: dict[str, str], params: dict[str, str], *, nonce: str, redirect_uri: str
    ) -> Identity:
        """Check the provider's response (signature, audience, nonce, expiry) and return
        who signed in; raise IdentityProviderError if anything doesn't check out."""
        ...


_PROVIDERS: dict[str, IdentityProvider] = {}


def register(name: str, provider: IdentityProvider) -> None:
    _PROVIDERS[name] = provider


def unregister(name: str) -> None:
    _PROVIDERS.pop(name, None)


def get_provider(name: str) -> IdentityProvider:
    provider = _PROVIDERS.get(name)
    if provider is not None:
        return provider
    if name in PLANNED:
        raise IdentityProviderError(
            f"{PLANNED[name]} sign-in isn't built yet; see DATA_SEGREGATION_PLAN.md §9.7"
        )
    raise IdentityProviderError(
        f"Unknown identity provider {name!r}; choose one of: {', '.join([*_PROVIDERS, *PLANNED])}"
    )


@dataclass
class _Pending:
    org_id: str
    nonce: str
    expires_at: datetime


class SsoStateStore:
    """Sign-ins in progress. Each `state` is random, tied to one organisation, used once,
    and expires, so a provider response can't be replayed or sent to another organisation."""

    def __init__(self) -> None:
        self._pending: dict[str, _Pending] = {}
        self._lock = Lock()

    def start(self, org_id: str) -> tuple[str, str]:
        """(state, nonce) for a new sign-in."""
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        with self._lock:
            self._pending = {k: p for k, p in self._pending.items() if p.expires_at > now}
            self._pending[state] = _Pending(org_id, nonce, now + STATE_LIFETIME)
        return state, nonce

    def finish(self, state: str, org_id: str) -> str | None:
        """The sign-in's nonce if `state` is current and for this organisation, else None.
        Either way the state can't be used again."""
        with self._lock:
            pending = self._pending.pop(state, None)
        if pending is None or pending.org_id != org_id or pending.expires_at <= datetime.now(UTC):
            return None
        return pending.nonce


@lru_cache(maxsize=1)
def get_sso_states() -> SsoStateStore:
    return SsoStateStore()
