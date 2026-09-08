"""
app/core/exceptions.py

"""


class NotAuthenticatedException(Exception):
    pass

class ForbiddenException(Exception):
    pass


class CompanyNotApprovedException(Exception):
    pass
