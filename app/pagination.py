"""Простая серверная пагинация для списков админки."""

from __future__ import annotations

from math import ceil
from urllib.parse import urlencode


DEFAULT_PER_PAGE = 25
ALLOWED_PER_PAGE = (10, 25, 50, 100)


def parse_page_args(page: int | None, per_page: int | None) -> tuple[int, int]:
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(per_page or DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    if page < 1:
        page = 1
    if per_page not in ALLOWED_PER_PAGE:
        per_page = DEFAULT_PER_PAGE
    return page, per_page


def paginate(query, page: int, per_page: int) -> dict:
    """Возвращает slice query и метаданные для шаблона."""
    total = query.count()
    pages = max(1, ceil(total / per_page)) if total else 1
    if page > pages:
        page = pages
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "rows": items,
        "count": len(items),
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < pages else None,
    }


def page_url(base_path: str, page: int, per_page: int, q: str = "", extra: dict | None = None) -> str:
    params = {"page": page, "per_page": per_page}
    if q:
        params["q"] = q
    if extra:
        params.update({k: v for k, v in extra.items() if v is not None and v != ""})
    return f"{base_path}?{urlencode(params)}"
