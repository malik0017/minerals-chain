"""
app/core/forms.py
"""
from fastapi import Request
from starlette.datastructures import FormData


async def form_data(request: Request) -> FormData:
    return await request.form()
