// Direct Keepa REST client (replaces the Python `keepa` package). Handles the
// Product Finder, product detail (with server-computed `stats`), category search
// and best-seller endpoints. Keepa returns prices in integer cents and rating on
// a 0-50 scale; conversion to dollars/stars happens in `analysis.ts`.

export const DOMAIN_IDS: Record<string, number> = {
  US: 1, GB: 2, DE: 3, FR: 4, JP: 5, CA: 6, IT: 8, ES: 9, IN: 10, MX: 11, BR: 12,
};

export const DOMAIN_TLDS: Record<string, string> = {
  US: "com", GB: "co.uk", DE: "de", FR: "fr", JP: "co.jp", CA: "ca",
  IT: "it", ES: "es", IN: "in", MX: "com.mx", BR: "com.br",
};

const DOMAIN_ALIASES: Record<string, string> = {
  UK: "GB", GB: "GB", US: "US", USA: "US", DE: "DE", FR: "FR", IT: "IT",
  ES: "ES", JP: "JP", CA: "CA", IN: "IN", MX: "MX", BR: "BR",
};

// Keepa csv / stats array indices we read.
export const KEEPA_IDX = {
  AMAZON: 0, NEW: 1, USED: 2, SALES: 3, LISTPRICE: 4, NEW_FBA: 10,
  COUNT_NEW: 11, RATING: 16, COUNT_REVIEWS: 17, BUY_BOX_SHIPPING: 18,
} as const;

export type KeepaProduct = Record<string, any>;

export function keepaConfig() {
  return {
    apiKey: process.env.KEEPA_API_KEY || "",
    defaultDomain: (process.env.KEEPA_DEFAULT_DOMAIN || "US").toUpperCase(),
    statsDays: Number(process.env.KEEPA_STATS_DAYS || "90"),
  };
}

export function normalizeDomain(domain?: string | null): string {
  const raw = (domain || keepaConfig().defaultDomain || "US").trim().toUpperCase();
  const code = DOMAIN_ALIASES[raw];
  if (!code) {
    throw new Error(
      `Unsupported marketplace ${raw}. Use one of: ${Object.keys(DOMAIN_ALIASES).join(", ")}`,
    );
  }
  return code;
}

export function domainId(domain?: string | null): number {
  return DOMAIN_IDS[normalizeDomain(domain)] ?? 1;
}

export class KeepaError extends Error {
  status: number;
  constructor(message: string, status = 502) {
    super(message);
    this.name = "KeepaError";
    this.status = status;
  }
}

async function keepaGet(path: string, params: Record<string, string | number>): Promise<any> {
  const { apiKey } = keepaConfig();
  if (!apiKey) {
    throw new KeepaError("KEEPA_API_KEY не задан — живой поиск недоступен.", 400);
  }
  const url = new URL(`https://api.keepa.com/${path}`);
  url.searchParams.set("key", apiKey);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v));

  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch (e) {
    throw new KeepaError(`Сеть до api.keepa.com недоступна: ${(e as Error).message}`, 502);
  }
  if (res.status === 429) {
    throw new KeepaError("Закончились токены Keepa (429). Подождите пополнения квоты.", 429);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    if (res.status === 401 || res.status === 403) {
      throw new KeepaError("Keepa отклонил ключ (401/403): проверьте KEEPA_API_KEY и подписку.", res.status);
    }
    throw new KeepaError(`Keepa ответил ${res.status}: ${body.slice(0, 200)}`, 502);
  }
  return res.json();
}

export type SearchFilters = {
  title?: string;
  categoryId?: number;
  brand?: string;
  minPrice?: number;
  maxPrice?: number;
  minRating?: number;
  maxSalesRank?: number;
  minReviewCount?: number;
  maxOfferCount?: number;
  minMonthlySold?: number;
  sortBySalesRank?: boolean;
  extraFilters?: Record<string, unknown>;
};

/** Translate friendly filters into a Keepa Product Finder selection (ported
 *  from keepa_client.build_selection). Prices → cents, rating → 0-50 scale. */
