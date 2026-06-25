"""Amazon referral-fee estimation by category.

Amazon's referral fee is **not** a flat 15% — it depends on the product
category (consumer electronics ~8%, apparel ~17%, jewelry up to 20%, most other
categories 15%). Keepa returns the real per-product referral percent for many
ASINs and that is always used first (see :func:`analysis._referral_pct`). This
module is the fallback: it maps the Amazon category to its published US referral
rate so the estimate is **category-correct** instead of a blind 15%.

Rates approximate Amazon's US schedule (incl. the common price tiers) and are
easy to adjust in one place. An explicit per-item ``amazon_referral_pct`` always
wins over both Keepa and this estimate.
"""

from __future__ import annotations

# Used only when the category cannot be matched at all.
DEFAULT_REFERRAL_PCT = 0.15

# Flat keyword -> referral fraction, matched against the category tree +
# productGroup (lowercased). First hit wins, so list specific terms first.
_FLAT_RULES: list[tuple[tuple[str, ...], float]] = [
    (("amazon device", "echo ", "fire tv", "kindle accessor"), 0.45),
    (("fine art",), 0.20),
    (("clothing", "apparel", "fashion"), 0.17),
    (("shoe", "handbag", "sunglass", "luggage", "backpack"), 0.15),
    (("personal computer", "desktop computer", "laptop", "notebook computer"), 0.06),
    (("consumer electronic", "electronics", "camera", "photo", "cell phone",
      "smartphone", "headphone", "earbud", "computer", "tablet", "television",
      " tv ", "monitor", "video game console", "game console", "speaker"), 0.08),
    (("major appliance", "large appliance", "refrigerator", "freezer",
      "washer", "dryer", "dishwasher"), 0.08),
    (("automotive", "powersport", "tire", "motorcycle"), 0.12),
    (("industrial", "scientific"), 0.12),
    (("power tool", "base equipment"), 0.12),
    (("musical instrument",), 0.15),
]


def estimate_referral_pct(
    category_tree: list[str] | None,
    product_group: str | None = None,
    price: float | None = None,
) -> float:
    """Estimate the Amazon referral fraction for a product's category.

    ``category_tree`` is the list of Amazon category names (root → leaf);
    ``product_group`` is Keepa's productGroup. ``price`` selects the right tier
    for price-tiered categories. Returns a fraction (e.g. ``0.08`` = 8%).
    """
    text = " ".join([*(category_tree or []), product_group or ""]).lower()
    p = price or 0.0

    # Neutralise Amazon's combined department name so apparel products are not
    # misread as jewelry (the breadcrumb literally says "Clothing, Shoes &
    # Jewelry"); a real jewelry sub-node still leaves "jewelry" in the text.
    for combined in ("clothing, shoes & jewelry", "clothing, shoes and jewelry",
                     "clothing shoes & jewelry"):
        text = text.replace(combined, "clothing shoes")

    # Price-tiered categories — apply the tier that fits the price (a close,
    # documented approximation of Amazon's split-tier schedule).
    if "jewelry" in text or "jewellery" in text:
        return 0.20 if p <= 250 else 0.05
    if "watch" in text:
        return 0.16 if p <= 1500 else 0.03
    if "furniture" in text or "mattress" in text:
        return 0.15 if p <= 200 else 0.10
    if "electronics accessor" in text or "electronic accessor" in text:
        return 0.15 if p <= 100 else 0.08
    if "grocery" in text or "gourmet food" in text:
        return 0.08 if p <= 15 else 0.15
    if any(k in text for k in ("health", "household", "beauty", "personal care",
                               "cosmetic", "baby")):
        return 0.08 if p <= 10 else 0.15

    for keywords, pct in _FLAT_RULES:
        if any(k in text for k in keywords):
            return pct
    return DEFAULT_REFERRAL_PCT
