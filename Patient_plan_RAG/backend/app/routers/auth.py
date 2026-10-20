"""Sign in, sign out, current user, and password change."""

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

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Registration(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


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
    _set_cookie(response, sessions.start(user.username))
    return user.public()


@router.post("/register")
async def register(body: Registration, request: Request, response: Response) -> dict:
    """Self sign-up for individuals (hospital accounts are created by their
    hospital admin). Signs the new user in."""
    username = body.username.strip().lower()
    request.state.audit_username = username
    try:
        user = user_store.create(username, body.password, Role.INDIVIDUAL,
                                 must_change_password=False)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _set_cookie(response, sessions.start(user.username))
    return user.public()


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    if token := request.cookies.get(SESSION_COOKIE):
        sessions.end(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signed_out": True}


@router.get("/me")
async def me(user: User = Depends(signed_in)) -> dict:
    return user.public()


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
    return updated.public()
