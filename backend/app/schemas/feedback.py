"""Pydantic schemas for coach feedback (record_feedback tool) output validation."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


FEEDBACK_TYPES = Literal["filler", "pacing", "clarity", "general"]


class RecordFeedbackSchema(BaseModel):
    """Schema for record_feedback tool call arguments. Validates and normalizes agent output."""

    feedback_type: Literal["filler", "pacing", "clarity", "general"] = Field(
        description="Category of feedback",
    )
    message: str = Field(
        min_length=5,
        max_length=500,
        description="Short, actionable feedback. Include slide number when known, e.g. 'Slide 2: Slow down.'",
    )

    @field_validator("feedback_type", mode="before")
    @classmethod
    def normalize_feedback_type(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return "general"
        v = v.strip().lower()
        if v in ("filler", "pacing", "clarity", "general"):
            return v
        return "general"

    @field_validator("message", mode="before")
    @classmethod
    def clean_message(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("message is required")
        s = v.strip()
        # Reject tool syntax or obvious non-feedback
        if "record_feedback" in s.lower():
            raise ValueError("message must be natural language only")
        if len(s) < 5:
            raise ValueError("message too short")
        return s[:500]


class ValidatedFeedbackResponse(BaseModel):
    """Response returned by record_feedback after validation. Used as agent tool result."""

    status: Literal["recorded", "error"] = "recorded"
    type: str = "general"
    message: str = ""

    @classmethod
    def error(cls, reason: str = "invalid") -> "ValidatedFeedbackResponse":
        return cls(status="error", type="", message=reason)


def validate_feedback_args(args: dict | None) -> RecordFeedbackSchema | None:
    """
    Validate raw tool call args against RecordFeedbackSchema.
    Returns validated schema if valid, None otherwise.
    """
    if not args or not isinstance(args, dict):
        return None
    try:
        return RecordFeedbackSchema.model_validate(args)
    except Exception:
        return None
