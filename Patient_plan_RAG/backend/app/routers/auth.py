"""Sign in, sign out, current user, and password change."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..auth.sessions import (
    SESSION_COOKIE,
    SESSION_MAX_SECONDS,
    cookie_secure,
    identity_provider,
    login_throttle,
    sessions,
    signed_in,
)
from ..auth.users import Role, User, user_store
from ..services import records

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Registration(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ProviderRegistration(BaseModel):
    """A provider organisation signs itself up; the person signing up becomes
    its first provider admin. The organisation starts pending approval."""
    org_name: str = Field(min_length=2, max_length=200)
    category: str = Field(max_length=40)
    npi: str = Field("", pattern=r"^(\d{10})?$")
    address: str = Field("", max_length=300)
    city: str = Field(min_length=1, max_length=100)
    phone: str = Field("", max_length=40)
    full_name: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def account(user: User) -> dict:
    """The signed-in user plus their provider's name and approval status."""
    data = user.public()
    org = records.orgs.get(user.org_id) if user.org_id else None
    if org:
        data |= {"org_name": org.name, "org_category": org.category, "org_status": org.status}
    if user.role is Role.PLATFORM_ADMIN:  # for the navigation badge
        data["pending_providers"] = sum(1 for o in records.orgs.all() if o.status == records.PENDING)
    return data


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MAX_SECONDS, httponly=True,
        samesite="strict", secure=cookie_secure(), path="/",
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict:
    username = body.username.strip().lower()
    request.state.audit_username = username  # the attempt is audited, success or not
    if wait := login_throttle.locked_for(username):
        raise HTTPException(429, "Too many failed sign-in attempts. Try again later.",
                            headers={"Retry-After": str(max(1, round(wait)))})
    user = identity_provider.authenticate(username, body.password)
    if user is None:
        login_throttle.failed(username)
        # same message for unknown user and wrong password
        raise HTTPException(401, "Incorrect email or password")
    login_throttle.succeeded(username)
    org = records.orgs.get(user.org_id) if user.org_id else None
    if org and org.status == records.REJECTED:
        note = f" Reason: {org.review_note}" if org.review_note else ""
        raise HTTPException(403, "Your provider sign-up was not approved. Contact the "
                                 f"platform administrator.{note}")
    user = user_store.update(user.username, last_sign_in=datetime.now(UTC).isoformat())
    _set_cookie(response, sessions.start(user.username))
    return account(user)


@router.post("/register")
async def register(body: Registration, request: Request, response: Response) -> dict:
    """Self sign-up for individuals (provider staff are added by their
    provider admin). Signs the new user in."""
    username = body.username.strip().lower()
    request.state.audit_username = username
    try:
        user = user_store.create(username, body.password, Role.INDIVIDUAL,
                                 must_change_password=False)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _set_cookie(response, sessions.start(user.username))
    return account(user)


@router.post("/register/provider")
async def register_provider(body: ProviderRegistration, request: Request,
                            response: Response) -> dict:
    """Self sign-up for a provider organisation. It stays pending (not listed
    for sharing, no uploads or patient records) until the platform admin
    approves it. Signs the new provider admin in."""
    username = body.username.strip().lower()
    request.state.audit_username = username
    if body.category not in records.PROVIDER_CATEGORIES:
        raise HTTPException(400, "Choose a provider category.")
    if user_store.get(username):
        raise HTTPException(400, f"An account for {username} already exists.")
    org = records.orgs.add(records.Org(
        records.new_id(), body.org_name.strip(), category=body.category,
        status=records.PENDING, npi=body.npi, address=body.address.strip(),
        city=body.city.strip(), phone=body.phone.strip(), contact_email=username,
        signed_up_by=username))
    try:
        user = user_store.create(username, body.password, Role.HOSPITAL_ADMIN,
                                 org_id=org.org_id, must_change_password=False)
        user = user_store.update(username, full_name=body.full_name.strip())
    except ValueError as exc:
        records.orgs.remove(org.org_id)
        raise HTTPException(400, str(exc)) from exc
    _set_cookie(response, sessions.start(user.username))
    return account(user)


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    if token := request.cookies.get(SESSION_COOKIE):
        sessions.end(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signed_out": True}


@router.get("/me")
async def me(user: User = Depends(signed_in)) -> dict:
    return account(user)


@router.post("/password")
async def change_password(body: PasswordChange, response: Response,
                          user: User = Depends(signed_in)) -> dict:
    if identity_provider.authenticate(user.username, body.current_password) is None:
        raise HTTPException(400, "Current password is incorrect")
    if body.new_password == body.current_password:
        raise HTTPException(400, "New password must be different")
    try:
        updated = user_store.update(user.username, password=body.new_password,
                                    must_change_password=False)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # sign out every other session, then issue a fresh one for this browser
    sessions.end_all_for(user.username)
    _set_cookie(response, sessions.start(user.username))
    return account(updated)
