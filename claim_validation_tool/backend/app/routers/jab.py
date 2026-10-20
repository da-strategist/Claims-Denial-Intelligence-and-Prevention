from fastapi import APIRouter

from app.models import Permission
from app.models.jab import ApiContract
from app.services.auth import require
from app.services.jab import list_contracts

router = APIRouter(
    prefix="/api/jab", tags=["jab-audit"], dependencies=[require(Permission.CLAIMS_READ)]
)


@router.get("/contracts", response_model=list[ApiContract])
def get_contracts() -> list[ApiContract]:
    """Proposed ClaustraRCM <-> JAB Audit API contracts (conceptual; not yet live)."""
    return list_contracts()
