"""
backend/app/services/proctoring_service.py
AI-based proctoring — violation logging, penalty calculation, and summary reporting.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.core.logger import get_logger
from app.db.interview_models import ViolationLogDocument, AssessmentSessionDocument

logger = get_logger(__name__)


# ─── Violation Severity Map ───────────────────────────────────────────────────

VIOLATION_SEVERITY = {
    "tab_switch":           ("medium", 1),
    "window_blur":          ("low",    1),
    "copy_attempt":         ("medium", 2),
    "paste_attempt":        ("medium", 2),
    "right_click":          ("low",    0),
    "devtools_detected":    ("high",   3),
    "face_not_detected":    ("medium", 1),
    "multiple_faces":       ("high",   2),
    "phone_detected":       ("high",   2),
    "suspicious_behavior":  ("high",   2),
    "keyboard_shortcut":    ("low",    1),
}


# ─── Log a Violation ─────────────────────────────────────────────────────────

async def log_violation(
    session_id: str,
    assessment_id: str,
    candidate_id: str,
    violation_type: str,
    description: str = "",
    screenshot_b64: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ViolationLogDocument:
    """Record a proctoring violation event."""
    severity, _ = VIOLATION_SEVERITY.get(violation_type, ("low", 0))

    violation = ViolationLogDocument(
        session_id=session_id,
        assessment_id=assessment_id,
        candidate_id=candidate_id,
        violation_type=violation_type,
        severity=severity,
        description=description or violation_type.replace("_", " ").title(),
        screenshot_b64=screenshot_b64,
        metadata=metadata or {},
    )
    await violation.insert()

    # Update session violation counters
    session = await AssessmentSessionDocument.get(session_id)
    if session:
        field_map = {
            "tab_switch":        "tab_switches",
            "window_blur":       "window_blurs",
            "copy_attempt":      "copy_attempts",
            "paste_attempt":     "paste_attempts",
            "right_click":       "right_clicks",
            "devtools_detected": "devtools_detected",
            "face_not_detected": "face_not_detected",
            "multiple_faces":    "multiple_faces",
            "phone_detected":    "phone_detected",
        }
        field = field_map.get(violation_type)
        updates = {"total_violations": session.total_violations + 1, "last_activity_at": datetime.utcnow()}
        if field:
            updates[field] = getattr(session, field, 0) + 1
        await session.set(updates)

    logger.info(f"[Proctoring] {violation_type} | session={session_id} | severity={severity}")
    return violation


# ─── Penalty Calculation ──────────────────────────────────────────────────────

def calculate_cheating_penalty_from_session(session_data: dict, max_penalty: int = 20) -> int:
    """
    Calculate score penalty from proctoring violations in a session dict.
    
    Penalties:
    - tab_switches: 1pt each (max 5)
    - window_blurs: 1pt each (max 3)
    - copy_attempts: 2pt each (max 6)
    - paste_attempts: 2pt each (max 6)
    - devtools_detected: 3pt each (max 9)
    - face_not_detected + multiple_faces + phone_detected: 1pt each (max 6)
    Total capped at max_penalty (20pts default)
    """
    penalty = 0
    penalty += min(session_data.get("tab_switches", 0) * 1, 5)
    penalty += min(session_data.get("window_blurs", 0) * 1, 3)
    penalty += min(session_data.get("copy_attempts", 0) * 2, 6)
    penalty += min(session_data.get("paste_attempts", 0) * 2, 6)
    penalty += min(session_data.get("devtools_detected", 0) * 3, 9)
    penalty += min(session_data.get("face_not_detected", 0) * 1, 3)
    penalty += min(session_data.get("multiple_faces", 0) * 1, 3)
    penalty += min(session_data.get("phone_detected", 0) * 2, 6)
    return min(penalty, max_penalty)


async def get_violation_summary(session_id: str) -> Dict[str, Any]:
    """Get violation summary for a session."""
    violations = await ViolationLogDocument.find({"session_id": session_id}).to_list()
    session = await AssessmentSessionDocument.get(session_id)

    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for v in violations:
        by_type[v.violation_type] = by_type.get(v.violation_type, 0) + 1
        by_severity[v.severity] = by_severity.get(v.severity, 0) + 1

    penalty = 0
    if session:
        penalty = calculate_cheating_penalty_from_session(session.model_dump(mode="json"))

    return {
        "total_violations": len(violations),
        "by_type": by_type,
        "by_severity": by_severity,
        "cheating_penalty": penalty,
        "high_risk": by_severity.get("high", 0) >= 2 or by_severity.get("critical", 0) >= 1,
        "violations": [
            {
                "type": v.violation_type,
                "severity": v.severity,
                "description": v.description,
                "logged_at": v.logged_at.isoformat(),
            }
            for v in violations[-20:]  # Last 20 violations
        ],
    }


async def generate_cheating_narrative(session_data: dict) -> str:
    """Generate a human-readable cheating summary for the report."""
    tab = session_data.get("tab_switches", 0)
    copy = session_data.get("copy_attempts", 0)
    paste = session_data.get("paste_attempts", 0)
    devtools = session_data.get("devtools_detected", 0)
    no_face = session_data.get("face_not_detected", 0)
    multi_face = session_data.get("multiple_faces", 0)
    total = session_data.get("total_violations", 0)
    penalty = calculate_cheating_penalty_from_session(session_data)

    if total == 0:
        return "No proctoring violations detected. Candidate demonstrated honest test-taking behavior."

    parts = []
    if tab > 0:    parts.append(f"{tab} tab switch(es)")
    if copy > 0:   parts.append(f"{copy} copy attempt(s)")
    if paste > 0:  parts.append(f"{paste} paste attempt(s)")
    if devtools > 0: parts.append(f"{devtools} DevTools opening(s)")
    if no_face > 0:  parts.append(f"face not detected {no_face} time(s)")
    if multi_face > 0: parts.append(f"multiple faces detected {multi_face} time(s)")

    risk = "HIGH" if penalty >= 10 else "MEDIUM" if penalty >= 5 else "LOW"
    return (
        f"Proctoring flagged {total} violation(s): {', '.join(parts)}. "
        f"Risk level: {risk}. Score penalty applied: -{penalty} points."
    )
