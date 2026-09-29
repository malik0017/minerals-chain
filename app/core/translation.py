"""
app/core/translation.py
"""
import html as html_lib
import re
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CACHE_SECONDS = 120
_cache: dict = {"at": 0.0, "exact": {}, "patterns": []}

_SKIP_BLOCK = re.compile(
    r"(<(script|style|textarea|pre|code)\b[^>]*>.*?</\2\s*>)|(<[^>]*\btranslate=\"no\"[^>]*>.*?</[a-z0-9]+\s*>)",
    re.S | re.I,
)
_TEXT_NODE = re.compile(r">([^<>]+)<")
_ATTR = re.compile(r'\b(placeholder|title|aria-label|data-bs-title|alt)="([^"]*)"')


def _norm(text: str) -> str:
    return " ".join(html_lib.unescape(text).split())


def invalidate() -> None:
    _cache["at"] = 0.0


def _load() -> None:
    from app.database.base import SessionLocal
    from app.models.ui_translation import UITranslation
    exact, patterns = {}, []
    db = SessionLocal()
    try:
        for src, ar in db.query(UITranslation.source_text, UITranslation.text_ar).filter(UITranslation.is_active.is_(True)):
            key = _norm(src)
            if not key or not ar:
                continue
            if "{}" in key:
                rx = "^" + re.escape(key).replace(r"\{\}", "(.+?)") + "$"
                patterns.append((re.compile(rx), ar))
            else:
                exact[key] = ar
    except Exception: 
        db.rollback()
    finally:
        db.close()
    _cache.update(at=time.monotonic(), exact=exact, patterns=patterns)


def lookup(text: str) -> str | None:
    if time.monotonic() - _cache["at"] > CACHE_SECONDS:
        _load()
    key = _norm(text)
    if not key:
        return None
    hit = _cache["exact"].get(key)
    if hit is not None:
        return hit
    for rx, ar in _cache["patterns"]:
        m = rx.match(key)
        if m:
            out = ar
            for g in m.groups():
                out = out.replace("{}", _translate_fragment(g), 1)
            return out
    return None


def _translate_fragment(value: str) -> str:
    hit = _cache["exact"].get(value)
    return hit if hit is not None else value


def translate_text(text: str) -> str:
    return lookup(text) or text


def translate_html(page: str) -> str:
    def text_node(m: re.Match) -> str:
        raw = m.group(1)
        if not raw.strip():
            return m.group(0)
        ar = lookup(raw)
        if ar is None:
            return m.group(0)
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        return ">" + lead + html_lib.escape(ar, quote=False) + trail + "<"

    def attr(m: re.Match) -> str:
        ar = lookup(m.group(2))
        return m.group(0) if ar is None else f'{m.group(1)}="{html_lib.escape(ar, quote=True)}"'

    out, pos = [], 0
    for block in _SKIP_BLOCK.finditer(page):
        chunk = page[pos:block.start()]
        out.append(_ATTR.sub(attr, _TEXT_NODE.sub(text_node, chunk)))
        out.append(block.group(0))
        pos = block.end()
    chunk = page[pos:]
    out.append(_ATTR.sub(attr, _TEXT_NODE.sub(text_node, chunk)))
    return "".join(out)


class TranslationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if not response.headers.get("content-type", "").startswith("text/html"):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        if b'lang="ar"' in body[:800]:
            body = translate_html(body.decode("utf-8")).encode("utf-8")
        new = Response(content=body, status_code=response.status_code)
        new.raw_headers = [(k, v) for k, v in response.raw_headers if k.lower() != b"content-length"] + [
            (b"content-length", str(len(body)).encode())
        ]
        return new
