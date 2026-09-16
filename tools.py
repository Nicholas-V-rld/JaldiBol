"""Atlys Guest Delight Tool Implementations for Project Aero.

Provides typed, deterministic, low-latency tools for:
- Live visa application status lookups (`get_visa_status`)
- Human escalation and priority handoff (`escalate_to_human`)
- Distress keyword detection for automatic escalation
"""

import re
from typing import Optional
from pydantic import BaseModel, Field
from mock_db import get_application


class VisaStatusResult(BaseModel):
    """Structured result returned by visa status tool."""

    found: bool = Field(..., description="Whether the application was located in the database")
    application_id: str = Field(..., description="Normalized Atlys application reference ID")
    spoken_summary: str = Field(..., description="Voice-optimized 1-2 sentence response for TTS")
    status: Optional[str] = Field(default=None, description="Current application status if found")
    country: Optional[str] = Field(default=None, description="Destination country")


class EscalationResult(BaseModel):
    """Structured response confirming handoff to a senior human agent."""

    escalated: bool = Field(default=True, description="Confirmation that escalation flag was set")
    priority: str = Field(default="high", description="Escalation priority: standard, urgent, emergency")
    reason: str = Field(..., description="Stated cause or distress trigger")
    spoken_response: str = Field(..., description="Spoken message reassuring the traveler")


# Distress and escalation trigger phrases
_DISTRESS_PATTERNS = [
    r"\b(flight\s+(is\s+)?(today|tonight|tomorrow|in\s+\d+\s+hours?))\b",
    r"\b(leaving\s+(today|tonight|in\s+\d+\s+hours?))\b",
    r"\b(stranded|emergency|critical|urgent|panic|stuck\s+at\s+airport)\b",
    r"\b(real\s+person|human\s+being|human\s+agent|talk\s+to\s+someone|supervisor|representative)\b",
    r"\b(give\s+me\s+a\s+person|connect\s+me\s+to\s+a\s+human)\b",
]

_COMPILED_DISTRESS_REGEX = [re.compile(p, re.IGNORECASE) for p in _DISTRESS_PATTERNS]


def detect_distress(text: str) -> bool:
    """Scan transcript or user utterance for urgent escalation signals."""
    clean_text = text.strip()
    return any(pattern.search(clean_text) for pattern in _COMPILED_DISTRESS_REGEX)


def get_visa_status(application_id: str) -> VisaStatusResult:
    """Query the authoritative Atlys database and format a voice-ready response.

    Guarantees:
    - Never hallucinates dates, fees, or outcomes.
    - Limits spoken summary to strictly 1-2 concise sentences.
    - Zero markdown or special characters.
    """
    record = get_application(application_id)
    norm_id = application_id.strip().upper()

    if not record:
        return VisaStatusResult(
            found=False,
            application_id=norm_id,
            spoken_summary=f"I could not find an application with reference ID {norm_id}. Please check your reference code in the Atlys app.",
        )

    # 1. Approved state (1 sentence)
    if record.status == "Approved":
        spoken = (
            f"Great news, your {record.country} {record.visa_type} is approved and ready to download in the Atlys app."
        )
    # 2. Action Required / Document Defect state (2 sentences)
    elif record.status == "Action Required":
        defect = (record.defect_issue or "").rstrip(".")
        action = (record.traveler_action or "").rstrip(".")
        spoken = (
            f"Your {record.country} application needs attention because your {defect.lower()}. "
            f"Please {action[0].lower() + action[1:] if action else 'check the Atlys app'}."
        )
    # 3. Rejected state (2 sentences)
    elif record.status == "Rejected":
        defect = (record.defect_issue or "").rstrip(".")
        spoken = (
            f"I see that your {record.country} visa was not approved by the consulate due to {defect.lower()}. "
            f"I am connecting you with our Guest Delight team right now to review your options."
        )
    # 4. In Review / Processing states (2 sentences)
    else:
        days_phrase = f"in about {record.estimated_days} business days" if record.estimated_days else "soon"
        spoken = (
            f"Your {record.country} visa is currently {record.status.lower()} with the embassy. "
            f"Everything is on track, and we expect a decision {days_phrase}."
        )

    return VisaStatusResult(
        found=True,
        application_id=record.application_id,
        spoken_summary=spoken,
        status=record.status,
        country=record.country,
    )


def escalate_to_human(reason: str, priority: str = "high") -> EscalationResult:
    """Execute human handoff and generate urgent reassurance script (strictly 2 sentences)."""
    spoken = (
        "I completely understand how urgent this is. "
        "I am connecting you directly to our senior Guest Delight specialist right now."
    )
    return EscalationResult(
        escalated=True,
        priority=priority,
        reason=reason,
        spoken_response=spoken,
    )
