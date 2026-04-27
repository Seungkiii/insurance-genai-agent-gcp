"""Custom exception definitions."""


class AppError(Exception):
    """Base application exception."""


class NotImplementedPlaceholder(AppError):
    """Raised when a placeholder feature is not implemented."""
