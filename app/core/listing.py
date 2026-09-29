"""
app/core/listing.py
"""
from urllib.parse import urlencode

PAGE_SIZE = 25


def paginate(query, page: int, page_size: int = PAGE_SIZE):
    page = max(1, page or 1)
    total = query.order_by(None).count()
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total, page, pages


def qs(**params) -> str:
    return urlencode({k: v for k, v in params.items() if v not in (None, "")})
