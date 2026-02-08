"""Custom exception types for clearer error handling."""

class PupExporterError(Exception):
    """Base exception for the app."""

class RemoteFetchError(PupExporterError):
    """Raised when a remote HTTP fetch fails."""

class DataValidationError(PupExporterError):
    """Raised when expected data is missing or malformed."""

class NoUpdateError(PupExporterError):
    """Raised when no remote updates are detected."""
