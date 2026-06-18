"""China-side sourcing: match Amazon products to Chinese-marketplace supply.

This module is the "now find it cheaper in China" half of the workflow. Given
a product that looks good on the demand side (found via Keepa, or supplied
from the user's own Amazon market data), it produces everything Claude needs
to go and search the Chinese marketplaces by hand — 1688, Alibaba.com,
Taobao/Tmall, Pinduoduo — and then scores the supplier offers Claude brings
back.

There is **no paid marketplace API** in the loop: the browsing is done by
Claude itself (WebSearch / WebFetch / image search). So, mirroring how the
Keepa side works (the server returns data + guidance, Claude reasons, the
server persists a report), this module provides:

  * :func:`build_search_plan`  — per-platform search URLs + queries to open;
  * :func:`score_match`        — EXACT (~100%) vs SIMILAR classification;
  * :func:`estimate_margin`    — rough China-cost vs Amazon-price economics;
  * :func:`rank_offers`        — best EXACT / best SIMILAR per product;
  * :data:`SOURCING_GUIDANCE`  — how Claude should browse and what to capture;
  * :func:`fetch_page`         — best-effort HTTP fallback when Claude's own
    WebFetch is blocked (Chinese sites are bot-hostile, so this often fails).

Everything except :func:`fetch_page` is offline and deterministic; nothing
here requires the network.
"""

from __future__ import annotations

import difflib
import re
from typing import Any
from urllib.parse import quote

from . import config

# --- Marketplace catalogue ---------------------------------------------------
# ``needs_chinese`` marks platforms whose on-site search works far better with a
# Chinese-language query; Claude should translate the product name first (and
# pass it as ``query_zh``). Alibaba.com is the English-language B2B exception.
_PLATFORMS: dict[str, dict[str, Any]] = {
    "1688": {
        "name": "1688.com",
        "kind": "B2B wholesale (China domestic)",
        "currency": "CNY",
        "b2b": True,
        "needs_chinese": True,
        "search_url": "https://s.1688.com/selloffer/offer_search.htm?keywords={q}",
        # 拍立淘 / image search (needs an uploaded photo).
        "image_search_url": "https://s.1688.com/youyuan/index.htm",
    },
    "alibaba": {
        "name": "Alibaba.com",
        "kind": "B2B export (global, English)",
        "currency": "USD",
        "b2b": True,
        "needs_chinese": False,
        "search_url": "https://www.alibaba.com/trade/search?SearchText={q}",
        "image_search_url": "https://www.alibaba.com/picture/search.htm",
    },
    "taobao": {
        "name": "Taobao",
        "kind": "retail (China)",
        "currency": "CNY",
        "b2b": False,
        "needs_chinese": True,
        "search_url": "https://s.taobao.com/search?q={q}",
        "image_search_url": "https://www.taobao.com/",  # image search via the app (拍立淘)
    },
    "tmall": {
        "name": "Tmall",
        "kind": "retail brand store (China)",
        "currency": "CNY",
        "b2b": False,
        "needs_chinese": True,
        "search_url": "https://list.tmall.com/search_product.htm?q={q}",
        "image_search_url": None,
    },
    "pinduoduo": {
        "name": "Pinduoduo",
        "kind": "retail / group-buy (China)",
        "currency": "CNY",
        "b2b": False,
        "needs_chinese": True,
        "search_url": "https://mobile.yangkeduo.com/search_result.html?search_key={q}",
        "image_search_url": None,
    },
}

DEFAULT_PLATFORM_ORDER = ["1688", "alibaba", "taobao", "tmall", "pinduoduo"]

# Friendly aliases -> canonical platform keys.
_PLATFORM_ALIASES = {
    "1688": "1688", "alibaba": "alibaba", "ali": "alibaba", "alibaba.com": "alibaba",
    "taobao": "taobao", "tao": "taobao", "tmall": "tmall", "tmall.com": "tmall",
    "pinduoduo": "pinduoduo", "pdd": "pinduoduo", "yangkeduo": "pinduoduo",
}

