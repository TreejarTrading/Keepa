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


def _out_of_stock_pct(product: dict[str, Any]) -> float | None:
    """Best-effort out-of-stock percentage from the Keepa stats object.

    Keepa exposes several ``outOfStockPercentage*`` fields depending on the
    requested window. We take the first usable one so inventory signals work
    whenever the stats object is present, and degrade gracefully otherwise.
    """
    stats = product.get("stats")
    if not isinstance(stats, dict):
        return None
    for key, value in stats.items():
        if "outofstock" in str(key).lower():
            v = _clean(value)
            if v is not None:
                return min(100.0, v)
    return None


def estimate_velocity(
    monthly_sold: float | None,
    rank_current: float | None,
    rank_avg: float | None,
) -> dict[str, Any]:
    """Estimate sales velocity (daily/weekly/monthly) and its trend.

    Prefers Keepa's actual ``monthlySold`` when present; otherwise falls back
    to a rank-based heuristic (``1e6 / sqrt(rank)``) adapted from common Keepa
    tooling. Marked as an estimate so downstream consumers know its precision.
    """
    source = None
    daily: float | None = None
    if monthly_sold and monthly_sold > 0:
        daily = monthly_sold / 30.0
        source = "monthly_sold"
    elif rank_current and rank_current > 0:
        daily = max(1.0, math.floor(1_000_000 / math.sqrt(rank_current)))
        source = "rank_estimate"

    if daily is None:
        return {
            "estimated_daily_sales": None,
            "estimated_weekly_sales": None,
            "estimated_monthly_sales": None,
            "trend": None,
            "change_pct": None,
            "source": None,
        }

    # Trend: a *lower* current rank than the window average means the item is
    # selling faster now than on average -> accelerating.
    trend = None
    change_pct = None
    if rank_current and rank_avg and rank_avg > 0:
        change_pct = round((rank_avg - rank_current) / rank_avg * 100, 1)
        if change_pct > 5:
            trend = "accelerating"
        elif change_pct < -5:
            trend = "declining"
        else:
            trend = "stable"

    return {
        "estimated_daily_sales": int(round(daily)),
        "estimated_weekly_sales": int(round(daily * 7)),
        "estimated_monthly_sales": int(round(daily * 30)),
        "trend": trend,
        "change_pct": change_pct,
        "source": source,
    }


def inventory_signals(
    daily_sales: float | None, out_of_stock_pct: float | None
) -> dict[str, Any]:
    """Inventory turnover, days-of-inventory, reorder qty and stockout risk.

    Thresholds adapted from common Keepa inventory tooling; ``daily_sales``
    comes from :func:`estimate_velocity` so the numbers stay consistent with
    the velocity block.
    """
    if out_of_stock_pct is None:
        turnover = None
        risk = "unknown"
    else:
        turnover = max(1.0, 12 - (out_of_stock_pct / 10)) if out_of_stock_pct < 50 else 1.0
        if out_of_stock_pct > 30:
            risk = "high"
        elif out_of_stock_pct > 15:
            risk = "medium"
        else:
            risk = "low"

    days_of_inventory = None
    reorder_qty = None
    if daily_sales and daily_sales > 0:
        days_of_inventory = math.ceil(30 / max(1.0, daily_sales))
        reorder_qty = math.ceil(daily_sales * 30)

    return {
        "turnover_rate": round(turnover, 1) if turnover is not None else None,
        "days_of_inventory": days_of_inventory,
        "recommended_order_qty": reorder_qty,
        "out_of_stock_pct": round(out_of_stock_pct, 1) if out_of_stock_pct is not None else None,
        "stockout_risk": risk,
    }


def opportunity_score(record: dict[str, Any]) -> dict[str, Any]:
    """A 0-100 market-opportunity score with the drivers that produced it.

    Higher = a more attractive niche to enter. Combines competition (rank &
    offers), quality headroom (low ratings = room for a better product), a
    price sweet spot and price stability. Adapted and extended from the
    opportunity heuristic in cosjef/Keepa_MCP.
    """
    m = record.get("metrics") or {}
    rank = (m.get("sales_rank") or {})
    pricing = (m.get("pricing") or {}).get("new") or {}
    comp = m.get("competition") or {}
    offers = (comp.get("offer_count") or {}).get("current")
    rating = (m.get("reviews") or {}).get("rating_current")
    avg_rank = rank.get("avg") or rank.get("current")
    avg_price = pricing.get("avg") or pricing.get("current")
    volatility = pricing.get("volatility")

    score = 50
    drivers: list[str] = []

    if avg_rank is not None:
        if avg_rank > 100_000:
            score += 30
            drivers.append("low competition (high avg rank)")
        elif avg_rank > 50_000:
            score += 20
            drivers.append("moderate competition")
        elif avg_rank < 5_000:
            score -= 10
            drivers.append("crowded (very low rank)")

    if rating is not None and rating < 3.8:
        score += 15
        drivers.append(f"quality headroom (rating {rating})")

    if avg_price is not None and 20 <= avg_price <= 100:
        score += 10
        drivers.append("price in sweet spot ($20-100)")

    if volatility is not None:
        if volatility <= 0.25:
            score += 10
            drivers.append("stable price")
        elif volatility >= 0.5:
            score -= 10
            drivers.append("volatile price")

    if offers is not None:
        if offers <= 12:
            score += 10
            drivers.append(f"few offers ({int(offers)})")
        elif offers >= 25:
            score -= 10
            drivers.append(f"many offers ({int(offers)})")

    score = max(0, min(100, score))
    label = "high" if score >= 70 else "medium" if score >= 45 else "low"
    return {"score": score, "label": label, "drivers": drivers}


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

    velocity = estimate_velocity(monthly_sold, rank.get("current"), rank.get("avg"))
    inventory = inventory_signals(
        velocity.get("estimated_daily_sales"), _out_of_stock_pct(product)
    )

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
        "velocity": velocity,
        "inventory": inventory,
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
    """Combine overview + metrics + opportunity into a single analysis record."""
    record = {
        **product_overview(product, domain=domain),
        "metrics": extract_metrics(product, stats_days=stats_days),
    }
    record["opportunity"] = opportunity_score(record)
    return record


