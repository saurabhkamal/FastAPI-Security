import uuid
from datetime import datetime, timezone

from app.store import AUDIT_LOGS


def log_audit_event(action: str, actor_email: str, target: str) -> None:
    AUDIT_LOGS.append(
        {
            "id": str(uuid.uuid4()),
            "action": action,
            "actor_email": actor_email,
            "target": target,
            "timestamp": datetime.now(timezone.utc),
        }
    )