# Keepa domain code -> the currency its prices are quoted in (for margin math).
MARKET_CURRENCY = {
    "US": "USD", "GB": "GBP", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR",
    "JP": "JPY", "CA": "CAD", "IN": "INR", "MX": "MXN", "BR": "BRL",
}

# Currency-symbol / alias normalisation for FX lookups.
_CURRENCY_ALIASES = {
    "US$": "USD", "$": "USD", "USD": "USD",
    "¥": "CNY", "RMB": "CNY", "元": "CNY", "YUAN": "CNY", "CNY": "CNY",
    "€": "EUR", "£": "GBP",
}


def normalize_platforms(platforms: list[str] | None = None) -> list[str]:
    """Return a validated, de-duplicated, ordered list of platform keys."""
    raw = platforms or config.CHINA_PLATFORMS or DEFAULT_PLATFORM_ORDER
    out: list[str] = []
    for item in raw:
        key = _PLATFORM_ALIASES.get(str(item).strip().lower())
        if key and key in _PLATFORMS and key not in out:
            out.append(key)
    return out or list(DEFAULT_PLATFORM_ORDER)


# --- Query / search-plan building -------------------------------------------
def _source_query(product: dict[str, Any]) -> str:
    """Best source-language (usually English) query string for a product."""
    explicit = product.get("query") or product.get("keywords")
    if isinstance(explicit, (list, tuple)):
        explicit = " ".join(str(x) for x in explicit if x)
    if explicit:
        return str(explicit).strip()
    parts = [product.get("brand"), product.get("title")]
    joined = " ".join(str(p) for p in parts if p).strip()
    return joined or str(product.get("title") or "").strip()


def _product_label(product: dict[str, Any]) -> str:
    """Short human label for a product, e.g. ``"Mini Fridge 4L (B0ABC...)"``."""
    asin = product.get("asin")
    title = product.get("title") or product.get("query") or "—"
    title = str(title).strip() or "—"
    return f"{title} ({asin})" if asin else title


def build_search_plan(
    product: dict[str, Any], platforms: list[str] | None = None
) -> dict[str, Any]:
    """Build per-platform search URLs + queries for one product.

    ``product`` is a free-form descriptor; recognised keys are ``title``,
    ``brand``, ``keywords`` (str or list), ``query`` (explicit search string),
    ``query_zh`` (a Chinese translation for the CN-only platforms),
    ``image_url`` (the Amazon product photo, for image search), ``asin``,
    ``reference_price`` and ``currency`` (the Amazon price to compare against).
    """
    keys = normalize_platforms(platforms)
    src_q = _source_query(product)
    zh_q = str(product.get("query_zh") or "").strip()
    image_url = product.get("image_url") or product.get("image")

    plan: list[dict[str, Any]] = []
    for key in keys:
        meta = _PLATFORMS[key]
        if meta["needs_chinese"]:
            query = zh_q or src_q
        else:
            query = src_q
        url = meta["search_url"].format(q=quote(query)) if query else None

        notes: list[str] = []
        if meta["needs_chinese"] and not zh_q:
            notes.append("translate the product name to Chinese for best results (pass query_zh)")
        if image_url and meta.get("image_search_url"):
            notes.append("for a 100% match, search by the Amazon product photo (image_url)")

        plan.append(
            {
                "platform": key,
                "name": meta["name"],
                "kind": meta["kind"],
                "b2b": meta["b2b"],
                "currency": meta["currency"],
                "query_used": query or None,
                "query_is_chinese": bool(meta["needs_chinese"] and zh_q),
                "search_url": url,
                "image_search_url": meta.get("image_search_url"),
                "notes": "; ".join(notes) or None,
            }
        )

    return {
        "product": _product_label(product),
        "asin": product.get("asin"),
        "image_url": image_url,
        "reference_price": product.get("reference_price"),
        "reference_currency": product.get("currency") or "USD",
        "source_query": src_q or None,
        "query_zh": zh_q or None,
        "needs_translation": bool(zh_q) is False
        and any(_PLATFORMS[k]["needs_chinese"] for k in keys),
        "platforms": plan,
    }


# --- Matching ----------------------------------------------------------------
# Keep latin letters, digits and CJK unified ideographs as match tokens.
_TOKEN_RE = re.compile("[a-z0-9一-鿿]+")


