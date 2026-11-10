"""The public website's pilot request form (no sign-in). Requests wait on the Platform page
(data/pilot_requests.py); nothing is created until a platform account approves one."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, StringConstraints

from app.data.pilot_requests import TooManyRequests, get_pilot_requests
from app.services.auth import audit_note

router = APIRouter(prefix="/api/pilot-requests", tags=["pilot requests"])


def _text(longest: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=longest)]


Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=200, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
]


class PilotRequestForm(BaseModel):
    name: _text(100)
    email: Email
    organization: _text(150)
    title: _text(100)
    org_type: _text(60)
    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1500)] = ""
    # Hidden on the form: people leave it empty, form-filling bots don't
    website: str = ""


class Received(BaseModel):
    received: bool = True


@router.post("", response_model=Received, status_code=status.HTTP_202_ACCEPTED)
def submit_pilot_request(body: PilotRequestForm, request: Request) -> Received:
    """Ask for a pilot. A filled-in hidden field gets the usual answer but isn't kept; past
    the limits, 429."""
    if body.website:
        audit_note(request, discarded="honeypot")
        return Received()
    address = request.client.host if request.client else "unknown"
    try:
        saved = get_pilot_requests().submit(address=address, **body.model_dump(exclude={"website"}))
    except TooManyRequests as err:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(err)) from err
    audit_note(request, pilot_request=saved.id)  # the ID only: the details stay in the request
    return Received()
