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
