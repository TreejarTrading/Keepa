/**
 * Amazon referral-fee estimation by category.
 *
 * Amazon's referral fee is **not** a flat 15% — it depends on the product
 * category (consumer electronics ~8%, apparel ~17%, jewelry up to 20%, most
 * other categories 15%). Keepa returns the real per-product referral percent for
 * many ASINs and that is always used first (see `_referral_pct` in the Python
 * `analysis` module). This module is the fallback: it maps the Amazon category to
 * its published US referral rate so the estimate is **category-correct** instead
 * of a blind 15%.
 *
 * Rates approximate Amazon's US schedule (incl. the common price tiers) and are
 * easy to adjust in one place. An explicit per-item `amazon_referral_pct` always
 * wins over both Keepa and this estimate.
 *
 * Faithful TypeScript port of `src/keepa_mcp/fees.py`.
 */

/** Used only when the category cannot be matched at all. */
export const DEFAULT_REFERRAL_PCT = 0.15;

/**
 * Amazon charges a minimum referral fee per item (commonly $0.30).
 *
 * In the Python code this constant lives in `analysis._MIN_REFERRAL_FEE`; it is
 * exported here so the referral-fee math can stay together in one place.
 */
export const MIN_REFERRAL_FEE = 0.3;

/** A single flat rule: a list of keywords and the referral fraction they map to. */
export type FlatRule = {
  readonly keywords: readonly string[];
  readonly pct: number;
};

/**
 * Flat keyword -> referral fraction, matched against the category tree +
 * productGroup (lowercased). First hit wins, so list specific terms first.
 */
export const FLAT_RULES: readonly FlatRule[] = [
  { keywords: ["amazon device", "echo ", "fire tv", "kindle accessor"], pct: 0.45 },
  { keywords: ["fine art"], pct: 0.2 },
  { keywords: ["clothing", "apparel", "fashion"], pct: 0.17 },
  { keywords: ["shoe", "handbag", "sunglass", "luggage", "backpack"], pct: 0.15 },
  {
    keywords: ["personal computer", "desktop computer", "laptop", "notebook computer"],
    pct: 0.06,
  },
  {
    keywords: [
      "consumer electronic",
      "electronics",
      "camera",
      "photo",
      "cell phone",
      "smartphone",
      "headphone",
      "earbud",
      "computer",
      "tablet",
      "television",
      " tv ",
      "monitor",
      "video game console",
      "game console",
      "speaker",
    ],
    pct: 0.08,
  },
  {
    keywords: [
      "major appliance",
      "large appliance",
      "refrigerator",
      "freezer",
      "washer",
      "dryer",
      "dishwasher",
    ],
    pct: 0.08,
  },
  { keywords: ["automotive", "powersport", "tire", "motorcycle"], pct: 0.12 },
  { keywords: ["industrial", "scientific"], pct: 0.12 },
  { keywords: ["power tool", "base equipment"], pct: 0.12 },
  { keywords: ["musical instrument"], pct: 0.15 },
];

/**
 * Estimate the Amazon referral fraction for a product's category.
 *
 * `categoryTree` is the list of Amazon category names (root → leaf);
 * `productGroup` is Keepa's productGroup. `price` selects the right tier for
 * price-tiered categories. Returns a fraction (e.g. `0.08` = 8%).
 */
export function estimateReferralPct(
  categoryTree: string[] | null | undefined,
  productGroup: string | null | undefined = null,
  price: number | null | undefined = null,
): number {
  let text = [...(categoryTree ?? []), productGroup ?? ""].join(" ").toLowerCase();
  const p = price || 0.0;

  // Neutralise Amazon's combined department name so apparel products are not
  // misread as jewelry (the breadcrumb literally says "Clothing, Shoes &
  // Jewelry"); a real jewelry sub-node still leaves "jewelry" in the text.
  for (const combined of [
    "clothing, shoes & jewelry",
    "clothing, shoes and jewelry",
    "clothing shoes & jewelry",
  ]) {
    text = text.split(combined).join("clothing shoes");
  }

  // Price-tiered categories — apply the tier that fits the price (a close,
  // documented approximation of Amazon's split-tier schedule).
  if (text.includes("jewelry") || text.includes("jewellery")) {
    return p <= 250 ? 0.2 : 0.05;
  }
  if (text.includes("watch")) {
    return p <= 1500 ? 0.16 : 0.03;
  }
  if (text.includes("furniture") || text.includes("mattress")) {
    return p <= 200 ? 0.15 : 0.1;
  }
  if (text.includes("electronics accessor") || text.includes("electronic accessor")) {
    return p <= 100 ? 0.15 : 0.08;
  }
  if (text.includes("grocery") || text.includes("gourmet food")) {
    return p <= 15 ? 0.08 : 0.15;
  }
  if (
    ["health", "household", "beauty", "personal care", "cosmetic", "baby"].some((k) =>
      text.includes(k),
    )
  ) {
    return p <= 10 ? 0.08 : 0.15;
  }

  for (const { keywords, pct } of FLAT_RULES) {
    if (keywords.some((k) => text.includes(k))) {
      return pct;
    }
  }
  return DEFAULT_REFERRAL_PCT;
}
