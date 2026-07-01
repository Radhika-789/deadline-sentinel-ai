"""
Custom exceptions for the extraction pipeline.

Defining typed exceptions (instead of raising generic Exception/ValueError)
lets the API layer later catch specific failure modes and return the
right HTTP status + user-facing message for each one.
"""


class ExtractionError(Exception):
    """Base class for all extraction-related failures."""


class GeminiAPIError(ExtractionError):
    """Raised when the Gemini API call itself fails (network, auth, quota)."""


class EmptyResponseError(ExtractionError):
    """Raised when Gemini returns no usable content."""


class InvalidJSONError(ExtractionError):
    """Raised when Gemini's response isn't parseable as JSON."""


class SchemaValidationError(ExtractionError):
    """Raised when parsed JSON doesn't satisfy GeminiExtractedFields."""

    def __init__(self, message: str, raw_errors: list[dict] | None = None) -> None:
        super().__init__(message)
        self.raw_errors = raw_errors or []