def portfolio_health(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate fast/slow-mover health across a set of records.

    Fast mover: ~30+ est. units/month. Slow mover: <10 est. units/month.
    Classification thresholds adapted from cosjef/Keepa_MCP.
    """
    total = len(records)
    if total == 0:
        return {"products": 0, "rating": "n/a", "fast_movers": 0, "slow_movers": 0}

    fast = slow = 0
    for rec in records:
        monthly = (((rec.get("metrics") or {}).get("velocity") or {})
                   .get("estimated_monthly_sales"))
        if monthly is None:
            continue
        if monthly >= 30:
            fast += 1
        elif monthly < 10:
            slow += 1

    fast_ratio = fast / total
    slow_ratio = slow / total
    if fast_ratio > 0.30 and slow_ratio < 0.30:
        rating = "excellent"
    elif fast_ratio > 0.20 and slow_ratio < 0.40:
        rating = "good"
    elif slow_ratio > 0.50:
        rating = "poor"
    else:
        rating = "fair"

    return {
        "products": total,
        "rating": rating,
        "fast_movers": fast,
        "slow_movers": slow,
        "fast_mover_pct": round(fast_ratio * 100, 1),
        "slow_mover_pct": round(slow_ratio * 100, 1),
    }


def category_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Market-level summary: price bands, competition, quality, brand share.

    A compact category-analysis block adapted from cosjef/Keepa_MCP, computed
    over whatever record set is passed (best sellers, a search, etc.).
    """
    total = len(records)
    if total == 0:
        return {"products": 0}

    prices: list[float] = []
    ranks: list[float] = []
    ratings: list[float] = []
    opp_scores: list[int] = []
    brands: dict[str, int] = {}
    bands = {"budget": 0, "mid": 0, "premium": 0, "luxury": 0}

    for rec in records:
        m = rec.get("metrics") or {}
        price = ((m.get("pricing") or {}).get("new") or {}).get("current")
        rank = (m.get("sales_rank") or {}).get("current")
        rating = (m.get("reviews") or {}).get("rating_current")
        opp = (rec.get("opportunity") or {}).get("score")
        brand = rec.get("brand")
        if price is not None:
            prices.append(price)
            if price < 25:
                bands["budget"] += 1
            elif price < 75:
                bands["mid"] += 1
            elif price < 200:
                bands["premium"] += 1
            else:
                bands["luxury"] += 1
        if rank is not None:
            ranks.append(rank)
        if rating is not None:
            ratings.append(rating)
        if opp is not None:
            opp_scores.append(opp)
        if brand:
            brands[brand] = brands.get(brand, 0) + 1

    avg_rank = sum(ranks) / len(ranks) if ranks else None
    avg_rating = sum(ratings) / len(ratings) if ratings else None
    if avg_rank is None:
        competition = "unknown"
    elif avg_rank < 10_000:
        competition = "high"
    elif avg_rank <= 50_000:
        competition = "medium"
    else:
        competition = "low"
    if avg_rating is None:
        quality = "unknown"
    elif avg_rating >= 4.2:
        quality = "excellent"
    elif avg_rating >= 3.8:
        quality = "good"
    elif avg_rating >= 3.0:
        quality = "fair"
    else:
        quality = "poor"

    top_brands = sorted(brands.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_share = round(top_brands[0][1] / total * 100, 1) if top_brands else 0

    return {
        "products": total,
        "price_avg": round(sum(prices) / len(prices), 2) if prices else None,
        "price_min": round(min(prices), 2) if prices else None,
        "price_max": round(max(prices), 2) if prices else None,
        "price_bands": bands,
        "competition_level": competition,
        "avg_sales_rank": int(avg_rank) if avg_rank is not None else None,
        "quality": quality,
        "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
        "avg_opportunity_score": round(sum(opp_scores) / len(opp_scores), 1) if opp_scores else None,
        "unique_brands": len(brands),
        "top_brands": [{"brand": b, "count": c} for b, c in top_brands],
        "leader_share_pct": top_share,
        "portfolio_health": portfolio_health(records),
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
