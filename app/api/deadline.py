"""
API routes for deadline extraction and retrieval.

Routes stay thin by design: parse the request, delegate to
GeminiExtractionService for AI work, and use the injected SQLAlchemy
Session directly for persistence.
"""

import logging
from datetime import datetime
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.deadline import (
    DeadlineEntry,
    DeadlineStatus,
    OpportunityCategory,
    SourceType,
)
from app.schemas.deadline import (
    DeadlineEntryCreate,
    DeadlineEntryResponse,
    DeadlineEntryUpdate,
    ExtractionRequest,
)
from app.services.gemini_extraction import GeminiExtractionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deadlines"])


def get_extraction_service() -> GeminiExtractionService:
    """Dependency provider for GeminiExtractionService."""
    return GeminiExtractionService()



# Extract + Save


@router.post("/extract", response_model=DeadlineEntryResponse)
async def extract_deadline(
    payload: ExtractionRequest,
    service: GeminiExtractionService = Depends(get_extraction_service),
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Extract structured deadline information from raw text using Gemini
    and persist it to the database.
    """

    logger.info("Extraction request received (%d chars).", len(payload.text))

    extracted = service.extract_from_text(payload.text)

    logger.info(
        "Extraction succeeded: company=%s category=%s",
        extracted.company_name,
        extracted.category,
    )

    entry_data = DeadlineEntryCreate(
        **extracted.model_dump(),
        source_type=SourceType.TEXT,
        raw_text=payload.text,
    )

    entry = DeadlineEntry(**entry_data.model_dump())

    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info(
        "Persisted deadline entry id=%d company=%s",
        entry.id,
        entry.company_name,
    )

    return DeadlineEntryResponse.model_validate(entry)


# List Deadlines


@router.get("/deadlines", response_model=List[DeadlineEntryResponse])
async def list_deadlines(
    category: OpportunityCategory | None = None,
    status: DeadlineStatus | None = None,
    company_name: str | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    sort_by: Literal["deadline", "created_at", "company_name"] = "deadline",
    order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),
) -> List[DeadlineEntryResponse]:
    """
    Return deadlines with optional filtering, sorting and pagination.
    """

    query = db.query(DeadlineEntry).filter(
        DeadlineEntry.is_deleted.is_(False)
    )

    if category:
        query = query.filter(DeadlineEntry.category == category)

    if status:
        query = query.filter(DeadlineEntry.status == status)

    if company_name:
        query = query.filter(
            DeadlineEntry.company_name.ilike(f"%{company_name}%")
        )

    if deadline_from:
        query = query.filter(
            DeadlineEntry.deadline >= deadline_from
        )

    if deadline_to:
        query = query.filter(
            DeadlineEntry.deadline <= deadline_to
        )

    sort_column = getattr(DeadlineEntry, sort_by)

    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    entries = (
        query.offset(skip)
        .limit(limit)
        .all()
    )

    return entries



# Get Single Deadline


@router.get("/deadlines/{deadline_id}", response_model=DeadlineEntryResponse)
async def get_deadline(
    deadline_id: int,
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Return a single deadline by id.
    """

    entry = (
        db.query(DeadlineEntry)
        .filter(
            DeadlineEntry.id == deadline_id,
            DeadlineEntry.is_deleted.is_(False),
        )
        .first()
    )

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deadline {deadline_id} not found.",
        )

    return entry



# Update Deadline


@router.patch("/deadlines/{deadline_id}", response_model=DeadlineEntryResponse)
async def update_deadline(
    deadline_id: int,
    payload: DeadlineEntryUpdate,
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Update editable fields of a deadline.
    """

    entry = (
        db.query(DeadlineEntry)
        .filter(
            DeadlineEntry.id == deadline_id,
            DeadlineEntry.is_deleted.is_(False),
        )
        .first()
    )

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deadline {deadline_id} not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    # Prevent updates to system-managed fields
    protected_fields = {
        "id",
        "created_at",
        "updated_at",
    }

    for field in protected_fields:
        updates.pop(field, None)

    for field, value in updates.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)

    return entry


# SOFT DELETE

@router.delete("/deadlines/{deadline_id}", status_code=204)
async def delete_deadline(
    deadline_id: int,
    db: Session = Depends(get_db),
):
    """
    Soft delete a deadline.
    """

    entry = (
        db.query(DeadlineEntry)
        .filter(
            DeadlineEntry.id == deadline_id,
            DeadlineEntry.is_deleted.is_(False),
        )
        .first()
    )

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deadline {deadline_id} not found.",
        )

    entry.is_deleted = True

    db.commit()

    return