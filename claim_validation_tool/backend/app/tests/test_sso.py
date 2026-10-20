"""Single sign-on through an organisation's identity provider (a stand-in here; real ones
plug in the same way), and the SSO-only rule for passwords."""

import re
from urllib.parse import parse_qs, urlparse

import pytest

from app.data.audit import get_audit_log
from app.models import Role
from app.services.identity_providers import Identity, IdentityProviderError, register, unregister
from app.tests.conftest import TEST_PASSWORD, TestClient, sign_in

SSO = {"provider": "test-idp", "settings": {"issuer": "https://idp.example"}}


class FakeIdp:
    """Signs in whoever `next_subject` names, echoing the nonce like a real ID token."""

    name = "test-idp"

    def __init__(self) -> None:
        self.next_subject = "Amina.Bello@meridian.example"

    def authorization_url(self, settings, *, state, nonce, redirect_uri):
        return f"{settings['issuer']}/authorize?state={state}&nonce={nonce}&redirect_uri={redirect_uri}"

    def complete(self, settings, params, *, nonce, redirect_uri):
        if params.get("nonce") != nonce or params.get("code") != "good":
            raise IdentityProviderError("the identity provider's response didn't check out")
        return Identity(subject=self.next_subject)


@pytest.fixture
def idp():
    fake = FakeIdp()
    register("test-idp", fake)
    yield fake
    unregister("test-idp")


def connect(client, enforced=False):
    sign_in(client, Role.PLATFORM)
    return client.put("/api/platform/organisations/meridian/sso", json={**SSO, "enforced": enforced})


def link(client, username, **changes):
    sign_in(client, Role.ADMIN)
    res = client.patch(f"/api/users/{username}", json=changes)
    assert res.status_code == 200, res.text
    return res.json()


def sso_sign_in(client, code="good", org="meridian"):
    """Follow the flow as a browser would, the identity provider answering `code`."""
    start = client.get(f"/api/auth/sso/{org}/start", follow_redirects=False)
    assert start.status_code == 302, start.text
    query = parse_qs(urlparse(start.headers["location"]).query)
    callback = urlparse(query["redirect_uri"][0]).path
    return client.get(
        callback,
        params={"state": query["state"][0], "nonce": query["nonce"][0], "code": code},
        follow_redirects=False,
    )


def test_signing_in_through_the_organisations_identity_provider(client, idp):
    assert connect(client).status_code == 200
    assert link(client, "biller1", sso_id="amina.bello@meridian.example")["sso_id"] == "amina.bello@meridian.example"
    with TestClient(client.app) as browser:
        res = sso_sign_in(browser)
        assert res.status_code == 302 and res.headers["location"] == "/"
        me = browser.get("/api/auth/me").json()
        assert (me["username"], me["organisation"]["id"]) == ("biller1", "meridian")
    events = get_audit_log("meridian").events()
    assert any(e.action == "GET /api/auth/sso/{org_id}/callback" and e.username == "biller1" for e in events)


def test_responses_that_dont_check_out_are_refused(client, idp):
    connect(client)
    link(client, "biller1", sso_id="amina.bello@meridian.example")
    with TestClient(client.app) as browser:
        assert sso_sign_in(browser, code="forged").status_code == 401
        # A state can't be reused, or carried to another organisation
        start = browser.get("/api/auth/sso/meridian/start", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        assert browser.get("/api/auth/sso/lakeside/callback", params={"state": state, "code": "good"}).status_code == 404
        assert browser.get("/api/auth/sso/meridian/callback", params={"state": "made-up", "code": "good"}).status_code == 400
        assert browser.get("/api/auth/me").status_code == 401


def test_only_linked_active_accounts_in_that_organisation_get_in(client, idp):
    connect(client)
    with TestClient(client.app) as browser:
        assert sso_sign_in(browser).status_code == 403  # nobody linked yet
    link(client, "biller1", sso_id="amina.bello@meridian.example")
    link(client, "biller1", active=False)
    with TestClient(client.app) as browser:
        assert sso_sign_in(browser).status_code == 403
    # Lakeside has no SSO; Meridian's identity provider can't reach it
    with TestClient(client.app) as browser:
        assert browser.get("/api/auth/sso/lakeside/start", follow_redirects=False).status_code == 404


def test_sso_only_refuses_passwords_except_break_glass_admins(client, idp):
    assert connect(client, enforced=True).status_code == 409  # no break-glass admin yet
    sign_in(client, Role.ADMIN)
    assert client.patch("/api/users/biller1", json={"break_glass": True}).status_code == 422  # admins only
    link(client, "admin1", break_glass=True)
    assert connect(client, enforced=True).status_code == 200
    with TestClient(client.app) as browser:
        res = browser.post("/api/auth/login", json={"username": "biller1", "password": TEST_PASSWORD})
        assert res.status_code == 403 and "single sign-on" in res.text
        assert browser.post("/api/auth/login", json={"username": "admin1", "password": TEST_PASSWORD}).status_code == 200
    # The last break-glass administrator can't be removed while it's SSO only
    sign_in(client, Role.ADMIN)
    assert client.patch("/api/users/admin1", json={"break_glass": False}).status_code == 409


def test_sso_ids_are_unique_in_the_organisation(client):
    link(client, "biller1", sso_id="amina@meridian.example")
    assert client.patch("/api/users/analyst1", json={"sso_id": "AMINA@meridian.example"}).status_code == 409
    assert link(client, "biller1", sso_id="")["sso_id"] is None  # cleared


@pytest.mark.parametrize(
    ("provider", "message"),
    [("oidc", "OpenID Connect .* isn't built yet"), ("okta-ish", "Unknown identity provider")],
)
def test_unbuilt_or_unknown_providers_cant_be_connected(client, provider, message):
    sign_in(client, Role.PLATFORM)
    res = client.put("/api/platform/organisations/meridian/sso", json={"provider": provider})
    assert res.status_code == 422
    assert re.search(message, res.json()["detail"])


def test_only_the_platform_connects_sso(client, idp):
    assert client.put("/api/platform/organisations/meridian/sso", json=SSO).status_code == 403
    connect(client)
    assert client.get("/api/platform/organisations").json()[1]["sso"]["provider"] == "test-idp"
    assert client.delete("/api/platform/organisations/meridian/sso").json()["sso"] is None
