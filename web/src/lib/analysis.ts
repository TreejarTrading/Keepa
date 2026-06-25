// Distil a raw Keepa product (with server-computed `stats`) into the same
// decision-oriented record the Python `analysis.py` produces: pricing window
// stats, Amazon fees (referral + FBA), sales velocity, competition, reviews,
// plus a rule-based BUY/WATCH/SKIP auto-verdict.

import { estimateReferralPct, MIN_REFERRAL_FEE } from "./fees";
import {
  KEEPA_IDX,
  type KeepaProduct,
  amazonUrl,
  keepaUrl,
  normalizeDomain,
} from "./keepa";

export type PriceStat = {
  current: number | null;
  min: number | null;
  max: number | null;
  avg: number | null;
  volatility: number | null;
};

export type AnalysisRecord = ReturnType<typeof buildRecord>;

function clean(v: unknown): number | null {
  if (v == null) return null;
  const f = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(f) || f < 0) return null;
  return f;
}

function roundN(v: number | null, digits = 2): number | null {
  if (v == null) return null;
  const p = 10 ** digits;
  return Math.round(v * p) / p;
}

/** Read a value from a Keepa stats sub-array (`current`/`avg`) at an index. */
function statValue(arr: unknown, idx: number): number | null {
  if (!Array.isArray(arr)) return null;
  return clean(arr[idx]);
}

/** Keepa stats `min`/`max` entries are usually `[keepaTime, value]` pairs. */
function statExtreme(arr: unknown, idx: number): number | null {
  if (!Array.isArray(arr)) return null;
  const entry = arr[idx];
  if (Array.isArray(entry)) return clean(entry[entry.length - 1]);
  return clean(entry);
}

function centsStat(stats: any, idx: number): PriceStat {
  const toUnit = (v: number | null) => (v == null ? null : roundN(v / 100, 2));
  const current = toUnit(statValue(stats?.current, idx));
  const avg = toUnit(statValue(stats?.avg, idx));
  const min = toUnit(statExtreme(stats?.min, idx));
  const max = toUnit(statExtreme(stats?.max, idx));
  let volatility: number | null = null;
  if (min != null && max != null && avg) volatility = roundN((max - min) / avg, 3);
  return { current, min, max, avg, volatility };
}

function amazonFees(product: KeepaProduct, pricing: Record<string, PriceStat>) {
  let sell: number | null = null;
  for (const key of ["buy_box", "new", "amazon"]) {
    const cur = pricing[key]?.current ?? null;
    if (cur != null) { sell = cur; break; }
  }

  // Referral %: prefer Keepa's real per-product value, else estimate by category.
  let referralPct = keepaReferralPct(product);
  let referralSource = "keepa";
  if (referralPct == null) {
    const cats = (product.categoryTree || [])
      .map((c: any) => c?.name)
      .filter((n: any): n is string => typeof n === "string");
    referralPct = estimateReferralPct(cats, product.productGroup, sell);
    referralSource = "category";
  }

  const fbaFee = fbaPickPackFee(product);
  const referralFee =
    sell != null && referralPct != null
      ? roundN(Math.max(sell * referralPct, MIN_REFERRAL_FEE), 2)
      : null;
  const totalFees =
    referralFee != null || fbaFee != null
      ? roundN((referralFee ?? 0) + (fbaFee ?? 0), 2)
      : null;
  const net = sell != null && totalFees != null ? roundN(sell - totalFees, 2) : null;

  return {
    sell_price_used: sell,
    referral_pct: referralPct,
    referral_pct_source: referralSource,
    referral_fee: referralFee,
    fba_fee: fbaFee,
    total_fees: totalFees,
    net_proceeds: net,
  };
}

function keepaReferralPct(product: KeepaProduct): number | null {
  for (const key of ["referralFeePercent", "referralFeePercentage", "referralFee"]) {
    const pct = clean(product[key]);
    if (pct != null) return roundN(pct > 1 ? pct / 100 : pct, 4);
  }
  return null;
}

function fbaPickPackFee(product: KeepaProduct): number | null {
  const fees = product.fbaFees;
  if (fees && typeof fees === "object") {
    const cents = clean(fees.pickAndPackFee);
    if (cents != null) return cents >= 50 ? roundN(cents / 100, 2) : roundN(cents, 2);
  }
  return null;
}

function imageUrl(product: KeepaProduct): string | null {
  const first = String(product.imagesCSV || "").split(",")[0];
  return first ? `https://m.media-amazon.com/images/I/${first}` : null;
}