def _norm_tokens(text: Any) -> list[str]:
    if not text:
        return []
    return _TOKEN_RE.findall(str(text).lower())


def _text_similarity(a: Any, b: Any) -> float:
    """0-1 similarity combining sequence ratio and token-set overlap."""
    ta, tb = _norm_tokens(a), _norm_tokens(b)
    if not ta or not tb:
        return 0.0
    seq = difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    sa, sb = set(ta), set(tb)
    jaccard = len(sa & sb) / len(sa | sb)
    return round(max(seq, jaccard), 3)


def _keyword_coverage(keywords: Any, offer_text: Any) -> float | None:
    """Fraction of the product's keywords present in the offer title."""
    if isinstance(keywords, str):
        kw = _norm_tokens(keywords)
    elif isinstance(keywords, (list, tuple)):
        kw = [tok for item in keywords for tok in _norm_tokens(item)]
    else:
        kw = []
    kw_set = set(kw)
    if not kw_set:
        return None
    offer_tokens = set(_norm_tokens(offer_text))
    hits = sum(1 for k in kw_set if k in offer_tokens)
    return round(hits / len(kw_set), 3)


def score_match(
    product: dict[str, Any], offer: dict[str, Any], *, exact_threshold: float | None = None
) -> dict[str, Any]:
    """Classify a China ``offer`` against a ``product`` as EXACT or SIMILAR.

    ``offer`` recognised keys: ``title`` (listing title, any language),
    ``title_en`` (an English translation, improves text matching),
    ``brand``, ``image_confirmed`` (set True when you visually verified it is
    the same physical product), ``image_score`` (0-1 confidence).

    EXACT means ~100% the same product: either image-confirmed, or a very high
    text/spec similarity. Otherwise the offer is SIMILAR.
    """
    threshold = config.CHINA_EXACT_THRESHOLD if exact_threshold is None else exact_threshold
    prod_title = product.get("title") or product.get("query") or ""
    offer_title = offer.get("title_en") or offer.get("title") or ""

    signals: list[str] = []
    text_sim = _text_similarity(prod_title, offer_title)
    signals.append(f"title similarity {text_sim}")

    coverage = _keyword_coverage(product.get("keywords") or prod_title, offer_title)
    if coverage is not None:
        signals.append(f"keyword coverage {coverage}")

    base = text_sim if coverage is None else max(text_sim, coverage)

    brand = str(product.get("brand") or "").strip().lower()
    haystack = f"{offer_title} {offer.get('brand') or ''}".lower()
    if brand and brand in haystack:
        base = min(1.0, base + 0.1)
        signals.append("brand match")

    image_confirmed = bool(offer.get("image_confirmed"))
    image_score = offer.get("image_score")
    if image_confirmed:
        isc = float(image_score) if isinstance(image_score, (int, float)) else 0.95
        score = max(base, isc)
        signals.append(f"image-confirmed ({isc:.2f})")
    else:
        score = base

    score = round(min(1.0, max(0.0, score)), 3)
    is_exact = (
        image_confirmed and (image_score is None or float(image_score) >= 0.85)
    ) or score >= threshold

    return {
        "match_type": "EXACT" if is_exact else "SIMILAR",
        "match_score": score,
        "image_confirmed": image_confirmed,
        "match_signals": signals,
    }


# --- Economics ---------------------------------------------------------------
def to_usd(price: Any, currency: str | None) -> float | None:
    """Convert a price in ``currency`` to USD using the configured FX map.

    Unlabelled prices default to CNY (most Chinese platforms quote yuan); set
    the offer's ``currency`` to ``"USD"`` for Alibaba.com offers.
    """
    if price is None:
        return None
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    raw = str(currency or "").strip().upper()
    code = _CURRENCY_ALIASES.get(raw, raw)
    rate = config.CHINA_FX_TO_USD.get(code)
    if rate is None:
        rate = config.CHINA_FX_TO_USD["CNY"]  # sensible default for China platforms
    return round(value * rate, 2)


