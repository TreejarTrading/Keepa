// Map computed records (Amazon analysis / China sourcing) to ReportItem rows so
// reports stay sliceable by category and verdict without re-parsing the blob.
import type { Prisma } from "@prisma/client";
import type { AnalysisRecord } from "./analysis";
import type { SourcingRow } from "./sourcing";

function intOrNull(v: unknown): number | null {
  if (v == null || typeof v !== "number" || !Number.isFinite(v)) return null;
  return Math.trunc(v);
}
function floatOrNull(v: unknown): number | null {
  if (v == null || typeof v !== "number" || !Number.isFinite(v)) return null;
  return v;
}

export function analysisToItem(rec: AnalysisRecord): Prisma.ReportItemCreateWithoutReportInput {
  const fees = rec.metrics.amazon_fees;
  const reviews = rec.metrics.reviews;
  return {
    asin: rec.asin,
    title: rec.title ?? null,
    brand: rec.brand ?? null,
    manufacturer: rec.manufacturer ?? null,
    marketplace: rec.marketplace,
    rootCategory: rec.root_category ?? null,
    categoryPath: rec.category_tree ?? [],
    imageUrl: rec.image ?? null,
    sellPrice: floatOrNull(fees.sell_price_used),
    monthlySold: intOrNull(rec.metrics.demand.monthly_sold_estimate),
    rating: floatOrNull(reviews.rating_current),
    reviewCount: intOrNull(reviews.review_count_current),
    referralPct: floatOrNull(fees.referral_pct),
    fbaFee: floatOrNull(fees.fba_fee),
    verdict: rec.verdict ?? null,
    confidence: rec.confidence ?? null,
    rationale: rec.rationale ?? null,
    data: rec as unknown as Prisma.InputJsonValue,
  };
}

export function sourcingToItem(row: SourcingRow): Prisma.ReportItemCreateWithoutReportInput {
  return {
    asin: (row.asin as string) ?? "—",
    title: (row.title as string) ?? null,
    brand: (row.brand as string) ?? null,
    manufacturer: (row.manufacturer as string) ?? null,
    marketplace: (row.marketplace as string) ?? "US",
    rootCategory: null,
    categoryPath: [],
    imageUrl: null,
    sellPrice: floatOrNull(row.amazon_sell_price),
    monthlySold: intOrNull(row.monthly_sold),
    rating: null,
    reviewCount: null,
    referralPct: null,
    fbaFee: null,
    landedCost: floatOrNull((row as any).landed_cost),
    marginPct: floatOrNull((row as any).margin_pct),
    roiPct: floatOrNull((row as any).roi_pct),
    verdict: (row.verdict as string) ?? null,
    rationale: ((row as any).verdict_reason as string) ?? null,
    data: row as unknown as Prisma.InputJsonValue,
  };
}