export function extractMetrics(product: KeepaProduct, statsDays = 90) {
  const stats = product.stats || {};

  const pricing = {
    amazon: centsStat(stats, KEEPA_IDX.AMAZON),
    new: centsStat(stats, KEEPA_IDX.NEW),
    used: centsStat(stats, KEEPA_IDX.USED),
    buy_box: centsStat(stats, KEEPA_IDX.BUY_BOX_SHIPPING),
    new_fba: centsStat(stats, KEEPA_IDX.NEW_FBA),
  };

  const rankCurrent = statValue(stats.current, KEEPA_IDX.SALES);
  const sales_rank = {
    current: rankCurrent,
    min: statExtreme(stats.min, KEEPA_IDX.SALES),
    max: statExtreme(stats.max, KEEPA_IDX.SALES),
    avg: statValue(stats.avg, KEEPA_IDX.SALES),
    drops_30d: clean(stats.salesRankDrops30) ?? clean(product.salesRankDrops30),
    drops_90d: clean(stats.salesRankDrops90) ?? clean(product.salesRankDrops90),
  };

  const offerCount = statValue(stats.current, KEEPA_IDX.COUNT_NEW);
  const competition = {
    offer_count: offerCount,
    buy_box_seller_id: product.buyBoxSellerId ?? null,
    buy_box_is_amazon: product.buyBoxIsAmazon ?? null,
  };

  const ratingCurrent = statValue(stats.current, KEEPA_IDX.RATING);
  const ratingAvg = statValue(stats.avg, KEEPA_IDX.RATING);
  const reviewCurrent = statValue(stats.current, KEEPA_IDX.COUNT_REVIEWS);
  const reviewMin = statExtreme(stats.min, KEEPA_IDX.COUNT_REVIEWS);
  const reviews = {
    rating_current: ratingCurrent == null ? null : roundN(ratingCurrent / 10, 1),
    rating_avg: ratingAvg == null ? null : roundN(ratingAvg / 10, 1),
    review_count_current: reviewCurrent,
  };
  let reviewVelocity: number | null = null;
  if (reviewCurrent != null && reviewMin != null) {
    reviewVelocity = roundN(((reviewCurrent - reviewMin) / Math.max(statsDays, 1)) * 30, 1);
  }

  return {
    pricing,
    amazon_fees: amazonFees(product, pricing),
    sales_rank,
    competition,
    demand: {
      monthly_sold_estimate: clean(product.monthlySold) ?? null,
      review_velocity_per_month: reviewVelocity,
    },
    reviews,
  };
}

export function buildRecord(
  product: KeepaProduct,
  opts: { domain?: string; statsDays?: number } = {},
) {
  const domain = normalizeDomain(opts.domain);
  const statsDays = opts.statsDays ?? 90;
  const categoryTree = (product.categoryTree || [])
    .map((c: any) => (c && typeof c === "object" ? c.name : null))
    .filter((n: any): n is string => typeof n === "string");

  const overview = {
    marketplace: domain,
    asin: product.asin as string,
    title: (product.title as string) ?? null,
    brand: (product.brand || product.manufacturer) ?? null,
    manufacturer: (product.manufacturer as string) ?? null,
    product_group: (product.productGroup as string) ?? null,
    category_tree: categoryTree,
    root_category: categoryTree[0] ?? null,
    features: (product.features as string[]) || [],
    description: (product.description as string) ?? null,
    number_of_items: product.numberOfItems ?? null,
    package_weight_g: product.packageWeight ?? null,
    package_dimensions: {
      length: product.packageLength ?? null,
      width: product.packageWidth ?? null,
      height: product.packageHeight ?? null,
    },
    variation_count: Array.isArray(product.variations) ? product.variations.length : 0,
    fba_pick_pack_fee: fbaPickPackFee(product),
    referral_fee_pct: keepaReferralPct(product),
    image: imageUrl(product),
    url: product.asin ? amazonUrl(product.asin, domain) : null,
    keepa_url: product.asin ? keepaUrl(product.asin, domain) : null,
  };

  const record = { ...overview, metrics: extractMetrics(product, statsDays) };
  return autoVerdict(record);
}

/** Rule-based BUY / WATCH / SKIP verdict (ported from analysis.auto_verdict). */
export function autoVerdict<T extends { metrics: ReturnType<typeof extractMetrics> }>(record: T) {
  const m = record.metrics;
  const pricing = m.pricing.new;
  const rank = m.sales_rank;
  const comp = m.competition;
  const offers = comp.offer_count;
  const reviews = m.reviews;
  const demand = m.demand;

  const pros: string[] = [];
  const cons: string[] = [];

  const volatility = pricing.volatility;
  if (volatility != null) {
    if (volatility <= 0.25) pros.push(`stable price (volatility ${volatility})`);
    else if (volatility >= 0.5) cons.push(`volatile price (volatility ${volatility})`);
  }

  const drops30 = rank.drops_30d;
  const monthly = demand.monthly_sold_estimate;
  if ((drops30 || 0) >= 8 || (monthly || 0) >= 300) {
    pros.push(`healthy sales velocity (drops30=${drops30}, monthly≈${monthly})`);
  } else if (drops30 != null && drops30 <= 2 && (monthly || 0) < 100) {
    cons.push(`weak sales velocity (drops30=${drops30}, monthly≈${monthly})`);
  }

  if (comp.buy_box_is_amazon) cons.push("Amazon holds the Buy Box");
  if (offers != null) {
    if (offers <= 12) pros.push(`moderate competition (${Math.trunc(offers)} offers)`);
    else if (offers >= 25) cons.push(`crowded listing (${Math.trunc(offers)} offers)`);
  }

  const rating = reviews.rating_current;
  const reviewCount = reviews.review_count_current;
  if (rating != null) {
    if (rating >= 4.2 && (reviewCount || 0) >= 100) {
      pros.push(`strong rating ${rating} with ${Math.trunc(reviewCount || 0)} reviews`);
    } else if (rating < 4.0) {
      cons.push(`low rating ${rating}`);
    }
  }

  let verdict: "BUY" | "WATCH" | "SKIP";
  if (cons.length >= 3 || (rating != null && rating < 3.8)) verdict = "SKIP";
  else if (pros.length >= 3 && cons.length <= 1) verdict = "BUY";
  else verdict = "WATCH";

  const confidence =
    pros.length + cons.length >= 4 ? "high" : pros.length || cons.length ? "medium" : "low";
  const rationale =
    [...pros.map((p) => "+ " + p), ...cons.map((c) => "- " + c)].join("; ") || "insufficient data";

  return { ...record, verdict, confidence, rationale };
}
