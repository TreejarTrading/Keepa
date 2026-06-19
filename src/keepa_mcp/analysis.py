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


# Amazon charges a minimum referral fee per item (commonly $0.30).
_MIN_REFERRAL_FEE = 0.30


def _referral_pct(product: dict[str, Any]) -> float | None:
    """Referral fee as a fraction (0.15), read from Keepa's integer percent.

    Keepa exposes the category referral percent; field spelling has varied
    across API versions, so accept the known variants.
    """
    for key in ("referralFeePercent", "referralFeePercentage", "referralFee"):
        pct = _clean(product.get(key))
        if pct is not None:
            return round(pct / 100.0, 4) if pct > 1 else round(pct, 4)
    return None


def _fba_pick_pack_fee(product: dict[str, Any]) -> float | None:
    """FBA pick&pack fee in dollars from Keepa's ``fbaFees`` object (raw cents)."""
    fees = product.get("fbaFees")
    if isinstance(fees, dict):
        cents = _clean(fees.get("pickAndPackFee"))
        if cents is not None:
            # Nested fee objects are passed through in the smallest currency
            # unit (cents); the keepa package only converts the csv/stats series.
            return round(cents / 100.0, 2) if cents >= 50 else round(cents, 2)
    return None


def _amazon_fees(product: dict[str, Any], pricing: dict[str, Any]) -> dict[str, Any]:
    """Estimate per-unit Amazon fees so margin-after-fees can be computed.

    Combines Keepa's referral percent and FBA pick&pack fee with the realistic
    sell price (Buy Box, else current New/Amazon) to give referral fee amount,
    total fees and net proceeds — the basis for the China-sourcing margin.
    """
    from . import fees

    sell = None
    for key in ("buy_box", "new", "amazon"):
        cur = (pricing.get(key) or {}).get("current")
        if cur is not None:
            sell = cur
            break

    # Referral %: prefer Keepa's real per-product value; otherwise estimate from
    # the Amazon category (NOT a blind 15%).
    referral_pct = _referral_pct(product)
    referral_source = "keepa"
    if referral_pct is None:
        cats = [
            c.get("name")
            for c in (product.get("categoryTree") or [])
            if isinstance(c, dict)
        ]
        referral_pct = fees.estimate_referral_pct(cats, product.get("productGroup"), sell)
        referral_source = "category"

    fba_fee = _fba_pick_pack_fee(product)

    referral_fee = None
    if sell is not None and referral_pct is not None:
        referral_fee = round(max(sell * referral_pct, _MIN_REFERRAL_FEE), 2)

    total_fees = None
    if referral_fee is not None or fba_fee is not None:
        total_fees = round((referral_fee or 0.0) + (fba_fee or 0.0), 2)

    net = round(sell - total_fees, 2) if (sell is not None and total_fees is not None) else None

    return {
        "sell_price_used": sell,
        "referral_pct": referral_pct,
        "referral_pct_source": referral_source,
        "referral_fee": referral_fee,
        "fba_fee": fba_fee,
        "total_fees": total_fees,
        "net_proceeds": net,
    }


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
        "amazon_fees": _amazon_fees(product, pricing),
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


def product_overview(product: dict[str, Any], domain: str = "US") -> dict[str, Any]:
    """Catalogue / qualitative fields useful for spec & customer-need analysis."""
    from . import keepa_client

    code = keepa_client.normalize_domain(domain)
    tld = keepa_client.DOMAIN_TLDS.get(code, "com")
    domain_id = keepa_client.DOMAIN_IDS.get(code, 1)
    category_tree = product.get("categoryTree") or []
    categories = [c.get("name") for c in category_tree if isinstance(c, dict)]
    return {
        "marketplace": code,
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
        "fba_pick_pack_fee": _fba_pick_pack_fee(product),
        "referral_fee_pct": _referral_pct(product),
        "image": (product.get("imagesCSV") or "").split(",")[0] or None,
        "url": f"https://www.amazon.{tld}/dp/{product.get('asin')}"
        if product.get("asin")
        else None,
        "keepa_url": f"https://keepa.com/#!product/{domain_id}-{product.get('asin')}"
        if product.get("asin")
        else None,
    }


def build_record(
    product: dict[str, Any], stats_days: int = 90, domain: str = "US"
) -> dict[str, Any]:
    """Combine overview + metrics into a single analysis record."""
    return {
        **product_overview(product, domain=domain),
        "metrics": extract_metrics(product, stats_days=stats_days),
    }


def auto_verdict(record: dict[str, Any]) -> dict[str, Any]:
    """Attach a rule-based verdict to a record (used by unattended auto runs).

    Mirrors DECISION_GUIDANCE so scheduled reports are immediately actionable;
    when Claude is in the loop it produces its own, richer verdicts instead.
    """
    m = record.get("metrics") or {}
    pricing = (m.get("pricing") or {}).get("new") or {}
    rank = m.get("sales_rank") or {}
    comp = m.get("competition") or {}
    offers = (comp.get("offer_count") or {}).get("current")
    reviews = m.get("reviews") or {}
    demand = m.get("demand") or {}

    pros: list[str] = []
    cons: list[str] = []

    volatility = pricing.get("volatility")
    if volatility is not None:
        if volatility <= 0.25:
            pros.append(f"stable price (volatility {volatility})")
        elif volatility >= 0.5:
            cons.append(f"volatile price (volatility {volatility})")

    drops30 = rank.get("drops_30d")
    monthly = demand.get("monthly_sold_estimate")
    if (drops30 or 0) >= 8 or (monthly or 0) >= 300:
        pros.append(f"healthy sales velocity (drops30={drops30}, monthly≈{monthly})")
    elif drops30 is not None and drops30 <= 2 and (monthly or 0) < 100:
        cons.append(f"weak sales velocity (drops30={drops30}, monthly≈{monthly})")

    if comp.get("buy_box_is_amazon"):
        cons.append("Amazon holds the Buy Box")
    if offers is not None:
        if offers <= 12:
            pros.append(f"moderate competition ({int(offers)} offers)")
        elif offers >= 25:
            cons.append(f"crowded listing ({int(offers)} offers)")

    rating = reviews.get("rating_current")
    review_count = reviews.get("review_count_current")
    if rating is not None:
        if rating >= 4.2 and (review_count or 0) >= 100:
            pros.append(f"strong rating {rating} with {int(review_count)} reviews")
        elif rating < 4.0:
            cons.append(f"low rating {rating}")

    if len(cons) >= 3 or (rating is not None and rating < 3.8):
        verdict = "SKIP"
    elif len(pros) >= 3 and len(cons) <= 1:
        verdict = "BUY"
    else:
        verdict = "WATCH"

    confidence = "high" if len(pros) + len(cons) >= 4 else "medium" if pros or cons else "low"
    rationale = "; ".join(["+ " + p for p in pros] + ["- " + c for c in cons]) or "insufficient data"
    return {**record, "verdict": verdict, "confidence": confidence, "rationale": rationale}


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
