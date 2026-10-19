"""Shared types and base models."""

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# Attached to every API response (body field and/or X-Disclaimer header).
DISCLAIMER = (
    "This tool provides AI-generated interpretations of insurance "
    "policy language. It does not constitute coverage determinations, "
    "legal advice, or guarantees of benefits."
)


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
