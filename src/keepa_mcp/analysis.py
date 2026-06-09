"""Distil raw Keepa product records into purchase-decision metrics.

The MCP server returns these structured metrics to Claude, which performs the
qualitative buy/skip reasoning (reviews, specs, customer-need fit). The numeric
extraction here is deliberately defensive: Keepa fields are frequently missing
or sentinel-valued (-1 / NaN), so every accessor tolerates absence.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

# Keepa "data" time-series keys we care about (price keys are in dollars,
# already converted by the keepa package; -1/NaN means "no data").
_PRICE_KEYS = {
    "amazon": "AMAZON",
    "new": "NEW",
    "used": "USED",
    "buy_box": "BUY_BOX_SHIPPING",
    "new_fba": "NEW_FBA",
}


def _clean(value: Any) -> float | None:
    """Return a usable float or None for Keepa sentinels (-1, NaN, None)."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or f < 0:
        return None
    return f


def _window_stats(values, times, days: int | None) -> dict[str, float | None]:
    """Compute min/max/avg/current over the last ``days`` of a time series."""
    out: dict[str, float | None] = {"current": None, "min": None, "max": None, "avg": None}
    if values is None or times is None or len(values) == 0:
        return out

    pairs: list[tuple[Any, float]] = []
    for t, v in zip(times, values):
        cv = _clean(v)
        if cv is not None:
            pairs.append((t, cv))
    if not pairs:
        return out

    out["current"] = pairs[-1][1]

    if days is not None and len(pairs) > 1:
        try:
            latest = pairs[-1][0]
            # times are numpy datetime64; convert via python datetime when possible
            cutoff = _to_datetime(latest) - timedelta(days=days)
            pairs = [(t, v) for t, v in pairs if _to_datetime(t) >= cutoff] or pairs
        except Exception:
            pass

    nums = [v for _, v in pairs]
    out["min"] = min(nums)
    out["max"] = max(nums)
    out["avg"] = round(sum(nums) / len(nums), 2)
    return out


def _to_datetime(value: Any) -> datetime:
    """Best-effort conversion of a numpy datetime64 / datetime to datetime."""
    if isinstance(value, datetime):
        return value
    # numpy datetime64 -> python datetime
    try:
        import numpy as np  # noqa

        return value.astype("datetime64[s]").astype(datetime)
    except Exception:
        return datetime.utcnow()


def _price_volatility(stats: dict[str, float | None]) -> float | None:
    """Spread between min and max as a fraction of the average price."""
    lo, hi, avg = stats.get("min"), stats.get("max"), stats.get("avg")
    if lo is None or hi is None or not avg:
        return None
    return round((hi - lo) / avg, 3)


def _rank_drops(values, times, days: int | None = 90) -> int | None:
    """Count sales-rank drops (a proxy for sales events) over a window.

    A meaningful drop in sales rank generally corresponds to a unit sold.
    """
    if values is None or len(values) < 2:
        return None
    pairs: list[float] = []
    cutoff = None
    if days is not None and times is not None and len(times) == len(values):
        try:
            cutoff = _to_datetime(times[-1]) - timedelta(days=days)
        except Exception:
            cutoff = None
    for i, v in enumerate(values):
        cv = _clean(v)
        if cv is None:
            continue
        if cutoff is not None:
            try:
                if _to_datetime(times[i]) < cutoff:
                    continue
            except Exception:
                pass
        pairs.append(cv)
    drops = 0
    for prev, cur in zip(pairs, pairs[1:]):
        # rank getting smaller = improvement = likely a sale
        if cur < prev * 0.9:  # >10% improvement
            drops += 1
    return drops


