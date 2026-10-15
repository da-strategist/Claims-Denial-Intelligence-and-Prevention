"""Shared types, enums, and helpers used across the domain models."""

import math
from enum import StrEnum
from typing import Annotated, Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
)


def _blank_to_none(value: Any) -> Any:
    """CSV/pandas sources encode missing values as "" or NaN; normalize to None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


OptionalStr = Annotated[str | None, BeforeValidator(_blank_to_none)]

# Identifier formats as they appear in Data/raw_data/
ClaimId = Annotated[str, StringConstraints(pattern=r"^CLM\d{7}$")]
DenialId = Annotated[str, StringConstraints(pattern=r"^DEN\d{7}$")]
LineId = Annotated[str, StringConstraints(pattern=r"^LN\d{8}$")]
PatientId = Annotated[str, StringConstraints(pattern=r"^PAT\d{6}$")]
ProviderId = Annotated[str, StringConstraints(pattern=r"^PROV\d{3}$")]
PayerId = Annotated[str, StringConstraints(pattern=r"^PAY\d{3}$")]
FacilityId = Annotated[str, StringConstraints(pattern=r"^FAC\d{3}$")]
DepartmentId = Annotated[str, StringConstraints(pattern=r"^DEPT\d{2}$")]

Npi = Annotated[str, StringConstraints(pattern=r"^\d{10}$")]
Icd10Code = Annotated[str, StringConstraints(pattern=r"^[A-Z]\d{2}(\.[A-Z0-9]{1,4})?$")]
CptCode = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{5}$")]

Money = Annotated[float, Field(ge=0)]
Ratio = Annotated[float, Field(ge=0, le=1)]


class RecordStatus(StrEnum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class DomainModel(BaseModel):
    """Base for all domain models: ignores unknown columns, coerces CSV strings."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)

    @computed_field
    @property
    def pages(self) -> int:
        return math.ceil(self.total / self.page_size) if self.total else 0
