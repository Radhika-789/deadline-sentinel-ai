"""
Gemini-powered extraction service.

Responsibility: take raw unstructured text and return a validated
GeminiExtractedFields object. This service knows nothing about the
database, HTTP, or file handling — it's a pure text-in, schema-out
component, which is what makes it easy to test and easy to swap out
(e.g. for a different LLM provider) later.
"""

import json
import logging
import re

import google.generativeai as genai
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.deadline import GeminiExtractedFields
from app.services.exceptions import (
    EmptyResponseError,
    GeminiAPIError,
    InvalidJSONError,
    SchemaValidationError,
)

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-flash-latest"

# System-style instruction, kept as a module constant so it's easy to
# version/tune without hunting through method bodies.
_EXTRACTION_PROMPT_TEMPLATE = """\
You are a data extraction engine for a college placement/deadline tracker.

Extract structured information from the text below, which may describe a \
placement drive, internship, scholarship, hackathon, or campus event.

Return ONLY a single valid JSON object — no markdown code fences, no \
explanations, no leading or trailing text. If a field is not present in \
the source text, use JSON null for that field.

JSON schema to follow exactly:
{{
  "company_name": string (required, the hiring company or organizing body),
  "role": string or null (job title / internship role, if applicable),
  "eligible_branches": string or null (e.g. "CSE, ECE, IT"),
  "cgpa_criteria": string or null (e.g. "7.0 and above"),
   "deadline": string (required, the application deadline date in YYYY-MM-DD \
format. If the year is missing, assume the current year. Ignore terms like \
"EOD", "End of Day", "11:59 PM", and "Midnight". If an exact calendar date \
cannot be determined, return null),
  "registration_link": string or null (application/registration URL),
  "important_instructions": string or null (any special instructions, \
documents required, or notes),
  "category": one of "placement", "internship", "scholarship", "hackathon", \
"event" (required, choose the single best fit),
  "extraction_confidence": number between 0 and 1 (required, your own \
confidence that this extraction is accurate)
}}

Source text:
---
{source_text}
---

JSON output:"""


class GeminiExtractionService:
    """
    Wraps the Gemini SDK to extract structured deadline data from raw text.

    Instantiated with an API key rather than reading settings globally,
    so it can be constructed with a fake/test key in unit tests without
    touching the real settings module.
    """

    def __init__(self, api_key: str | None = None, model_name: str = _MODEL_NAME) -> None:
        genai.configure(api_key=api_key or settings.gemini_api_key)
        self._model = genai.GenerativeModel(model_name)

    def extract_from_text(self, raw_text: str) -> GeminiExtractedFields:
        """
        Extract structured fields from raw text using Gemini.

        Raises:
            EmptyResponseError: input text is blank, or Gemini returns nothing.
            GeminiAPIError: the API call itself failed.
            InvalidJSONError: Gemini's response wasn't valid JSON.
            SchemaValidationError: parsed JSON doesn't match the expected schema.
        """
        if not raw_text or not raw_text.strip():
            raise EmptyResponseError("Input text is empty — nothing to extract.")

        prompt = _EXTRACTION_PROMPT_TEMPLATE.format(source_text=raw_text.strip())
        response_text = self._call_gemini(prompt)
        payload = self._parse_json(response_text)
        return self._validate_payload(payload)

    def _call_gemini(self, prompt: str) -> str:
        """Calls the Gemini API and returns the raw text response."""
        try:
            response = self._model.generate_content(prompt)
        except Exception as exc:
            # The SDK can raise several different exception types depending
            # on failure mode (auth, quota, network). We deliberately catch
            # broadly here and wrap into our own typed error, so callers
            # only ever need to handle GeminiAPIError, not SDK internals.
            logger.exception("Gemini API call failed.")
            raise GeminiAPIError(f"Gemini API call failed: {exc}") from exc

        text = getattr(response, "text", None)
        if not text or not text.strip():
            logger.warning("Gemini returned an empty response.")
            raise EmptyResponseError("Gemini returned no content.")

        return text

    def _parse_json(self, response_text: str) -> dict:
        """
        Safely parses Gemini's response as JSON, tolerating common
        formatting quirks (e.g. wrapping output in ```json fences despite
        being told not to — this happens often enough to defend against).
        """
        cleaned = self._strip_markdown_fences(response_text)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Gemini response as JSON: %s", cleaned[:500])
            raise InvalidJSONError(
                f"Gemini response was not valid JSON: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise InvalidJSONError(
                f"Expected a JSON object, got {type(payload).__name__}."
            )

        return payload

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Removes ```json ... ``` or ``` ... ``` wrapping if present."""
        stripped = text.strip()
        match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
        return match.group(1) if match else stripped

    @staticmethod
    def _validate_payload(payload: dict) -> GeminiExtractedFields:
        """Validates the parsed JSON against the Pydantic contract."""
        try:
            return GeminiExtractedFields.model_validate(payload)
        except ValidationError as exc:
            logger.error("Gemini output failed schema validation: %s", exc)
            raise SchemaValidationError(
                "Gemini's extracted data did not match the expected schema.",
                raw_errors=exc.errors(),
            ) from exc