def extract_metrics(product: dict[str, Any], stats_days: int = 90) -> dict[str, Any]:
    """Build a flat, decision-oriented metrics dict from a Keepa product."""
    data = product.get("data") or {}

    def series(key: str):
        return data.get(key), data.get(f"{key}_time")

    # --- pricing ---------------------------------------------------------
    pricing: dict[str, Any] = {}
    for label, key in _PRICE_KEYS.items():
        vals, times = series(key)
        s = _window_stats(vals, times, stats_days)
        s["volatility"] = _price_volatility(s)
        pricing[label] = s

    # --- sales rank & velocity ------------------------------------------
    rank_vals, rank_times = series("SALES")
    rank = _window_stats(rank_vals, rank_times, stats_days)
    rank_drops_30 = _rank_drops(rank_vals, rank_times, days=30)
    rank_drops_90 = _rank_drops(rank_vals, rank_times, days=90)

    # --- competition -----------------------------------------------------
    offer_vals, offer_times = series("COUNT_NEW")
    offers = _window_stats(offer_vals, offer_times, stats_days)

    # --- reviews / ratings ----------------------------------------------
    rating_vals, rating_times = series("RATING")
    rating = _window_stats(rating_vals, rating_times, stats_days)
    review_vals, review_times = series("COUNT_REVIEWS")
    reviews = _window_stats(review_vals, review_times, stats_days)
    review_velocity = None
    if reviews.get("current") is not None and reviews.get("min") is not None:
        delta = reviews["current"] - reviews["min"]
        review_velocity = round(delta / max(stats_days, 1) * 30, 1)  # ~per month

    monthly_sold = product.get("monthlySold") or product.get("monthlySoldEstimate")

    return {
        "pricing": pricing,
        "sales_rank": {
            **rank,
            "drops_30d": rank_drops_30,
            "drops_90d": rank_drops_90,
        },
        "competition": {
            "offer_count": offers,
            "buy_box_seller_id": product.get("buyBoxSellerId"),
            "buy_box_is_amazon": product.get("buyBoxIsAmazon"),
        },
        "demand": {
            "monthly_sold_estimate": monthly_sold,
            "review_velocity_per_month": review_velocity,
        },
        "reviews": {
            "rating_current": rating.get("current"),
            "rating_avg": rating.get("avg"),
            "review_count_current": reviews.get("current"),
        },
    }


def product_overview(product: dict[str, Any]) -> dict[str, Any]:
    """Catalogue / qualitative fields useful for spec & customer-need analysis."""
    category_tree = product.get("categoryTree") or []
    categories = [c.get("name") for c in category_tree if isinstance(c, dict)]
    return {
        "asin": product.get("asin"),
        "title": product.get("title"),
        "brand": product.get("brand") or product.get("manufacturer"),
        "manufacturer": product.get("manufacturer"),
        "product_group": product.get("productGroup"),
        "category_tree": categories,
        "features": product.get("features") or [],
        "description": product.get("description"),
        "number_of_items": product.get("numberOfItems"),
        "package_weight_g": product.get("packageWeight"),
        "package_dimensions": {
            "length": product.get("packageLength"),
            "width": product.get("packageWidth"),
            "height": product.get("packageHeight"),
        },
        "variation_count": len(product.get("variations") or []),
        "fba_fees": product.get("fbaFees"),
        "image": (product.get("imagesCSV") or "").split(",")[0] or None,
        "url": f"https://www.amazon.com/dp/{product.get('asin')}"
        if product.get("asin")
        else None,
        "keepa_url": f"https://keepa.com/#!product/1-{product.get('asin')}"
        if product.get("asin")
        else None,
    }


def build_record(product: dict[str, Any], stats_days: int = 90) -> dict[str, Any]:
    """Combine overview + metrics into a single analysis record."""
    return {
        **product_overview(product),
        "metrics": extract_metrics(product, stats_days=stats_days),
    }


# Guidance returned alongside data so Claude's verdicts stay consistent.
DECISION_GUIDANCE = {
    "buy_signals": [
        "Stable price history (low volatility) with healthy margin headroom",
        "Strong, steady sales velocity (frequent sales-rank drops, high monthly_sold)",
        "Low/moderate offer count (less competition), Buy Box not dominated by Amazon",
        "Rating >= 4.2 with a substantial and growing review count",
        "Clear, well-differentiated feature set matching evident customer needs",
    ],
    "risk_signals": [
        "High price volatility or a long downward price trend (margin erosion)",
        "Amazon holds the Buy Box (hard to compete)",
        "Very high offer count (price war / race to the bottom)",
        "Rating < 4.0 or recurring complaint themes in features/category",
        "Thin or stalled review velocity (weak or fading demand)",
        "Bulky/heavy item inflating FBA / shipping costs",
    ],
    "recommended_output": "For each ASIN give a verdict (BUY / WATCH / SKIP), a "
    "confidence level, the 2-3 metrics that drove it, and how well the product "
    "satisfies the target customer need.",
}
