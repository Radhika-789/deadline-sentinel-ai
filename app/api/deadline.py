import logging
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import List, Literal
from icalendar import Calendar, Event

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.deadline import (
    DeadlineStatus,
    OpportunityCategory,
)
from app.schemas.deadline import (
    DeadlineEntryResponse,
    DeadlineEntryUpdate,
    ExtractionRequest,
)
from app.services.deadline import DeadlineService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deadlines"])


def get_deadline_service() -> DeadlineService:
    """Dependency provider for DeadlineService."""
    return DeadlineService()


@router.post("/extract", response_model=DeadlineEntryResponse)
def extract_deadline(
    payload: ExtractionRequest,
    service: DeadlineService = Depends(get_deadline_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Extract structured deadline information from raw text using Gemini
    and persist it to the database for the authenticated user.
    """
    entry = service.create_deadline_from_text(db, payload, current_user.id)
    resp = DeadlineEntryResponse.model_validate(entry)
    resp.is_updated = getattr(entry, "is_updated", False)
    return resp


@router.post("/upload", response_model=DeadlineEntryResponse)
async def upload_file(
    file: UploadFile = File(...),
    service: DeadlineService = Depends(get_deadline_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Upload a file (PDF, DOCX, TXT, PNG, JPG, JPEG), extract text,
    run Gemini extraction, and save/update the deadline entry for the authenticated user.
    """
    logger.info(
        "Upload request from user %d: filename=%s, content_type=%s",
        current_user.id,
        file.filename,
        file.content_type,
    )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename.")

    filename = file.filename
    ext = filename.lower().split(".")[-1]

    # Validate file type
    supported_extensions = {"pdf", "docx", "txt", "png", "jpg", "jpeg"}
    if ext not in supported_extensions:
        logger.warning("Rejected unsupported file type from user %d: %s", current_user.id, filename)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: .{ext}. Supported types: {', '.join(supported_extensions)}"
        )

    # Read bytes and check for empty files
    file_bytes = await file.read()
    if not file_bytes:
        logger.warning("Rejected empty file from user %d: %s", current_user.id, filename)
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    # Process with Service
    entry = service.process_file_upload(db, filename, file_bytes, current_user.id)
    
    resp = DeadlineEntryResponse.model_validate(entry)
    resp.is_updated = getattr(entry, "is_updated", False)
    return resp


@router.get("/deadlines", response_model=List[DeadlineEntryResponse])
def list_deadlines(
    category: OpportunityCategory | None = None,
    status: DeadlineStatus | None = None,
    company_name: str | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    sort_by: Literal["deadline", "created_at", "company_name"] = "deadline",
    order: Literal["asc", "desc"] = "asc",
    service: DeadlineService = Depends(get_deadline_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[DeadlineEntryResponse]:
    """
    Return deadlines for the authenticated user with optional filtering, sorting and pagination.
    """
    return service.list_deadlines(
        db=db,
        user_id=current_user.id,
        category=category,
        status_val=status,
        company_name=company_name,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        order=order,
    )


@router.get("/deadlines/{deadline_id}", response_model=DeadlineEntryResponse)
def get_deadline(
    deadline_id: int,
    service: DeadlineService = Depends(get_deadline_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Return a single deadline by id for the authenticated user.
    """
    return service.get_deadline(db, deadline_id, current_user.id)


def _ics_slug(value: str) -> str:
    """Turn a company/role name into a safe filename fragment."""
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"\s+", "-", value) or "unknown"


@router.get("/deadlines/{deadline_id}/calendar")
def get_deadline_calendar(
    deadline_id: int,
    service: DeadlineService = Depends(get_deadline_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    Generate a standards-compliant .ics file for a single user-owned deadline,
    entirely in memory, and return it as a downloadable attachment.
    """
    entry = service.get_deadline(db, deadline_id, current_user.id)

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


@router.patch("/deadlines/{deadline_id}", response_model=DeadlineEntryResponse)
def update_deadline(
    deadline_id: int,
    payload: DeadlineEntryUpdate,
    service: DeadlineService = Depends(get_deadline_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeadlineEntryResponse:
    """
    Update editable fields of a user-owned deadline.
    """
    return service.update_deadline(db, deadline_id, payload, current_user.id)


@router.delete("/deadlines/{deadline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deadline(
    deadline_id: int,
    service: DeadlineService = Depends(get_deadline_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Soft delete a user-owned deadline.
    """
    service.delete_deadline(db, deadline_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)