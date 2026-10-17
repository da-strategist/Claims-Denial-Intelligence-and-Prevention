"""Sign in and out. Accounts are managed with `python -m app.users`."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.data.users import UserStore, get_user_store
from app.models import CurrentUser, LoginRequest, User
from app.services.auth import (
    SESSION_COOKIE,
    LoginThrottle,
    SessionStore,
    SignedIn,
    audit_note,
    cookie_secure,
    get_login_throttle,
    get_session_store,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

Sessions = Annotated[SessionStore, Depends(get_session_store)]

BAD_LOGIN = "Wrong username or password"


def _current(user: User, sessions: SessionStore, created) -> CurrentUser:
    return CurrentUser(
        username=user.username,
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

    token = sessions.create(user.username)
    request.state.user = user
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=cookie_secure(),
        path="/api",
        max_age=int(sessions.max_age.total_seconds()),
    )
    return _current(user, sessions, sessions.touch(token))


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
