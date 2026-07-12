"""
ORM model for a single extracted deadline entry (placement, internship,
scholarship, hackathon, or event).
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SourceType(str, enum.Enum):
    """Where the raw data came from — useful for debugging extraction quality."""

    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"


class DeadlineStatus(str, enum.Enum):
    """Lifecycle state of a deadline, used to filter dashboard views."""

    UPCOMING = "upcoming"
    EXPIRED = "expired"
    APPLIED = "applied"


class OpportunityCategory(str, enum.Enum):
    """Type of opportunity — drives dashboard filtering/grouping."""

    PLACEMENT = "placement"
    INTERNSHIP = "internship"
    SCHOLARSHIP = "scholarship"
    HACKATHON = "hackathon"
    EVENT = "event"


class DeadlineEntry(Base):
    """
    A structured record of one opportunity (placement/internship/
    scholarship/hackathon/event) extracted from an unstructured source.
    """

    __tablename__ = "deadline_entries"

    # --- Identity -----------------------------------------------------
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Core extracted fields ----------------------------------------
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eligible_branches: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cgpa_criteria: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Deadline is the single most important field — it drives the whole
    # reminder system, so it's indexed and NOT nullable.
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    registration_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    important_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classifies which of the 5 opportunity types this entry is —
    # needed for dashboard filtering (e.g. "show only hackathons").
    # Non-nullable with no default: forces the extraction/validation
    # layer to always classify an entry rather than letting it fall
    # through unclassified.
    category: Mapped[OpportunityCategory] = mapped_column(
        Enum(OpportunityCategory), nullable=False
    )

    # --- Provenance & AI metadata --------------------------------------
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType), nullable=False
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Status tracking -------------------------------------------------
    status: Mapped[DeadlineStatus] = mapped_column(
        Enum(DeadlineStatus), nullable=False, default=DeadlineStatus.UPCOMING
    )

    # Tracks whether the reminder service has already notified the user
    # for this entry, so APScheduler jobs don't send duplicate alerts.
    # NULL = never sent; timestamp = when it was sent.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Ownership link (Multi-tenancy)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner: Mapped["User"] = relationship("User", back_populates="deadlines")

    # Soft delete flag. User-facing deletions should never hard-delete
    # rows — this lets us hide an entry from the dashboard while
    # preserving it for recovery/audit. Every read query going forward
    # must filter on is_deleted = False.
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # --- Timestamps -----------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Dashboard's #1 query: "upcoming, non-deleted deadlines sorted
        # by date." Composite index matches filter + sort columns
        # together so the DB can satisfy it without a separate sort pass.
        Index("ix_deadline_status_deadline", "status", "deadline"),
        Index("ix_deadline_company_name", "company_name"),
        # Supports "filter by category" dashboard views (e.g. hackathons only).
        Index("ix_deadline_category", "category"),
        # Supports the reminder scheduler's query: "find UPCOMING entries
        # where reminder_sent_at IS NULL and deadline is within N days."
        Index("ix_deadline_reminder_pending", "status", "reminder_sent_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeadlineEntry id={self.id} company={self.company_name!r} "
            f"category={self.category.value} deadline={self.deadline.isoformat()} "
            f"status={self.status.value}>"
        )