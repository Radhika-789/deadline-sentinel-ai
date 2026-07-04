"""
API routes for deadline extraction and retrieval.

Routes stay thin by design: parse the request, delegate to
GeminiExtractionService for AI work, and use the injected SQLAlchemy
Session directly for persistence.
"""

import logging
import re
from datetime import datetime , timedelta, timezone
from io import BytesIO
from typing import List, Literal
from icalendar import Calendar, Event

from fastapi import APIRouter, Depends, HTTPException , Response ,Query, UploadFile, File
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
from app.services.file_extraction import FileExtractionService, FileExtractionError
from app.services.gemini_extraction import GeminiExtractionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deadlines"])


def get_extraction_service() -> GeminiExtractionService:
    """Dependency provider for GeminiExtractionService."""
    return GeminiExtractionService()


def get_file_extraction_service() -> FileExtractionService:
    """Dependency provider for FileExtractionService."""
    return FileExtractionService()


# Extract + Save


@router.post("/extract", response_model=DeadlineEntryResponse)
async def extract_deadline(
    payload: ExtractionRequest,
    service: GeminiExtractionService = Depends(get_extraction_service),
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Extract structured deadline information from raw text using Gemini
    and persist it to the database. If a duplicate exists, update it.
    """

    logger.info("Extraction request received (%d chars).", len(payload.text))

    extracted = service.extract_from_text(payload.text)

    logger.info(
        "Extraction succeeded: company=%s category=%s",
        extracted.company_name,
        extracted.category,
    )

    # Search for an existing non-deleted entry with same company_name, role, and deadline
    query = db.query(DeadlineEntry).filter(
        DeadlineEntry.company_name == extracted.company_name,
        DeadlineEntry.deadline == extracted.deadline,
        DeadlineEntry.is_deleted.is_(False)
    )
    if extracted.role is None:
        query = query.filter(DeadlineEntry.role.is_(None))
    else:
        query = query.filter(DeadlineEntry.role == extracted.role)
    existing = query.first()

    if existing:
        logger.info("Duplicate found (id=%d). Updating existing entry.", existing.id)
        # Update editable fields
        for field, val in extracted.model_dump(exclude_unset=True).items():
            setattr(existing, field, val)
        existing.source_type = SourceType.TEXT
        existing.raw_text = payload.text
        existing.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing)
        
        resp = DeadlineEntryResponse.model_validate(existing)
        resp.is_updated = True
        return resp

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
        "Persisted new deadline entry id=%d company=%s",
        entry.id,
        entry.company_name,
    )

    resp = DeadlineEntryResponse.model_validate(entry)
    resp.is_updated = False
    return resp


@router.post("/upload", response_model=DeadlineEntryResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileExtractionService = Depends(get_file_extraction_service),
    gemini_service: GeminiExtractionService = Depends(get_extraction_service),
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Upload a file (PDF, DOCX, TXT, PNG, JPG, JPEG), extract text,
    run Gemini extraction, and save the deadline entry. If a duplicate exists, update it.
    """
    logger.info("Upload request received: filename=%s, content_type=%s", file.filename, file.content_type)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename.")

    filename = file.filename
    ext = filename.lower().split(".")[-1]

    # Validate file type
    supported_extensions = {"pdf", "docx", "txt", "png", "jpg", "jpeg"}
    if ext not in supported_extensions:
        logger.warning("Rejected unsupported file type: %s", filename)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: .{ext}. Supported types: {', '.join(supported_extensions)}"
        )

    # Read bytes and check for empty files
    file_bytes = await file.read()
    if not file_bytes:
        logger.warning("Rejected empty file: %s", filename)
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    # Log file upload event
    logger.info("Processing file upload: %s (%d bytes)", filename, len(file_bytes))

    # Extract text based on file type
    try:
        if ext == "pdf":
            raw_text = file_service.extract_pdf(file_bytes)
            source_type = SourceType.PDF
        elif ext == "docx":
            raw_text = file_service.extract_docx(file_bytes)
            source_type = SourceType.TEXT
        elif ext == "txt":
            raw_text = file_service.extract_txt(file_bytes)
            source_type = SourceType.TEXT
        else: # png, jpg, jpeg
            raw_text = file_service.extract_image(file_bytes)
            source_type = SourceType.IMAGE
    except FileExtractionError as exc:
        logger.error("File text extraction failed for %s: %s", filename, exc)
        raise HTTPException(status_code=400, detail=str(exc))

    # Process with Gemini
    logger.info("Passing extracted text from %s to GeminiExtractionService", filename)
    extracted = gemini_service.extract_from_text(raw_text)

    logger.info(
        "Gemini extraction succeeded for %s: company=%s category=%s",
        filename,
        extracted.company_name,
        extracted.category,
    )

    # Search for an existing non-deleted entry with same company_name, role, and deadline
    query = db.query(DeadlineEntry).filter(
        DeadlineEntry.company_name == extracted.company_name,
        DeadlineEntry.deadline == extracted.deadline,
        DeadlineEntry.is_deleted.is_(False)
    )
    if extracted.role is None:
        query = query.filter(DeadlineEntry.role.is_(None))
    else:
        query = query.filter(DeadlineEntry.role == extracted.role)
    existing = query.first()

    if existing:
        logger.info("Duplicate found (id=%d). Updating existing entry from upload.", existing.id)
        # Update editable fields
        for field, val in extracted.model_dump(exclude_unset=True).items():
            setattr(existing, field, val)
        existing.source_type = source_type
        existing.raw_text = raw_text
        existing.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing)
        
        resp = DeadlineEntryResponse.model_validate(existing)
        resp.is_updated = True
        return resp

    # Create and persist DeadlineEntry
    entry_data = DeadlineEntryCreate(
        **extracted.model_dump(),
        source_type=source_type,
        raw_text=raw_text,
    )

    entry = DeadlineEntry(**entry_data.model_dump())

    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info(
        "Persisted new deadline entry from upload: id=%d company=%s filename=%s",
        entry.id,
        entry.company_name,
        filename,
    )

    resp = DeadlineEntryResponse.model_validate(entry)
    resp.is_updated = False
    return resp


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

