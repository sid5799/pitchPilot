"""Tools for the PitchPilot Live coach agent."""


def record_feedback(feedback_type: str, message: str) -> dict:
    """
    Record a piece of coaching feedback for the user.

    Call this when you want to log a specific feedback item (e.g. filler word, pacing tip)
    so it can be shown in the UI. Keep messages one short sentence.

    Args:
        feedback_type: Category of feedback: "filler", "pacing", "clarity", "general".
        message: Short, actionable feedback text for the presenter.
    """
    # No-op for now; WebSocket handler can surface tool calls as feedback in coach-feedback todo
    return {"status": "recorded", "type": feedback_type, "message": message}
