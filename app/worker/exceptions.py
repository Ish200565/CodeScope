class TransientError(Exception):
    """Temporary problem (network, 5xx, rate limit). Safe to retry."""


class PermanentError(Exception):
    """Retrying will not help (bad data, not found). Fail immediately."""