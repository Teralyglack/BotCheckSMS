class MissingCredentialsError(RuntimeError):
    """Raised when an external Russian API provider is not configured."""


class ExternalAPIError(RuntimeError):
    """Raised when an external API returns an error or an unexpected response."""
