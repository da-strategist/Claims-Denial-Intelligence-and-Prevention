"""Sign in and out: with a password, or through the organisation's single sign-on
(services/identity_providers.py). Accounts are managed on the Users page or with
`python -m app.users`."""

from typing import Annotated

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.data.users import UserStore, get_user_store
from app.data.emergency import get_emergency_access
from app.data.orgs import OrgId, OrgStatus, get_org_registry
from app.data.repository import get_repository
from app.models import CurrentUser, EmergencySummary, LoginRequest, OrganisationSummary, User
from app.services.auth import (
    SESSION_COOKIE,
    LoginThrottle,
    SessionStore,
    SignedIn,
    audit_note,
    cookie_secure,
    get_login_throttle,
    get_session_store,
    organisation_problem,
)
from app.services.identity_providers import (
    IdentityProviderError,
    SsoStateStore,
    get_provider,
    get_sso_states,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

Sessions = Annotated[SessionStore, Depends(get_session_store)]

BAD_LOGIN = "Wrong username or password"


def _access(user: User) -> str | None:
    """'Cardiology · Main Campus · Dr. Carol Robinson' for a limited account, else None."""
    scope = user.effective_scope
    if not scope.restricted:
        return None
    repo = get_repository(user.organisation_id)
    names = {d.department_id: d.department_name for d in repo.list_departments()}
    names |= {f.facility_id: f.facility_name for f in repo.list_facilities()}
    names |= {p.provider_id: p.provider_name for p in repo.list_providers()}
    return " · ".join(names.get(i, i) for i in (*scope.departments, *scope.facilities, *scope.providers))


def _current(user: User, sessions: SessionStore, created) -> CurrentUser:
    org = get_org_registry().get(user.organisation_id) if user.organisation_id else None
    grant = get_emergency_access().active_for(user.username) if user.emergency_access_id else None
    return CurrentUser(
        username=user.username,
        organisation=OrganisationSummary(id=org.id, name=org.name) if org else None,
        emergency=EmergencySummary(id=grant.id, reason=grant.reason, expires_at=grant.expires_at)
        if grant
        else None,
        access=_access(user) if org else None,
        display_name=user.display_name,
        role=user.role,
        permissions=sorted(user.permissions),
        session_expires_at=sessions.expires_at(created),
        idle_timeout_minutes=int(sessions.idle.total_seconds() // 60),
    )


@router.post("/login", response_model=CurrentUser)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    users: Annotated[UserStore, Depends(get_user_store)],
    sessions: Sessions,
    throttle: Annotated[LoginThrottle, Depends(get_login_throttle)],
) -> CurrentUser:
    """Check the password and set the session cookie."""
    username = body.username.strip().lower()
    audit_note(request, attempted_username=username)
    if throttle.locked(username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-ins. Try again in 15 minutes.",
        )
    user = users.authenticate(username, body.password)
    if user is None:
        throttle.failed(username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=BAD_LOGIN)
    throttle.succeeded(username)
    problem = organisation_problem(user)
    if problem:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=problem)
    org = get_org_registry().get(user.organisation_id) if user.organisation_id else None
    if org and org.sso and org.sso.enforced and not user.break_glass:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{org.name} signs in with single sign-on, not a password",
        )
    token = _start_session(response, user, sessions)
    request.state.user = user
    return _current(user, sessions, sessions.touch(token))


def _start_session(response: Response, user: User, sessions: SessionStore) -> str:
    token = sessions.create(user.username)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        # Strict holds for SSO too: the page the provider redirects to is ours, and its
        # requests to the API are same-site
        samesite="strict",
        secure=cookie_secure(),
        path="/api",
        max_age=int(sessions.max_age.total_seconds()),
    )
    return token


SsoStates = Annotated[SsoStateStore, Depends(get_sso_states)]


def _sso_org(org_id: str):
    org = get_org_registry().get(org_id)
    if org is None or org.status != OrgStatus.ACTIVE or org.sso is None:
        raise HTTPException(status_code=404, detail="Single sign-on isn't set up for that organisation")
    try:
        return org, get_provider(org.sso.provider)
    except IdentityProviderError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err


def _callback_url(request: Request, org_id: str) -> str:
    """Registered with the identity provider. RCM_PUBLIC_URL behind a proxy (Caddy)."""
    base = os.environ.get("RCM_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/auth/sso/{org_id}/callback"


@router.get("/sso/{org_id}/start")
def sso_start(org_id: OrgId, request: Request, states: SsoStates) -> RedirectResponse:
    """Send the browser to the organisation's identity provider to sign in."""
    org, provider = _sso_org(org_id)
    state, nonce = states.start(org_id)
    audit_note(request, organisation=org_id)
    url = provider.authorization_url(
        org.sso.settings, state=state, nonce=nonce, redirect_uri=_callback_url(request, org_id)
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/sso/{org_id}/callback")
def sso_callback(
    org_id: OrgId,
    request: Request,
    states: SsoStates,
    sessions: Sessions,
    users: Annotated[UserStore, Depends(get_user_store)],
) -> RedirectResponse:
    """Where the identity provider sends the person back. The response is checked, the
    account linked to who signed in is found, and a session starts; then on to the app."""
    org, provider = _sso_org(org_id)
    params = dict(request.query_params)
    nonce = states.finish(params.get("state", ""), org_id)
    if nonce is None:
        raise HTTPException(status_code=400, detail="This sign-in expired or was already used; start again")
    try:
        identity = provider.complete(
            org.sso.settings, params, nonce=nonce, redirect_uri=_callback_url(request, org_id)
        )
    except IdentityProviderError as err:
        raise HTTPException(status_code=401, detail=f"Single sign-on failed: {err}") from err
    user = users.by_sso_id(org_id, identity.subject)
    audit_note(request, attempted_username=user.username if user else None, sso_subject_known=user is not None)
    if user is None or not user.active:
        raise HTTPException(
            status_code=403,
            detail=f"No active {org.name} account is linked to this sign-in; ask an administrator",
        )
    if organisation_problem(user):
        raise HTTPException(status_code=403, detail=organisation_problem(user))
    response = RedirectResponse(os.environ.get("RCM_PUBLIC_URL", "") + "/", status_code=status.HTTP_302_FOUND)
    _start_session(response, user, sessions)
    request.state.user = user
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, user: SignedIn, sessions: Sessions) -> Response:
    """End this session and clear the cookie."""
    sessions.end(request.cookies[SESSION_COOKIE])
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/api")
    return response


@router.get("/me", response_model=CurrentUser)
def me(request: Request, user: SignedIn, sessions: Sessions) -> CurrentUser:
    """Who is signed in, with their role's permissions. 401 when signed out."""
    return _current(user, sessions, request.state.session)
