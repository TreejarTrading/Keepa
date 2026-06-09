"""Thin wrapper around the ``keepa`` Python package.

Centralises client creation, the Product Finder query, and product detail
fetches. The ``keepa`` package transparently handles Keepa's token bucket
(waiting/refilling) and converts raw Keepa cents/encoded values into
human-readable dollars, ratings and timestamps.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from . import config


@lru_cache(maxsize=1)
def get_client():
    """Return a cached, authenticated Keepa client.

    Imported lazily so that simply importing this module (e.g. for tests or
    report generation) does not require the API key or network access.
    """
    import keepa  # local import keeps module import cheap

    return keepa.Keepa(config.require_api_key())


def tokens_left() -> dict[str, Any]:
    """Report remaining Keepa request tokens (quota)."""
    api = get_client()
    return {
        "tokens_left": getattr(api, "tokens_left", None),
        "status": getattr(api, "status", None),
    }


def query_products(
    asins: list[str],
    *,
    domain: str | None = None,
    stats_days: int | None = None,
    offers: int = 20,
) -> list[dict[str, Any]]:
    """Fetch full product records for the given ASINs.

    Returns the raw parsed product dicts from the ``keepa`` package, including
    the ``data`` time series and the ``stats`` summary.
    """
    api = get_client()
    return api.query(
        asins,
        domain=domain or config.DEFAULT_DOMAIN,
        stats=stats_days or config.DEFAULT_STATS_DAYS,
        rating=True,
        offers=offers,
        buybox=True,
        history=True,
        wait=True,
    )


def product_finder(
    selection: dict[str, Any],
    *,
    domain: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Run a Keepa Product Finder query and return matching ASINs.

    ``selection`` follows the Keepa Product Finder schema. See
    :func:`build_selection` for a convenience builder over common filters.
    """
    api = get_client()
    return api.product_finder(
        selection,
        domain=domain or config.DEFAULT_DOMAIN,
        n_products=limit or config.DEFAULT_SEARCH_LIMIT,
    )


def build_selection(
    *,
    title: str | None = None,
    category_id: int | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    max_sales_rank: int | None = None,
    min_review_count: int | None = None,
    sort_by_sales_rank: bool = True,
) -> dict[str, Any]:
    """Translate friendly search parameters into a Keepa selection object.

    Prices are accepted in dollars and converted to the cents Keepa expects.
    Ratings are accepted as 0-5 and converted to Keepa's 0-50 scale.
    """
    sel: dict[str, Any] = {"productType": [0, 1]}  # standard + downloadable

    if title:
        sel["title"] = title
    if category_id is not None:
        sel["rootCategory"] = category_id
    if brand:
        sel["brand"] = [brand]

    # Current "New" price filter (Keepa expects cents).
    if min_price is not None:
        sel["current_NEW_gte"] = int(round(min_price * 100))
    if max_price is not None:
        sel["current_NEW_lte"] = int(round(max_price * 100))

    # Rating filter (Keepa scale = stars * 10).
    if min_rating is not None:
        sel["current_RATING_gte"] = int(round(min_rating * 10))

    if max_sales_rank is not None:
        sel["current_SALES_lte"] = int(max_sales_rank)

    if min_review_count is not None:
        sel["current_COUNT_REVIEWS_gte"] = int(min_review_count)

    if sort_by_sales_rank:
        # Best sellers first (ascending sales rank).
        sel["sort"] = [["current_SALES", "asc"]]

    return sel
