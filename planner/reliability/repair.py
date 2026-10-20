import time
import uuid

from backend.app.database import db


def propose_repair(incident_id: str, proposed_diff: str) -> str:
    """
    Creates a repair plan for an incident and forces human approval.
    """
    repair_id = f"rep_{uuid.uuid4().hex[:12]}"

    # We create an approval record (from Phase 4 framework)
    approval_id = f"app_{uuid.uuid4().hex[:12]}"

    db.save_approval(
        {
            "approval_id": approval_id,
            "task_id": "REPAIR_SYSTEM",  # Virtual task ID for repairs
            "decision_id": f"dec_rep_{repair_id}",
            "action": "APPLY_SELF_REPAIR",
            "target_identifier": incident_id,
            "risk_level": "HIGH",
            "state": "PENDING",
            "created_at": time.time(),
            "expires_at": time.time() + 3600,  # 1 hour to approve
            "payload": {"diff": proposed_diff},
        }
    )

    # Now we save the repair plan
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO repair_plans (
                repair_id, incident_id, status, proposed_diff, human_approval_id,
                created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repair_id,
                incident_id,
                "AWAITING_APPROVAL",
                proposed_diff,
                approval_id,
                time.time(),
                time.time(),
                "{}",
            ),
        )

    db.update_incident_status(incident_id, "REPAIRING")

    return repair_id


def apply_repair(repair_id: str) -> bool:
    """
    Applies the repair ONLY if human approval was granted.
    """
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM repair_plans WHERE repair_id = ?", (repair_id,))
        repair = cursor.fetchone()

        if not repair:
            return False

        approval = db.get_approval(repair["human_approval_id"])
        if not approval or approval["state"] != "GRANTED":
            # Safety Guard: Cannot apply without explicit human approval
            return False

        # In a real system we would apply the diff using `patch`
        # For Phase 9 reliability scope, we just mark it resolved

        conn.execute(
            "UPDATE repair_plans SET status = ?, updated_at = ? WHERE repair_id = ?",
            ("APPLIED", time.time(), repair_id),
        )

    # Call this outside the with block to avoid sqlite write lock collision
    db.update_incident_status(repair["incident_id"], "RESOLVED")

    return True


# Helper to add to DB manager for updates
def update_incident_status(incident_id: str, status: str):
    with db.connection() as conn:
        conn.execute(
            "UPDATE incidents SET status = ?, updated_at = ? WHERE incident_id = ?",
            (status, time.time(), incident_id),
        )


db.update_incident_status = update_incident_status
