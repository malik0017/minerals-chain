"""
app/core/exceptions.py
"""

class NotAuthenticatedException(Exception):
    pass

class ForbiddenException(Exception):
    pass

class CompanyNotApprovedException(Exception):
    pass

class AdminRedirectException(Exception):

    def __init__(self, redirect_route_name: str, query: str | None = None):
        self.redirect_route_name = redirect_route_name
        self.query = query

class RateLimitExceededException(Exception):
    """Batch G — raised by app/core/rate_limit.py when a caller has
    exceeded one of the login/OTP rate limits. Carries how long until the
    next attempt is allowed so the handler can show a useful message."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