def estimate_margin(
    offer: dict[str, Any],
    *,
    reference_price: Any,
    reference_currency: str = "USD",
    freight_pct: float | None = None,
    extra_cost_usd: float = 0.0,
) -> dict[str, Any]:
    """Rough landed-cost & margin of a China offer vs the Amazon reference price.

    These are estimates: real decisions still need actual freight, duties and
    marketplace fees. ``freight_pct`` is added on top of the unit cost.
    """
    freight = config.CHINA_FREIGHT_PCT if freight_pct is None else float(freight_pct)
    unit_usd = to_usd(offer.get("unit_price"), offer.get("currency"))
    ref_usd = to_usd(reference_price, reference_currency) if reference_price is not None else None

    out: dict[str, Any] = {
        "unit_price_usd": unit_usd,
        "landed_cost_usd": None,
        "reference_price_usd": ref_usd,
        "margin_abs_usd": None,
        "margin_pct": None,
    }
    if unit_usd is None:
        return out
    landed = round(unit_usd * (1 + freight) + float(extra_cost_usd or 0), 2)
    out["landed_cost_usd"] = landed
    if ref_usd:
        out["margin_abs_usd"] = round(ref_usd - landed, 2)
        out["margin_pct"] = round((ref_usd - landed) / ref_usd, 3)
    return out


# --- Ranking / aggregation ---------------------------------------------------
def _sort_key(offer: dict[str, Any]):
    landed = offer.get("landed_cost_usd")
    return (
        0 if offer.get("match_type") == "EXACT" else 1,  # EXACT first
        -float(offer.get("match_score") or 0),           # then best match
        landed if landed is not None else float("inf"),  # then cheapest landed
    )


