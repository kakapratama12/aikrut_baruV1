# services/session.py
#
# State machine validator dan transition logic untuk Assessment Sessions.
# Setiap transition di-validate — tidak boleh skip state.

from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import HTTPException
from backend.config import db

# Valid state transitions map
VALID_TRANSITIONS = {
    "pending": ["in_progress"],
    "in_progress": ["completed"],
    "completed": ["pending_review"],
    "pending_review": ["approved", "overridden", "request_more_info"],
    "request_more_info": ["pending_review"],
    # Terminal states — tidak bisa transition lagi
    "approved": [],
    "overridden": [],
}

def validate_transition(current_status: str, new_status: str) -> bool:
    """Check if a state transition is allowed."""
    allowed = VALID_TRANSITIONS.get(current_status, [])
    return new_status in allowed


async def transition_session_status(
    session_id: str,
    new_status: str,
    company_id: str,
    override_reason: Optional[str] = None,
    reviewer_id: Optional[str] = None
) -> dict:
    """
    Execute a validated state transition on an assessment session.
    Returns the updated session document.
    """
    session = await db.assessment_sessions.find_one({
        "id": session_id,
        "company_id": company_id
    })

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_status = session.get("status")

    if not validate_transition(current_status, new_status):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current_status} → {new_status}. "
                   f"Allowed transitions from '{current_status}': {VALID_TRANSITIONS.get(current_status, [])}"
        )

    # Enforce override_reason jika status overridden
    if new_status == "overridden" and not override_reason:
        raise HTTPException(
            status_code=400,
            detail="override_reason wajib diisi saat status overridden"
        )

    update_fields = {
        "status": new_status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    if override_reason:
        update_fields["override_reason"] = override_reason
    if reviewer_id:
        update_fields["reviewer_id"] = reviewer_id
    if new_status in ["approved", "overridden"]:
        update_fields["decided_at"] = datetime.now(timezone.utc).isoformat()

    await db.assessment_sessions.update_one(
        {"id": session_id},
        {"$set": update_fields}
    )

    # Trigger Phase 2 Task 5 computation if transitioning to completed
    if new_status == "completed":
        from backend.services.scoring import compute_competency_profile
        
        competency_scores = await compute_competency_profile(
            session_id=session_id,
            company_id=company_id
        )

        profile_id = str(uuid.uuid4())
        profile = {
            "id": profile_id,
            "session_id": session_id,
            "person_id": session["person_id"],
            "company_id": company_id,
            "competency_scores": competency_scores,
            "raw_evidence": session.get("session_evidence", []),
            "raw_roleplay": session.get("roleplay_result", {}),
            "narrative": {},    # Diisi di Phase 3 Task 2 (AI Narrative Generator)
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.competency_profiles.insert_one(profile)

        # Update returned session object with new status for recursive call safety
        session_copy = session.copy()
        session_copy.update(update_fields)

        # Auto-transition ke pending_review
        return await transition_session_status(
            session_id, "pending_review", company_id, override_reason, reviewer_id
        )

    return {**session, **update_fields}


async def notify_employee(person_id: str, session_id: str, notification_type: str):
    """
    MVP: Log notification intent.
    Phase 3 Task 8: Replace dengan actual email/in-app notification.
    """
    employee = await db.employees.find_one({"id": person_id})
    if employee:
        print(f"[NOTIFICATION] {notification_type} → {employee.get('email')} | session: {session_id}")
        # TODO Phase 3 Task 8: implement actual email send
    else:
        # Fallback: try users collection
        user = await db.users.find_one({"id": person_id})
        if user:
            print(f"[NOTIFICATION] {notification_type} → {user.get('email')} | session: {session_id}")
