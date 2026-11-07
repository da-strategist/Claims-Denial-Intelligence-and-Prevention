"""Claim upload: a CSV/Excel file in the template's layout, or an X12 837, read into
Draft claims. Each claim in the file is saved or reported back on its own."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.models.claim import Claim
from app.models.rule import ClaimValidation

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_CLAIMS = 200

ImportFileType = Literal["csv", "xlsx", "837P", "837I"]


class ClaimImportRequest(BaseModel):
    filename: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    content: str = Field(description="The file's bytes, base64-encoded")


class ImportedClaim(BaseModel):
    """A claim from the file, saved as a Draft and validated."""

    ref: str = Field(description="The file's own reference: claim_ref (CSV) or CLM01 (837)")
    where: str = Field(description="Where it is in the file, e.g. rows 2-3")
    claim: Claim
    validation: ClaimValidation
    notes: list[str] = Field(
        default_factory=list, description="What was assumed while reading it, to check"
    )


class ImportFailure(BaseModel):
    """A claim from the file that couldn't be saved, and why."""

    ref: str
    where: str
    errors: list[str]


class ClaimImportResult(BaseModel):
    file_type: ImportFileType
    claims_found: int
    created: list[ImportedClaim]
    failed: list[ImportFailure]
