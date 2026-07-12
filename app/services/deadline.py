import logging
from datetime import datetime, timezone
from typing import List, Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.deadline import (
    DeadlineEntry,
    DeadlineStatus,
    OpportunityCategory,
    SourceType,
)
from app.schemas.deadline import (
    DeadlineEntryCreate,
    DeadlineEntryUpdate,
    ExtractionRequest,
)
from app.services.file_extraction import FileExtractionService, FileExtractionError
from app.services.gemini_extraction import GeminiExtractionService

logger = logging.getLogger(__name__)


class DeadlineService:
    """Service layer managing user-scoped deadline operations."""

    def __init__(self) -> None:
        self.file_service = FileExtractionService()
        self.gemini_service = GeminiExtractionService()

    def list_deadlines(
        self,
        db: Session,
        user_id: int,
        category: OpportunityCategory | None = None,
        status_val: DeadlineStatus | None = None,
        company_name: str | None = None,
        deadline_from: datetime | None = None,
        deadline_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "deadline",
        order: str = "asc",
    ) -> List[DeadlineEntry]:
        """List deadlines belonging to a user with filtering, sorting, and pagination."""
        query = db.query(DeadlineEntry).filter(
            DeadlineEntry.user_id == user_id,
            DeadlineEntry.is_deleted.is_(False),
        )

        if category:
            query = query.filter(DeadlineEntry.category == category)

        if status_val:
            query = query.filter(DeadlineEntry.status == status_val)

        if company_name:
            query = query.filter(DeadlineEntry.company_name.ilike(f"%{company_name}%"))

        if deadline_from:
            query = query.filter(DeadlineEntry.deadline >= deadline_from)

        if deadline_to:
            query = query.filter(DeadlineEntry.deadline <= deadline_to)

        sort_column = getattr(DeadlineEntry, sort_by, DeadlineEntry.deadline)
        if order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        return query.offset(skip).limit(limit).all()

    def get_deadline(self, db: Session, deadline_id: int, user_id: int) -> DeadlineEntry:
        """Get a single deadline by ID. Raises 404 if not found or belongs to another user."""
        entry = (
            db.query(DeadlineEntry)
            .filter(
                DeadlineEntry.id == deadline_id,
                DeadlineEntry.user_id == user_id,
                DeadlineEntry.is_deleted.is_(False),
            )
            .first()
        )
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Deadline {deadline_id} not found.",
            )
        return entry

    def create_deadline_from_text(
        self, db: Session, payload: ExtractionRequest, user_id: int
    ) -> DeadlineEntry:
        """Extract information from text and create or update a deadline entry for a user."""
        logger.info("Extraction request received from user %d (%d chars).", user_id, len(payload.text))
        extracted = self.gemini_service.extract_from_text(payload.text)

        # Check for duplicates scoped to this user
        query = db.query(DeadlineEntry).filter(
            DeadlineEntry.user_id == user_id,
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
            logger.info("Duplicate found (id=%d). Updating existing entry for user %d.", existing.id, user_id)
            for field, val in extracted.model_dump(exclude_unset=True).items():
                setattr(existing, field, val)
            existing.source_type = SourceType.TEXT
            existing.raw_text = payload.text
            existing.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing)
            existing.is_updated = True
            return existing

        entry_data = DeadlineEntryCreate(
            **extracted.model_dump(),
            source_type=SourceType.TEXT,
            raw_text=payload.text,
        )

        entry = DeadlineEntry(**entry_data.model_dump(), user_id=user_id)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        entry.is_updated = False
        return entry

    def process_file_upload(
        self, db: Session, filename: str, file_bytes: bytes, user_id: int
    ) -> DeadlineEntry:
        """Extract text from file, run Gemini extraction, and save/update the deadline for the user."""
        ext = filename.lower().split(".")[-1]
        
        # Parse text based on file type
        try:
            if ext == "pdf":
                raw_text = self.file_service.extract_pdf(file_bytes)
                source_type = SourceType.PDF
            elif ext == "docx":
                raw_text = self.file_service.extract_docx(file_bytes)
                source_type = SourceType.TEXT
            elif ext == "txt":
                raw_text = self.file_service.extract_txt(file_bytes)
                source_type = SourceType.TEXT
            else: # png, jpg, jpeg
                raw_text = self.file_service.extract_image(file_bytes)
                source_type = SourceType.IMAGE
        except FileExtractionError as exc:
            logger.error("File text extraction failed for user %d: %s", user_id, exc)
            raise HTTPException(status_code=400, detail=str(exc))

        # Call Gemini
        extracted = self.gemini_service.extract_from_text(raw_text)

        # Duplicate check scoped to this user
        query = db.query(DeadlineEntry).filter(
            DeadlineEntry.user_id == user_id,
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
            logger.info("Duplicate found from upload (id=%d). Updating entry for user %d.", existing.id, user_id)
            for field, val in extracted.model_dump(exclude_unset=True).items():
                setattr(existing, field, val)
            existing.source_type = source_type
            existing.raw_text = raw_text
            existing.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing)
            existing.is_updated = True
            return existing

        entry_data = DeadlineEntryCreate(
            **extracted.model_dump(),
            source_type=source_type,
            raw_text=raw_text,
        )

        entry = DeadlineEntry(**entry_data.model_dump(), user_id=user_id)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        entry.is_updated = False
        return entry

    def update_deadline(
        self, db: Session, deadline_id: int, payload: DeadlineEntryUpdate, user_id: int
    ) -> DeadlineEntry:
        """Update a deadline. Raises 404 if not found or belongs to another user."""
        entry = self.get_deadline(db, deadline_id, user_id)
        
        updates = payload.model_dump(exclude_unset=True)
        protected_fields = {"id", "user_id", "created_at", "updated_at"}
        for field in protected_fields:
            updates.pop(field, None)

        for field, value in updates.items():
            setattr(entry, field, value)

        db.commit()
        db.refresh(entry)
        return entry

    def delete_deadline(self, db: Session, deadline_id: int, user_id: int) -> None:
        """Soft-delete a deadline. Raises 404 if not found or belongs to another user."""
        entry = self.get_deadline(db, deadline_id, user_id)
        entry.is_deleted = True
        db.commit()
