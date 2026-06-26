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


def _trend_pct(values, times, days: int | None, *, improving_is_down: bool) -> float | None:
    """Percent change between the recent third and the earlier part of a window.

    Compares the mean of the most recent third against the earlier portion. For
    sales rank (``improving_is_down=True``) a *falling* rank is good, so a
    positive result means the product is gaining momentum; for price/reviews a
    *rising* value is the positive direction.
    """
    if values is None or times is None or len(values) < 4:
        return None
    pairs: list[tuple[Any, float]] = []
    for t, v in zip(times, values):
        cv = _clean(v)
        if cv is not None:
            pairs.append((t, cv))
    if len(pairs) < 4:
        return None
    if days is not None:
        try:
            cutoff = _to_datetime(pairs[-1][0]) - timedelta(days=days)
            windowed = [(t, v) for t, v in pairs if _to_datetime(t) >= cutoff]
            if len(windowed) >= 4:
                pairs = windowed
        except Exception:
            pass
    k = max(1, len(pairs) // 3)
    recent = [v for _, v in pairs[-k:]]
    older = [v for _, v in pairs[:-k]]
    older_avg = sum(older) / len(older)
    if not older_avg:
        return None
    change = (sum(recent) / len(recent) - older_avg) / older_avg * 100.0
    if improving_is_down:
        change = -change  # falling rank → positive "improving" number
    return round(change, 1)


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
    # Momentum: positive % = sales rank improving over the window (rising demand).
    rank_trend_pct = _trend_pct(rank_vals, rank_times, stats_days, improving_is_down=True)

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
            "trend_pct": rank_trend_pct,
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


def _image_url(images_csv: str | None) -> str | None:
    """Build the full Amazon media URL for the main image (Keepa stores names)."""
    name = (images_csv or "").split(",")[0].strip()
    return f"https://m.media-amazon.com/images/I/{name}" if name else None


def product_overview(product: dict[str, Any], domain: str = "US") -> dict[str, Any]:
    """Catalogue / qualitative fields useful for spec & customer-need analysis."""
    from . import keepa_client, sourcing

    code = keepa_client.normalize_domain(domain)
    tld = keepa_client.DOMAIN_TLDS.get(code, "com")
    domain_id = keepa_client.DOMAIN_IDS.get(code, 1)
    category_tree = product.get("categoryTree") or []
    categories = [c.get("name") for c in category_tree if isinstance(c, dict)]
    title = product.get("title")
    brand = product.get("brand") or product.get("manufacturer")
    # Buyer-facing supplier-search links (Alibaba) derived from the title.
    links = sourcing.sourcing_links(title, brand, categories[-1] if categories else None)
    return {
        "marketplace": code,
        "asin": product.get("asin"),
        "title": title,
        "brand": brand,
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
        "image": _image_url(product.get("imagesCSV")),
        "url": f"https://www.amazon.{tld}/dp/{product.get('asin')}"
        if product.get("asin")
        else None,
        "keepa_url": f"https://keepa.com/#!product/{domain_id}-{product.get('asin')}"
        if product.get("asin")
        else None,
        **links,
    }


# --- Discovery / momentum classification ------------------------------------
# Buckets the buyer report sorts by: what already sells, what's gaining
# momentum, and what's newly launched. Thresholds are named so they're tunable.
NEW_LISTING_DAYS = 180        # tracked ≤ this many days → "New" arrival
BESTSELLER_RANK_MAX = 15000   # current sales rank ≤ this → "Bestseller"
BESTSELLER_MONTHLY = 300      # OR monthly sold ≥ this → "Bestseller"
RISING_TREND_PCT = 20.0       # sales rank improved ≥ this % over window → "Rising"
RISING_DROPS_30 = 8           # OR ≥ this many rank drops in 30d → "Rising"

# Keepa stores time as minutes since 2011-01-01 UTC.
_KEEPA_EPOCH = datetime(2011, 1, 1)


def _listing_age_days(product: dict[str, Any]) -> int | None:
    """Approximate how long Keepa has tracked the listing, in days (newness)."""
    ts = product.get("trackingSince")
    if ts is None:
        return None
    try:
        if isinstance(ts, datetime):
            dt = ts
        elif isinstance(ts, (int, float)):
            dt = _KEEPA_EPOCH + timedelta(minutes=int(ts))
        else:
            dt = _to_datetime(ts)
        age = (datetime.utcnow() - dt).days
        return age if age >= 0 else None
    except Exception:
        return None


def discovery_signals(
    product: dict[str, Any], record: dict[str, Any], stats_days: int = 90
) -> dict[str, Any]:
    """Tag a record as Bestseller / Rising / New and score its momentum.

    A product can carry several tags. ``momentum_score`` is a coarse rank for
    "most interesting to source first" — used to order the buyer report.
    """
    m = record.get("metrics") or {}
    rank = m.get("sales_rank") or {}
    demand = m.get("demand") or {}
    current_rank = rank.get("current")
    monthly = demand.get("monthly_sold_estimate")
    trend_pct = rank.get("trend_pct")
    drops30 = rank.get("drops_30d")
    review_velocity = demand.get("review_velocity_per_month")
    age_days = _listing_age_days(product)

    tags: list[str] = []
    is_new = age_days is not None and age_days <= NEW_LISTING_DAYS
    if is_new:
        tags.append("New")
    if (trend_pct or 0) >= RISING_TREND_PCT or (drops30 or 0) >= RISING_DROPS_30:
        tags.append("Rising")
    if (current_rank is not None and current_rank <= BESTSELLER_RANK_MAX) or (
        monthly or 0
    ) >= BESTSELLER_MONTHLY:
        tags.append("Bestseller")

    score = 0.0
    score += max(0.0, trend_pct or 0.0)          # improving rank
    score += (drops30 or 0) * 2.0                 # active selling
    score += min(review_velocity or 0.0, 50.0)    # review growth (capped)
    if is_new:
        score += 20.0                             # newness boost
    if monthly:
        score += min(monthly / 50.0, 20.0)        # raw volume (capped)

    return {
        "tags": tags or ["Steady"],
        "is_new": is_new,
        "listing_age_days": age_days,
        "momentum_score": round(score, 1),
    }


def build_record(
    product: dict[str, Any], stats_days: int = 90, domain: str = "US"
) -> dict[str, Any]:
    """Combine overview + metrics + discovery tags into a single record."""
    rec = {
        **product_overview(product, domain=domain),
        "metrics": extract_metrics(product, stats_days=stats_days),
    }
    rec["discovery"] = discovery_signals(product, rec, stats_days=stats_days)
    return rec


# --- Verdict rule thresholds -------------------------------------------------
# Tunable cut-offs for the rule-based verdict. Kept here (not buried inside the
# function) so the "rules" are explicit and editable in one place. These are
# mirrored in CLAUDE.md and SEARCH_GUIDE.md — keep all three in sync when you
# change a number.
VOLATILITY_STABLE_MAX = 0.25     # volatility ≤ this → "stable price" (pro)
VOLATILITY_RISK_MIN = 0.50       # volatility ≥ this → "volatile price" (con)
PRICE_DOWNTREND_RATIO = 0.85     # current < avg×this → downward trend / margin erosion (con)
DROPS30_STRONG = 8               # rank drops/30d ≥ this → strong velocity (pro)
MONTHLY_STRONG = 300             # monthly sold ≥ this → strong velocity (pro)
DROPS30_WEAK = 2                 # rank drops/30d ≤ this (+ low monthly) → weak velocity (con)
MONTHLY_WEAK = 100               # monthly sold < this (+ low drops) → weak velocity (con)
OFFERS_LOW_MAX = 12              # offers ≤ this → moderate competition (pro)
OFFERS_CROWDED_MIN = 25          # offers ≥ this → crowded / price war (con)
RATING_GOOD = 4.2                # rating ≥ this (+ enough reviews) → strong rating (pro)
RATING_GOOD_REVIEWS = 100        # reviews needed to treat the rating as proven
RATING_WEAK = 4.0                # rating < this → "low rating" (con)
RATING_SKIP = 3.8                # rating < this → hard SKIP regardless of other signals
HEAVY_ITEM_G = 2500              # package weight (g) > this → bulky/heavy, pricey FBA (con)


def auto_verdict(record: dict[str, Any]) -> dict[str, Any]:
    """Attach a rule-based verdict to a record (used by unattended auto runs).

    Mirrors DECISION_GUIDANCE so scheduled reports are immediately actionable;
    when Claude is in the loop it produces its own, richer verdicts instead.
    Thresholds are the module-level constants above.
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
        if volatility <= VOLATILITY_STABLE_MAX:
            pros.append(f"stable price (volatility {volatility})")
        elif volatility >= VOLATILITY_RISK_MIN:
            cons.append(f"volatile price (volatility {volatility})")

    # Sustained downward price trend = margin erosion (current well below avg).
    cur_price, avg_price = pricing.get("current"), pricing.get("avg")
    if cur_price is not None and avg_price and cur_price < avg_price * PRICE_DOWNTREND_RATIO:
        cons.append(
            f"downward price trend (now {cur_price} vs avg {avg_price}, margin erosion)"
        )

    drops30 = rank.get("drops_30d")
    monthly = demand.get("monthly_sold_estimate")
    if (drops30 or 0) >= DROPS30_STRONG or (monthly or 0) >= MONTHLY_STRONG:
        pros.append(f"healthy sales velocity (drops30={drops30}, monthly≈{monthly})")
    elif drops30 is not None and drops30 <= DROPS30_WEAK and (monthly or 0) < MONTHLY_WEAK:
        cons.append(f"weak sales velocity (drops30={drops30}, monthly≈{monthly})")

    if comp.get("buy_box_is_amazon"):
        cons.append("Amazon holds the Buy Box")
    if offers is not None:
        if offers <= OFFERS_LOW_MAX:
            pros.append(f"moderate competition ({int(offers)} offers)")
        elif offers >= OFFERS_CROWDED_MIN:
            cons.append(f"crowded listing ({int(offers)} offers)")

    rating = reviews.get("rating_current")
    review_count = reviews.get("review_count_current")
    if rating is not None:
        if rating >= RATING_GOOD and (review_count or 0) >= RATING_GOOD_REVIEWS:
            pros.append(f"strong rating {rating} with {int(review_count)} reviews")
        elif rating < RATING_WEAK:
            cons.append(f"low rating {rating}")

    # Bulky/heavy items carry pricey FBA pick&pack + inbound shipping.
    weight_g = _clean(record.get("package_weight_g"))
    if weight_g is not None and weight_g > HEAVY_ITEM_G:
        cons.append(f"bulky/heavy item ({int(weight_g)} g, pricey FBA/logistics)")

    if len(cons) >= 3 or (rating is not None and rating < RATING_SKIP):
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
    "confidence level, the 2-3 metrics that drove it, the active Amazon link "
    "(every record carries a `url`; in the XLSX the ASIN cell itself links to "
    "the product page), and how well the product satisfies the target customer "
    "need.",
}


# Guidance for the sourcing / discovery flow (what to buy and resell).
DISCOVERY_GUIDANCE = {
    "strategy": "US is the lead market (products surface here first). Use it to "
    "discover candidates to import and resell in DE and AE. Validate demand in "
    "DE via Keepa; Keepa has no data for amazon.ae, so treat AE as a target "
    "sell-side market without its own Keepa metrics.",
    "buckets": {
        "Bestseller": "Already selling well (low sales rank or high monthly sold) "
        "— safest demand, but usually more competition.",
        "Rising": "Sales rank improving over the window (momentum) or many recent "
        "rank drops — catching a trend early.",
        "New": "Recently listed (young tracking history) — first-mover sourcing, "
        "thinner history so verify carefully.",
    },
    "price_band": "Default sourcing band is $20–500 (we can import anything).",
    "recommended_output": "Hand the buyer a report where each product shows its "
    "bucket(s), momentum, key demand metrics, a clickable Amazon link, and a "
    "ready Alibaba supplier-search link so they can start sourcing immediately.",
}