export function buildSelection(f: SearchFilters): Record<string, unknown> {
  const sel: Record<string, unknown> = { productType: [0, 1] };
  if (f.title) sel.title = f.title;
  if (f.categoryId != null) sel.rootCategory = f.categoryId;
  if (f.brand) sel.brand = [f.brand];
  if (f.minPrice != null) sel.current_NEW_gte = Math.round(f.minPrice * 100);
  if (f.maxPrice != null) sel.current_NEW_lte = Math.round(f.maxPrice * 100);
  if (f.minRating != null) sel.current_RATING_gte = Math.round(f.minRating * 10);
  if (f.maxSalesRank != null) sel.current_SALES_lte = Math.round(f.maxSalesRank);
  if (f.minReviewCount != null) sel.current_COUNT_REVIEWS_gte = Math.round(f.minReviewCount);
  if (f.maxOfferCount != null) sel.current_COUNT_NEW_lte = Math.round(f.maxOfferCount);
  if (f.minMonthlySold != null) sel.monthlySold_gte = Math.round(f.minMonthlySold);
  if (f.sortBySalesRank ?? true) sel.sort = [["current_SALES", "asc"]];
  if (f.extraFilters) Object.assign(sel, f.extraFilters);
  return sel;
}

/** Run a Product Finder query; returns matching ASINs (sliced to `limit`). */
export async function productFinder(
  selection: Record<string, unknown>,
  opts: { domain?: string; limit?: number } = {},
): Promise<string[]> {
  const data = await keepaGet("query", {
    domain: domainId(opts.domain),
    selection: JSON.stringify(selection),
  });
  const asins: string[] = data.asinList || [];
  return typeof opts.limit === "number" ? asins.slice(0, opts.limit) : asins;
}

/** Fetch full product records (with the server-computed `stats` object). */
export async function queryProducts(
  asins: string[],
  opts: { domain?: string; statsDays?: number } = {},
): Promise<KeepaProduct[]> {
  if (asins.length === 0) return [];
  const data = await keepaGet("product", {
    domain: domainId(opts.domain),
    asin: asins.join(","),
    stats: opts.statsDays ?? keepaConfig().statsDays,
    rating: 1,
    buybox: 1,
    history: 0,
  });
  return data.products || [];
}

export type CategoryHit = { catId: string; name: string; parentId: string | null };

/** Find Keepa category ids whose names match a search term. */
export async function searchCategories(
  term: string,
  opts: { domain?: string } = {},
): Promise<CategoryHit[]> {
  const data = await keepaGet("category", {
    domain: domainId(opts.domain),
    type: "search",
    term,
  });
  const cats = data.categories || {};
  return Object.entries(cats).map(([catId, c]: [string, any]) => ({
    catId,
    name: c?.name ?? catId,
    parentId: c?.parent ? String(c.parent) : null,
  }));
}

/** Best-selling ASINs for a category. */
export async function bestSellers(
  categoryId: number | string,
  opts: { domain?: string } = {},
): Promise<string[]> {
  const data = await keepaGet("bestsellers", {
    domain: domainId(opts.domain),
    category: String(categoryId),
  });
  return data?.bestSellersList?.asinList || [];
}

/** Remaining request tokens (quota). */
export async function tokenStatus(): Promise<{
  tokensLeft: number | null;
  refillIn: number | null;
  refillRate: number | null;
}> {
  const data = await keepaGet("token", {});
  return {
    tokensLeft: data?.tokensLeft ?? null,
    refillIn: data?.refillIn ?? null,
    refillRate: data?.refillRate ?? null,
  };
}

export function amazonUrl(asin: string, domain?: string): string {
  const tld = DOMAIN_TLDS[normalizeDomain(domain)] ?? "com";
  return `https://www.amazon.${tld}/dp/${asin}`;
}

export function keepaUrl(asin: string, domain?: string): string {
  return `https://keepa.com/#!product/${domainId(domain)}-${asin}`;
}
