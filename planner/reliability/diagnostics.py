import traceback
import uuid
from typing import Any

from backend.app.database import db


def emit_incident(
    workflow_id: str | None,
    node_id: str | None,
    exception: Exception,
    severity: str = "ERROR",
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Emits a structured incident to the immutable DB ledger.
    """
    incident_id = f"inc_{uuid.uuid4().hex[:12]}"

    # Traceback as description
    tb_str = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )

    incident_data = {
        "incident_id": incident_id,
        "workflow_id": workflow_id,
        "node_id": node_id,
        "severity": severity,
        "status": "OPEN",
        "description": f"{type(exception).__name__}: {exception!s}\n{tb_str}",
        "metadata": metadata or {},
    }

    db.create_incident(incident_data)

    # Log an initial event
    db.log_incident_event(
        incident_id,
        "INCIDENT_CREATED",
        {"message": "Incident auto-created from unhandled exception"},
    )

    return incident_id