def _summarize(product_fields: dict[str, Any], offers: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(offers, key=_sort_key)
    exact = [o for o in ordered if o.get("match_type") == "EXACT"]
    similar = [o for o in ordered if o.get("match_type") != "EXACT"]
    return {
        **product_fields,
        "offer_count": len(ordered),
        "exact_count": len(exact),
        "similar_count": len(similar),
        "best_exact": exact[0] if exact else None,
        "best_similar": similar[0] if similar else None,
        "offers": ordered,
    }


def rank_offers(
    product: dict[str, Any],
    offers: list[dict[str, Any]] | None,
    *,
    freight_pct: float | None = None,
    extra_cost_usd: float = 0.0,
) -> dict[str, Any]:
    """Score, cost out and rank all China offers found for one product.

    Returns the product label plus the offers enriched with match
    classification and margin estimates, sorted EXACT-first then by match
    score then by landed cost, with the best EXACT and best SIMILAR surfaced.
    """
    ref = product.get("reference_price")
    ref_cur = product.get("currency") or "USD"
    scored: list[dict[str, Any]] = []
    for off in offers or []:
        if not isinstance(off, dict):
            continue
        match = score_match(product, off)
        econ = estimate_margin(
            off,
            reference_price=ref,
            reference_currency=ref_cur,
            freight_pct=freight_pct,
            extra_cost_usd=extra_cost_usd,
        )
        scored.append({**off, **match, **econ})

    product_fields = {
        "product": _product_label(product),
        "asin": product.get("asin"),
        "image_url": product.get("image_url") or product.get("image"),
        "reference_price": ref,
        "reference_currency": ref_cur,
    }
    return _summarize(product_fields, scored)


def ensure_ranked(
    item: Any, *, freight_pct: float | None = None, extra_cost_usd: float = 0.0
) -> dict[str, Any]:
    """Coerce a sourcing ``item`` into a :func:`rank_offers`-shaped result.

    Accepts either an already-ranked result (from ``match_china_offers``) or a
    raw ``{"product": {...}, "offers": [...]}`` item and normalises it so the
    report writer can consume a uniform shape.
    """
    if not isinstance(item, dict):
        return _summarize({"product": "—"}, [])

    offers = item.get("offers") or []
    already_scored = bool(offers) and all(
        isinstance(o, dict) and "match_type" in o for o in offers
    )
    if already_scored and isinstance(item.get("product"), str):
        product_fields = {
            "product": item.get("product"),
            "asin": item.get("asin"),
            "image_url": item.get("image_url"),
            "reference_price": item.get("reference_price"),
            "reference_currency": item.get("reference_currency") or "USD",
        }
        return _summarize(product_fields, offers)

    product = item.get("product")
    if isinstance(product, str):
        product = {"title": product}
    if not isinstance(product, dict):
        product = {}
    for key in ("asin", "title", "reference_price", "currency", "image_url"):
        if key in item and key not in product:
            product[key] = item[key]
    return rank_offers(product, offers, freight_pct=freight_pct, extra_cost_usd=extra_cost_usd)


# --- Best-effort live fetch (fallback only) ----------------------------------
def fetch_page(url: str, *, timeout: float | None = None, max_chars: int = 20000) -> dict[str, Any]:
    """Best-effort HTTP GET of a page, for Claude to parse as a *fallback*.

    The intended browsing path is Claude's own WebSearch / WebFetch / image
    search. Chinese marketplaces are aggressively bot-protected (login walls,
    JS challenges, region blocks, CAPTCHAs), so this frequently returns a
    challenge page or fails outright — that is expected, not a bug.
    """
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    to = config.CHINA_FETCH_TIMEOUT if timeout is None else timeout
    try:
        resp = httpx.get(url, headers=headers, timeout=to, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001 - report instead of crashing
        return {"url": url, "status_code": None, "blocked": True, "text": None,
                "error": f"{type(exc).__name__}: {exc}"}

    text = resp.text or ""
    markers = ("验证码", "captcha", "CAPTCHA", "滑块", "请输入验证码", "Sorry, we just need",
               "login", "登录", "robot")
    blocked = resp.status_code in (401, 403, 412, 429) or any(m in text for m in markers)
    return {
        "url": url,
        "final_url": str(resp.url),
        "status_code": resp.status_code,
        "blocked": blocked,
        "truncated": len(text) > max_chars,
        "text": text[:max_chars],
    }


# Guidance returned alongside sourcing tools so Claude browses consistently.
SOURCING_GUIDANCE = {
    "goal": (
        "Find each Amazon product on the Chinese marketplaces and capture "
        "supplier offer prices. Prefer a 100% identical product (EXACT); if "
        "none exists, capture the closest SIMILAR items."
    ),
    "how_to_search": [
        "Translate the product name + key attributes (size, capacity, material, "
        "model) into Chinese before searching 1688 / Taobao / Tmall / Pinduoduo; "
        "pass it as query_zh. Alibaba.com works in English.",
        "For a 100% match, search by image first: use the Amazon product photo "
        "(image_url) in the platform's image search (1688 拍立淘 / Alibaba image "
        "search) or a reverse-image search, then confirm it is the same product.",
        "If image search is unavailable, search by translated name + brand + "
        "distinguishing specs, and compare photos and dimensions.",
        "Browse with WebSearch / WebFetch (e.g. WebSearch \"site:1688.com <chinese "
        "keywords>\") or open the search_url from the plan. fetch_page is only a "
        "fallback and is often blocked by the sites.",
        "Prioritise the B2B platforms (1688, Alibaba) for wholesale / FOB pricing "
        "and MOQ; use Taobao / Tmall / Pinduoduo as retail price references.",
    ],
    "capture_per_offer": [
        "platform, supplier/shop name, title (and title_en = English translation)",
        "unit_price + currency (CNY on 1688/Taobao/Tmall/Pinduoduo, USD on Alibaba)",
        "moq (minimum order quantity) and url",
        "image_confirmed=true (+ image_score 0-1) when you visually verified the "
        "same physical product",
        "brand if shown",
    ],
    "exact_vs_similar": (
        "Mark an offer EXACT only when it is the same physical product "
        "(image-confirmed or near-identical title/specs). Otherwise SIMILAR. "
        "match_china_offers also scores and classifies each offer for you."
    ),
    "economics": (
        "The server estimates landed cost (unit price -> USD, + freight%) and "
        "margin vs the Amazon reference price. Treat as rough; verify real "
        "shipping, duties and marketplace fees before committing."
    ),
    "recommended_output": (
        "For each product report the best EXACT offer (if any) and the best "
        "SIMILAR offer — platform, supplier, price, MOQ, match score, estimated "
        "margin — then call save_sourcing_report to persist an XLSX."
    ),
}
