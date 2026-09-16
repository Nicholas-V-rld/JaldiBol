"""In-memory Atlys Visa Application Database.

Acts as the sole authoritative source of truth for Project Aero.
All lookups are deterministic, zero-latency, and anti-hallucination grounded.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class ApplicationRecord(BaseModel):
    """Authoritative representation of a traveler's visa application in Atlys."""

    application_id: str = Field(..., description="Unique Atlys application reference code (e.g. ATL123)")
    country: str = Field(..., description="Destination country")
    visa_type: str = Field(..., description="Category of visa (e.g. Schengen Tourist, eVisa)")
    status: str = Field(
        ...,
        description="Current state: Approved, In Review, Processing, Action Required, Rejected",
    )
    estimated_days: Optional[int] = Field(
        default=None,
        description="Estimated business days until embassy decision",
    )
    defect_issue: Optional[str] = Field(
        default=None,
        description="Specific document defect if status is Action Required",
    )
    traveler_action: Optional[str] = Field(
        default=None,
        description="Exact guidance for traveler to remediate issue",
    )
    notes: str = Field(..., description="Internal consular / Atlys status note")


# Authoritative mock database seeded with 10 representative applications
_APPLICATIONS_DB: Dict[str, ApplicationRecord] = {
    "ATL123": ApplicationRecord(
        application_id="ATL123",
        country="France",
        visa_type="Schengen Tourist",
        status="In Review",
        estimated_days=2,
        notes="Under active review at the French Consulate in Mumbai. All documents verified.",
    ),
    "ATL999": ApplicationRecord(
        application_id="ATL999",
        country="UAE",
        visa_type="Tourist Visa (30 Days)",
        status="Action Required",
        defect_issue="Passport bio-page scan is blurry and unreadable by OCR",
        traveler_action="Open the Atlys app and take a fresh photo of your passport under bright natural lighting.",
        notes="Embassy flagged document defect on passport scan.",
    ),
    "ATL456": ApplicationRecord(
        application_id="ATL456",
        country="United States",
        visa_type="B1/B2 Visitor",
        status="Processing",
        estimated_days=7,
        notes="Biometrics completed. Consular interview confirmation pending appointment date.",
    ),
    "ATL789": ApplicationRecord(
        application_id="ATL789",
        country="United Kingdom",
        visa_type="Standard Visitor",
        status="Approved",
        notes="Visa sticker stamped. Passport has been handed over to BlueDart courier for delivery.",
    ),
    "ATL000": ApplicationRecord(
        application_id="ATL000",
        country="Singapore",
        visa_type="Tourist eVisa",
        status="Rejected",
        defect_issue="Insufficient proof of financial sustenance for stay",
        notes="Embassy issued rejection notice due to inadequate bank statement balance.",
    ),
    "ATL321": ApplicationRecord(
        application_id="ATL321",
        country="Canada",
        visa_type="Electronic Travel Authorization (eTA)",
        status="Processing",
        estimated_days=5,
        notes="Automated risk and security assessment underway with IRCC.",
    ),
    "ATL654": ApplicationRecord(
        application_id="ATL654",
        country="Australia",
        visa_type="Subclass 600 Tourist",
        status="In Review",
        estimated_days=10,
        notes="Case officer assigned. Health declaration in verification.",
    ),
    "ATL111": ApplicationRecord(
        application_id="ATL111",
        country="Thailand",
        visa_type="Tourist eVisa on Arrival",
        status="Approved",
        notes="Approved by Thai Immigration Bureau. E-visa PDF available for immediate download in Atlys.",
    ),
    "ATL222": ApplicationRecord(
        application_id="ATL222",
        country="Japan",
        visa_type="Short-Term Tourism",
        status="Action Required",
        defect_issue="Missing confirmed accommodation voucher",
        traveler_action="Upload your confirmed hotel booking reservation PDF in the Atlys app.",
        notes="Consulate requested proof of stay before processing.",
    ),
    "ATL333": ApplicationRecord(
        application_id="ATL333",
        country="New Zealand",
        visa_type="NZeTA",
        status="Processing",
        estimated_days=3,
        notes="Standard security clearance in progress.",
    ),
}


def normalize_application_id(raw_id: str) -> str:
    """Normalize user or speech-recognized application IDs (e.g. 'atl 123' -> 'ATL123')."""
    return "".join(raw_id.strip().upper().split())


def get_application(application_id: str) -> Optional[ApplicationRecord]:
    """Retrieve an application by ID with strict grounding.

    Returns:
        ApplicationRecord if present, or None if not registered.
    """
    normalized_id = normalize_application_id(application_id)
    return _APPLICATIONS_DB.get(normalized_id)


def list_all_application_ids() -> list[str]:
    """List all registered application IDs for testing and validation."""
    return list(_APPLICATIONS_DB.keys())
