"""
app/core/client_ip.py
"""
from starlette.requests import Request


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
