"""Hospital department model — mirrors dim_departments.csv."""

from pydantic import Field

from app.models.common import DepartmentId, DomainModel, Ratio


class Department(DomainModel):
    department_id: DepartmentId
    department_name: str
    service_line: str
    claim_share: Ratio
    pa_frequency: Ratio = Field(description="Share of the department's claims that need prior auth")
    avg_daily_volume: int = Field(ge=0)
