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

# Friendly aliases -> Keepa domain codes (the keepa package expects "GB",
# not "UK"). Keys are upper-case.
_DOMAIN_ALIASES = {
    "UK": "GB",
    "GB": "GB",
    "US": "US",
    "USA": "US",
    "DE": "DE",
    "FR": "FR",
    "IT": "IT",
    "ES": "ES",
    "JP": "JP",
    "CA": "CA",
    "IN": "IN",
    "MX": "MX",
    "BR": "BR",
}

# Keepa numeric domain ids (for keepa.com product links).
DOMAIN_IDS = {
    "US": 1, "GB": 2, "DE": 3, "FR": 4, "JP": 5, "CA": 6,
    "IT": 8, "ES": 9, "IN": 10, "MX": 11, "BR": 12,
}

# Amazon storefront TLD per Keepa domain code.
DOMAIN_TLDS = {
    "US": "com", "GB": "co.uk", "DE": "de", "FR": "fr", "JP": "co.jp",
    "CA": "ca", "IT": "it", "ES": "es", "IN": "in", "MX": "com.mx", "BR": "com.br",
}


def normalize_domain(domain: str | None) -> str:
    """Map a user-facing market name (e.g. "UK") to a Keepa domain code."""
    raw = (domain or config.DEFAULT_DOMAIN or "US").strip().upper()
    code = _DOMAIN_ALIASES.get(raw)
    if code is None:
        raise ValueError(
            f"Unsupported marketplace {raw!r}. Use one of: "
            f"{', '.join(sorted(set(_DOMAIN_ALIASES)))}"
        )
    return code


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
    error: str | None = None
    try:
        api.update_status()
    except Exception as exc:  # noqa: BLE001 - report instead of crashing
        error = f"{type(exc).__name__}: {exc}"
        if "403" in str(exc):
            error += (
                " — likely an invalid key, no active Keepa API subscription, or "
                "api.keepa.com is blocked by the network policy/allowlist."
            )
    status = getattr(api, "status", None)
    return {
        "tokens_left": getattr(api, "tokens_left", None),
        "refill_in_ms": getattr(status, "refillIn", None),
        "refill_rate_per_min": getattr(status, "refillRate", None),
        "error": error,
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
        domain=normalize_domain(domain),
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
        domain=normalize_domain(domain),
        n_products=limit or config.DEFAULT_SEARCH_LIMIT,
    )


def search_categories(searchterm: str, *, domain: str | None = None) -> dict[str, Any]:
    """Find Keepa category ids whose names match ``searchterm``."""
    api = get_client()
    return api.search_for_categories(searchterm, domain=normalize_domain(domain)) or {}


def category_lookup(category_id: int, *, domain: str | None = None) -> dict[str, Any]:
    """Fetch details (name, parent, children) for a Keepa category id."""
    api = get_client()
    return api.category_lookup(category_id, domain=normalize_domain(domain)) or {}


def best_sellers(category_id: int, *, domain: str | None = None) -> list[str]:
    """Return best-selling ASINs for a category (Amazon Best Sellers list)."""
    api = get_client()
    result = api.best_sellers_query(str(category_id), domain=normalize_domain(domain))
    return list(result or [])


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
    max_offer_count: int | None = None,
    min_monthly_sold: int | None = None,
    min_rank_drops_30: int | None = None,
    sort_by_sales_rank: bool = True,
    extra_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate friendly search parameters into a Keepa selection object.

    Prices are accepted in dollars and converted to the cents Keepa expects.
    Ratings are accepted as 0-5 and converted to Keepa's 0-50 scale.
    ``extra_filters`` are raw Keepa Product Finder keys merged on top, so any
    additional filter the user supplies is passed through verbatim.
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

    if max_offer_count is not None:
        sel["current_COUNT_NEW_lte"] = int(max_offer_count)

    if min_monthly_sold is not None:
        sel["monthlySold_gte"] = int(min_monthly_sold)

    # Sales-rank drops in 30 days ≈ units sold — a reliable "is it actually
    # selling / gaining momentum" floor for discovery sweeps.
    if min_rank_drops_30 is not None:
        sel["salesRankDrops30_gte"] = int(min_rank_drops_30)

    if sort_by_sales_rank:
        # Best sellers first (ascending sales rank).
        sel["sort"] = [["current_SALES", "asc"]]

    if extra_filters:
        sel.update(extra_filters)

    return sel
