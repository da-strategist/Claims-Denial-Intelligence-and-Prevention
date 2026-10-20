"""Facility model — mirrors dim_facilities.csv."""

from app.models.common import DomainModel, FacilityId, RecordStatus


class Facility(DomainModel):
    facility_id: FacilityId
    facility_name: str
    facility_type: str
    status: RecordStatus
    address: str = ""  # one line, e.g. "4200 Providence Rd, Charlotte, NC 28211"
    tax_id: str = ""
