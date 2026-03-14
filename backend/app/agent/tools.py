"""Tools for the PitchPilot Live coach agent. Uses Pydantic schema for output validation."""
from app.schemas.feedback import (
    RecordFeedbackSchema,
    ValidatedFeedbackResponse,
    validate_feedback_args,
)


def record_feedback(feedback_type: str, message: str) -> dict:
    """
    Record a piece of coaching feedback for the user. Args should be validated
    with RecordFeedbackSchema before calling.

    Args:
        feedback_type: Category: "filler", "pacing", "clarity", "general".
        message: Short, actionable feedback (include slide number when known).
    """
    validated = validate_feedback_args({"feedback_type": feedback_type, "message": message})
    if validated is None:
        return ValidatedFeedbackResponse.error("invalid").model_dump()
    return ValidatedFeedbackResponse(
        status="recorded",
        type=validated.feedback_type,
        message=validated.message,
    ).model_dump()
