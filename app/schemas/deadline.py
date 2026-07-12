"""
Pydantic schemas for DeadlineEntry — validates data at two boundaries:
1. Gemini's raw extraction output (messy, needs cleaning/validation)
2. API responses sent to the frontend (clean, DB-shaped)
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.deadline import DeadlineStatus, OpportunityCategory, SourceType

# Common date formats Gemini tends to return — checked in order.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%B %d, %Y",
    "%d %B %Y",
)


def _parse_flexible_date(value: str) -> datetime:
    """Try multiple known formats before giving up on a date string."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Could not parse deadline date: {value!r}. "
        f"Expected a format like 'YYYY-MM-DD' or 'Month DD, YYYY'."
    )


class GeminiExtractedFields(BaseModel):
    """
    Fields that Gemini itself is responsible for extracting from the
    uploaded PDF/image/text. This schema exists to validate the AI's
    output *before* it's trusted enough to reach the database — it's
    the contract between the AI service and the rest of the app.
    """

    company_name: str = Field(..., min_length=2, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    eligible_branches: str | None = Field(default=None, max_length=500)
    cgpa_criteria: str | None = Field(default=None, max_length=100)
    deadline: datetime
    registration_link: str | None = Field(default=None, max_length=1000)
    important_instructions: str | None = Field(default=None, max_length=5000)
    category: OpportunityCategory

    # Gemini can optionally self-report confidence; not guaranteed, so optional.
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, v: str) -> str:
        """Catches whitespace-only strings that pass min_length after strip."""
        if not v.strip():
            raise ValueError("company_name cannot be blank")
        return v

    @field_validator("deadline", mode="before")
    @classmethod
    def parse_deadline(cls, v: object) -> object:
        """Gemini may return dates as strings in varied formats — normalize here."""
        if isinstance(v, str):
            return _parse_flexible_date(v)
        return v

    @field_validator("registration_link")
    @classmethod
    def validate_registration_link(cls, v: str | None) -> str | None:
        """
        Ensures the link is at least a plausible URL. Screenshots often
        yield links missing a scheme (e.g. 'forms.google.com/xyz') —
        we normalize rather than reject, since rejecting would drop
        otherwise-usable data.
        """
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"
        # Basic sanity check: must look like domain.tld/something
        if not re.match(r"^https?://[\w.-]+\.\w{2,}(/.*)?$", v):
            raise ValueError(f"registration_link does not look like a valid URL: {v!r}")
        return v


class DeadlineEntryCreate(GeminiExtractedFields):
    """
    Full payload needed to persist a DeadlineEntry. Extends the AI's
    output with fields supplied by the *pipeline*, not Gemini itself —
    keeping this separate from GeminiExtractedFields makes it clear
    which fields are AI-derived vs. application-derived.
    """

    source_type: SourceType
    raw_text: str | None = Field(default=None, max_length=20_000)


class DeadlineEntryResponse(BaseModel):
    """
    Shape of data returned to the frontend/dashboard. Deliberately
    excludes `raw_text` (internal debugging data, not user-facing) and
    includes DB-generated fields (id, timestamps, status) that only
    exist after persistence.
    """

    id: int
    user_id: int
    company_name: str
    role: str | None
    eligible_branches: str | None
    cgpa_criteria: str | None
    deadline: datetime
    registration_link: str | None
    important_instructions: str | None
    category: OpportunityCategory
    source_type: SourceType
    extraction_confidence: float | None
    status: DeadlineStatus
    reminder_sent_at: datetime | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    is_updated: bool = False

    # Lets this schema be built directly from a SQLAlchemy ORM object
    # (e.g. DeadlineEntryResponse.model_validate(db_entry)) instead of
    # manually mapping every field.
    model_config = ConfigDict(from_attributes=True)


class DeadlineEntryUpdate(BaseModel):
    company_name: str | None = None
    role: str | None = None
    eligible_branches: str | None = None
    cgpa_criteria: str | None = None
    deadline: datetime | None = None
    registration_link: str | None = None
    important_instructions: str | None = None
    category: OpportunityCategory | None = None
    status: DeadlineStatus | None = None

    model_config = ConfigDict(extra="forbid")

class ExtractionRequest(BaseModel):
    """Request body for POST /extract — raw unstructured text input."""

    text: str = Field(..., min_length=10, max_length=20_000)

    model_config = ConfigDict(str_strip_whitespace=True)