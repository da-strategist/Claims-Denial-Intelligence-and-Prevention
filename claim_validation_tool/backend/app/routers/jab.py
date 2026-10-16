from fastapi import APIRouter

from app.models.jab import ApiContract
from app.services.jab import list_contracts

router = APIRouter(prefix="/api/jab", tags=["jab-audit"])


@router.get("/contracts", response_model=list[ApiContract])
def get_contracts() -> list[ApiContract]:
    """Proposed ClaustraRCM <-> JAB Audit API contracts (conceptual; not yet live)."""
    return list_contracts()
