"""
app/modules/public/security_routes.py
"""
import json

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.config import settings
from app.core.security_headers import record_violation

router = APIRouter(tags=["security"])


@router.post("/csp-report", include_in_schema=False)
async def csp_report(request: Request):
    body = await request.body()
    if len(body) <= 16384:
        try:
            record_violation(json.loads(body or b"{}"))
        except ValueError:
            pass
    return Response(status_code=204)


@router.get("/.well-known/security.txt", include_in_schema=False)
def security_txt():
    return PlainTextResponse(
        f"Contact: mailto:security@mineralschain.sa\nExpires: 2027-12-31T23:59:59Z\nPreferred-Languages: en, ar\n"
        f"Canonical: {settings.PUBLIC_BASE_URL.rstrip('/')}/.well-known/security.txt\n")
