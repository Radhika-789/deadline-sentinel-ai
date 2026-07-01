"""
API routes for deadline extraction.

Routes stay thin by design: parse the request, delegate to
GeminiExtractionService, return the result. No business logic here —
that all lives in the service layer, which keeps routes trivially
readable and the service independently unit-testable.
"""

import logging

from fastapi import APIRouter, Depends

from app.schemas.deadline import ExtractionRequest, GeminiExtractedFields
from app.services.gemini_extraction import GeminiExtractionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deadlines"])


def get_extraction_service() -> GeminiExtractionService:
    """
    Dependency provider for GeminiExtractionService.

    FastAPI calls this per-request rather than us using a global
    singleton. The real payoff: in tests, you can override this with
    `app.dependency_overrides[get_extraction_service] = lambda: FakeService()`
    to fully mock Gemini without touching route code.
    """
    return GeminiExtractionService()


@router.post("/extract", response_model=GeminiExtractedFields)
async def extract_deadline(
    payload: ExtractionRequest,
    service: GeminiExtractionService = Depends(get_extraction_service),
) -> GeminiExtractedFields:
    """
    Extract structured deadline information from raw text using Gemini.

    This is a preview/extraction-only endpoint — nothing is persisted
    to the database yet. Any failure inside the service (empty input,
    Gemini API error, bad JSON, schema mismatch) propagates as a typed
    exception and is converted to the right HTTP status by the
    exception handlers registered in main.py.
    """
    logger.info("Extraction request received (%d chars).", len(payload.text))
    result = service.extract_from_text(payload.text)
    logger.info(
        "Extraction succeeded: company=%s category=%s",
        result.company_name,
        result.category,
    )
    return result