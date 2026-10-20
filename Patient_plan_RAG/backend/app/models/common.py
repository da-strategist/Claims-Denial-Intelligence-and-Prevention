"""Shared types and base models."""

import math
from typing import Generic, TypeVar

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# Attached to every API response (body field and/or X-Disclaimer header).
DISCLAIMER = (
    "This tool provides AI-generated interpretations of insurance "
    "policy language. It does not constitute coverage determinations, "
    "legal advice, or guarantees of benefits."
)


# Document IDs are used as file names (chunks/<id>.json), so restrict them
# to a safe alphabet; this also blocks path traversal like "../x".
DOCUMENT_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
DocumentId = Annotated[str, StringConstraints(pattern=DOCUMENT_ID_PATTERN)]

MAX_QUESTION_CHARS = 2000
MAX_SERVICE_CHARS = 200
MAX_CODE_CHARS = 20


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)

    @computed_field
    @property
    def pages(self) -> int:
        return math.ceil(self.total / self.page_size) if self.total else 0