# Export as .ics


def _ics_slug(value: str) -> str:
    """Turn a company/role name into a safe filename fragment."""
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"\s+", "-", value) or "unknown"


@router.get("/deadlines/{deadline_id}/calendar")
async def get_deadline_calendar(
    deadline_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """
    Generate a standards-compliant .ics file for a single deadline,
    entirely in memory, and return it as a downloadable attachment.
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

    role_part = entry.role or "Opportunity"
    summary = f"{entry.company_name} - {role_part}"

    description = "\n".join(
        [
            f"Category: {entry.category.value}",
            f"Eligibility: {entry.eligible_branches or 'N/A'}"
            + (f" (CGPA: {entry.cgpa_criteria})" if entry.cgpa_criteria else ""),
            f"Application Link: {entry.registration_link or 'N/A'}",
            f"Notes: {entry.important_instructions or 'N/A'}",
        ]
    )

    # Normalize to UTC regardless of whether the stored value is naive or aware.
    start = entry.deadline
    start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start.astimezone(timezone.utc)
    end = start + timedelta(hours=1)

    cal = Calendar()
    cal.add("prodid", "-//Deadline Sentinel AI//calendar-export//EN")
    cal.add("version", "2.0")

    event = Event()
    event.add("uid", f"deadline-{entry.id}@deadline-sentinel-ai")
    event.add("summary", summary)
    event.add("description", description)
    event.add("dtstart", start)
    event.add("dtend", end)
    event.add("dtstamp", datetime.now(timezone.utc))
    event.add("location", "")

    cal.add_component(event)

    ics_bytes = cal.to_ical()
    filename = f"{_ics_slug(entry.company_name)}-{_ics_slug(role_part)}.ics"

    return Response(
        content=BytesIO(ics_bytes).getvalue(),
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

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