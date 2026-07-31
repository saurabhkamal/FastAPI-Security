from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas import AuditLogEntry
from app.security import CurrentUser, require_api_key, require_role
from app.store import AUDIT_LOGS

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_api_key)])


@router.get("/audit-logs", response_model=list[AuditLogEntry])
def get_audit_logs(current_user: Annotated[CurrentUser, Depends(require_role("admin"))]):
    return list(reversed(AUDIT_LOGS))
