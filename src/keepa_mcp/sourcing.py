"""Supplier-sourcing links for the buyer report.

The purchasing team works from the report directly, so every product carries a
ready-to-click **Alibaba search link**. We don't scrape Alibaba here (that's the
optional Apify path in ``niche_analyzer``); we just build the search URL a buyer
would land on, derived from concise keywords pulled out of the Amazon title.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

ALIBABA_SEARCH = "https://www.alibaba.com/trade/search?SearchText={q}"

# Marketing / packaging / unit noise that hurts a supplier search. English-first
# (most source titles are US), but harmless on DE/FR titles too.
_STOPWORDS = {
    "the", "a", "an", "for", "with", "and", "of", "to", "in", "by", "or",
    "new", "premium", "pack", "set", "kit", "pcs", "pc", "piece", "pieces",
    "count", "ct", "pack of", "bundle", "size", "large", "small", "medium",
    "xl", "xxl", "inch", "inches", "cm", "mm", "ml", "oz", "lb", "lbs", "kg",
    "g", "pro", "plus", "best", "top", "quality", "high", "super", "ultra",
    "official", "genuine", "original", "brand", "color", "colour",
}


def keyword_phrase(title: str | None, brand: str | None = None, max_words: int = 4) -> str:
    """Distil an Amazon title into a short, supplier-searchable phrase.

    Drops the brand, pure numbers, units and marketing filler, then keeps the
    first ``max_words`` meaningful tokens (which tend to be the product noun +
    qualifiers, e.g. "stainless steel garlic press").
    """
    if not title:
        return (brand or "").strip()

    text = title.lower()
    if brand:
        for token in re.split(r"\s+", brand.lower().strip()):
            if token:
                text = re.sub(rf"\b{re.escape(token)}\b", " ", text)

    words = re.findall(r"\w+", text, flags=re.UNICODE)
    out: list[str] = []
    for w in words:
        if w in _STOPWORDS or len(w) <= 1 or w.isdigit():
            continue
        out.append(w)
        if len(out) >= max_words:
            break
    return " ".join(out) or title.strip()


def alibaba_search_url(text: str | None) -> str | None:
    """Build an Alibaba supplier-search URL for ``text`` (None if empty)."""
    q = quote_plus((text or "").strip())
    return ALIBABA_SEARCH.format(q=q) if q else None


def sourcing_links(
    title: str | None,
    brand: str | None = None,
    category: str | None = None,
) -> dict[str, str | None]:
    """Return the Alibaba links a buyer needs for one product.

    - ``alibaba_keywords``: the search phrase shown in the report cell;
    - ``alibaba_url``: product-level supplier search (specific);
    - ``alibaba_category_url``: broader search by the product's category name.
    """
    keywords = keyword_phrase(title, brand)
    return {
        "alibaba_keywords": keywords,
        "alibaba_url": alibaba_search_url(keywords),
        "alibaba_category_url": alibaba_search_url(category) if category else None,
    }
