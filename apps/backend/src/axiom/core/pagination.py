from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int
    per_page: int


def clamp_page_params(
    page: int,
    per_page: int,
    *,
    max_per_page: int = 100,
    default_per_page: int = 20,
) -> PageParams:
    safe_page = max(1, page)
    safe_per = min(max_per_page, max(1, per_page or default_per_page))
    return PageParams(page=safe_page, per_page=safe_per)


def pagination_meta(*, total: int, page: int, per_page: int) -> dict[str, int | bool]:
    has_more = page * per_page < total
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": has_more,
    }


def total_pages(total: int, per_page: int) -> int:
    if per_page <= 0:
        return 0
    return ceil(total / per_page)
