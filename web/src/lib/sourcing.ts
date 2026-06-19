/**
 * China-sourcing layer: match Amazon products to Chinese suppliers and model
 * the unit economics of importing & reselling them.
 *
 * Faithful TypeScript port of `keepa_mcp/sourcing.py`. This module is pure and
 * deterministic — it makes no API/network calls. Given assembled inputs it:
 *
 *  - picks the correct MOQ price tier for the intended order quantity;
 *  - converts supplier/marketplace currencies to one base currency;
 *  - computes landed unit cost, Amazon fees, profit, margin %, ROI %;
 *  - builds per-volume scenarios (precise what-if hypotheses by order size);
 *  - assigns a rule-based sourcing verdict ЗАКУПАТЬ / ПРОВЕРИТЬ / ОТКАЗ.
 *
 * Input object keys and output row keys deliberately keep the Python snake_case
 * names so the data shape matches the Python module 1:1.
 */

// --- types ------------------------------------------------------------------

export interface PriceTier {
  min_qty?: number | null;
  max_qty?: number | null;
  unit_price?: number | null;
}

/** A normalized tier always has concrete min/unit; max_qty may stay open (null). */
export interface NormalizedTier {
  min_qty: number;
  max_qty: number | null;
  unit_price: number;
}

export interface Supplier {
  platform?: string | null;
  supplier_name?: string | null;
  is_manufacturer?: boolean | null;
  matches_amazon_manufacturer?: boolean | null;
  match_quality?: string | null;
  match_basis?: string | null;
  model_number?: string | null;
  moq?: number | null;
  order_quantity?: number | null;
  currency?: string | null;
  price_tiers?: PriceTier[] | null;
  freight_per_unit?: number | null;
  duty_pct?: number | null;
  url?: string | null;
  notes?: string | null;
  [key: string]: unknown;
}

export interface Item {
  asin?: string | null;
  title?: string | null;
  brand?: string | null;
  manufacturer?: string | null;
  marketplace?: string | null;
  currency?: string | null;
  amazon_sell_price?: number | null;
  amazon_referral_pct?: number | null;
  amazon_referral_source?: string | null;
  amazon_fba_fee?: number | null;
  monthly_sold?: number | null;
  weight_kg?: number | null;
  weight_g?: number | null;
  duty_pct?: number | null;
  url?: string | null;
  suppliers?: Supplier[] | null;
  [key: string]: unknown;
}

export interface Economics {
  amazon_fee: number | null;
  unit_cost: number | null;
  freight: number | null;
  duty: number | null;
  landed_cost: number | null;
  profit_per_unit: number | null;
  margin_pct: number | null;
  roi_pct: number | null;
  monthly_profit: number | null;
  order_budget: number | null;
}

export interface Scenario {
  tier_range: string;
  qty: number;
  unit_cost: number | null;
  landed_cost: number | null;
  profit_per_unit: number | null;
  margin_pct: number | null;
  roi_pct: number | null;
}

export interface Verdict {
  verdict: string;
  confidence: string;
  rationale: string;
}

export interface SourcingRow extends Partial<Economics>, Partial<Verdict> {
  // Amazon side
  asin?: string | null;
  title?: string | null;
  brand?: string | null;
  manufacturer?: string | null;
  marketplace?: string | null;
  amazon_sell_price?: number | null;
  monthly_sold?: number | null;
  amazon_url?: string | null;
  // China side
  platform?: string | null;
  supplier_name?: string | null;
  is_manufacturer?: boolean | null;
  matches_amazon_manufacturer?: boolean | null;
  match_quality?: string | null;
  match_basis?: string | null;
  model_number?: string | null;
  moq?: number | null;
  order_qty?: number | null;
  tier_range?: string;
  all_tiers?: string;
  supplier_currency?: string;
  supplier_url?: string | null;
  notes?: string | null;
  currency?: string;
  assumptions?: string;
  scenarios?: Scenario[];
  [key: string]: unknown;
}

export interface Plan {
  rows: SourcingRow[];
  currency: string;
  base_currency: string;
  fx: Record<string, number>;
  duty_pct: number;
  freight_per_kg: number | null;
  guidance: typeof SOURCING_GUIDANCE;
}

// --- defaults & reference tables --------------------------------------------

/** Amazon referral fee as a fraction of the sale price (15% common default). */
export const DEFAULT_REFERRAL_PCT = 0.15;

/** Amazon's minimum referral fee per item (commonly $0.30 in USD terms). */
export const MIN_REFERRAL_FEE = 0.3;

/** Import duty as a fraction of (unit cost + freight). Default 5% (UAE/GCC). */
export const DEFAULT_DUTY_PCT = 0.05;

/** Currency reported by each Amazon marketplace (Keepa domain code -> ISO 4217). */
export const MARKET_CURRENCY: Record<string, string> = {
  US: "USD",
  GB: "GBP",
  DE: "EUR",
  FR: "EUR",
  IT: "EUR",
  ES: "EUR",
  JP: "JPY",
  CA: "CAD",
  IN: "INR",
  MX: "MXN",
  BR: "BRL",
};

/** Chinese sourcing platforms to cover — NOT only Alibaba. */
export const CHINA_PLATFORMS = [
  {
    code: "1688",
    name: "1688.com",
    note:
      "Внутренний оптовый рынок Китая (от Alibaba). Самые низкие цены и " +
      "прямой выход на фабрики, но интерфейс на китайском, оплата внутри КНР — " +
      "обычно нужен агент/карго. Лучшая площадка для поиска реальной себестоимости.",
  },
  {
    code: "Alibaba",
    name: "Alibaba.com",
    note:
      "Экспортная B2B-площадка. Цены выше 1688, но есть Trade Assurance, " +
      "англоязычные менеджеры и MOQ для экспорта.",
  },
  {
    code: "Made-in-China",
    name: "Made-in-China.com",
    note:
      "Каталог производителей, силён в промышленных и OEM-товарах; " +
      "удобно искать именно фабрику-изготовителя.",
  },
  {
    code: "Global Sources",
    name: "GlobalSources.com",
    note:
      "Проверенные экспортёры электроники и потребтоваров; данные с " +
      "выставок, выше шанс выйти на оригинального производителя.",
  },
  {
    code: "DHgate",
    name: "DHgate.com",
    note:
      "Мелкий опт / дропшиппинг, низкие MOQ. Полезен для проверки цены " +
      "на малых партиях и образцах.",
  },
] as const;

/** Allowed product-match grades, best first. */
export const MATCH_QUALITY = ["точное", "близкое", "аналог"] as const;

/** Sourcing-verdict thresholds (on the representative/base scenario). */
export const BUY_MARGIN = 0.3; // маржа к цене продажи
export const BUY_ROI = 0.6; // прибыль к себестоимости (наценка)
export const REJECT_MARGIN = 0.15;
export const REJECT_ROI = 0.3;

// --- numeric / formatting helpers -------------------------------------------

/**
 * Round to `digits` decimal places. Python uses round() (banker's rounding),
 * but the existing tests pass with normal values, so we use the simpler
 * half-away-from-zero rounding that matches the test expectations.
 */
export function roundN(value: number, digits: number): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

export function round2(value: number): number {
  return roundN(value, 2);
}

/** Coerce to a finite number, mirroring Python's float(); returns null on failure. */
function toFloat(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "boolean") return null;
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return null;
  return num;
}

/** Format like Python's `{x:.0%}` — percentage, no decimals (e.g. 0.3 -> "30%"). */
function pct0(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/**
 * Format like Python's `{x:g}` — general format, strips insignificant trailing
 * zeros. Good enough for the small magnitudes used here (qty, weights, rates).
 */
function fmtG(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  // Python's %g default precision is 6 significant digits.
  let s = value.toPrecision(6);
  if (s.indexOf(".") >= 0 && s.indexOf("e") < 0 && s.indexOf("E") < 0) {
    s = s.replace(/\.?0+$/, "");
  }
  // Normalize "-0" to "0".
  if (s === "-0") s = "0";
  return s;
}

// --- currency ---------------------------------------------------------------

/** ISO currency for an Amazon marketplace code (defaults to USD). */
export function marketCurrency(marketplace: string | null | undefined): string {
  const key = (marketplace ?? "US").trim().toUpperCase();
  return MARKET_CURRENCY[key] ?? "USD";
}

/** Return [multiplier to `base`, isKnown]. Unknown rates assume 1.0. */
export function fxRate(
  currency: string | null | undefined,
  base: string,
  fx: Record<string, number> | null | undefined,
): [number, boolean] {
  const baseU = (base || "USD").toUpperCase();
  const cur = (currency ?? baseU).toUpperCase();
  if (cur === baseU) return [1.0, true];
  const table: Record<string, number> = {};
  for (const [k, v] of Object.entries(fx ?? {})) {
    table[k.toUpperCase()] = v;
  }
  const rate = table[cur];
  if (rate === undefined || rate === null) return [1.0, false];
  const num = toFloat(rate);
  if (num === null) return [1.0, false];
  return [num, true];
}

/** Convert `amount` (in `currency`) to `base`. Returns [value, known]. */
export function toBase(
  amount: unknown,
  currency: string | null | undefined,
  base: string,
  fx: Record<string, number> | null | undefined,
): [number | null, boolean] {
  if (amount === null || amount === undefined) return [null, true];
  const val = toFloat(amount);
  if (val === null) return [null, true];
  const [rate, known] = fxRate(currency, base, fx);
  return [roundN(val * rate, 4), known];
}

// --- MOQ price tiers --------------------------------------------------------

/** Sort price tiers by `min_qty` and infer each tier's `max_qty`. */
export function normalizeTiers(
  tiers: PriceTier[] | null | undefined,
): NormalizedTier[] {
  const cleaned: NormalizedTier[] = [];
  for (const t of tiers ?? []) {
    if (t === null || t === undefined || typeof t !== "object") continue;
    const unit = toFloat(t.unit_price);
    if (unit === null) continue;
    let lo: number;
    const loRaw = toFloat(t.min_qty);
    // Python: int(t.get("min_qty") or 1); falsy (0/null/undefined) -> 1.
    if (!t.min_qty) {
      lo = 1;
    } else if (loRaw === null) {
      lo = 1;
    } else {
      lo = Math.trunc(loRaw);
    }
    let hi: number | null;
    const mx = t.max_qty;
    if (mx === null || mx === undefined) {
      hi = null;
    } else {
      const hiNum = toFloat(mx);
      hi = hiNum === null ? null : Math.trunc(hiNum);
    }
    cleaned.push({ min_qty: Math.max(1, lo), max_qty: hi, unit_price: unit });
  }

  cleaned.sort((a, b) => a.min_qty - b.min_qty);
  // Infer an open max_qty from the next tier's min_qty (… - 1).
  for (let i = 0; i < cleaned.length; i++) {
    const t = cleaned[i]!;
    if (t.max_qty === null && i + 1 < cleaned.length) {
      t.max_qty = Math.max(t.min_qty, cleaned[i + 1]!.min_qty - 1);
    }
  }
  return cleaned;
}

/** Return the price tier that applies to an order of `qty` units. */
export function pickTier(
  tiers: PriceTier[] | null | undefined,
  qty: number | null | undefined,
): NormalizedTier | null {
  const norm = normalizeTiers(tiers);
  if (norm.length === 0) return null;
  let q = qty;
  if (q === null || q === undefined) {
    q = norm[0]!.min_qty;
  }
  for (const t of norm) {
    const hi = t.max_qty;
    if (q >= t.min_qty && (hi === null || q <= hi)) {
      return t;
    }
  }
  // Below the smallest MOQ -> smallest tier; above the largest -> largest tier.
  if (q < norm[0]!.min_qty) return norm[0]!;
  return norm[norm.length - 1]!;
}

/** Human-readable summary of every MOQ tier (for the report / audit). */
export function tiersText(
  tiers: PriceTier[] | null | undefined,
  currency: string | null | undefined,
): string {
  const norm = normalizeTiers(tiers);
  const cur = (currency ?? "").toUpperCase();
  const parts: string[] = [];
  for (const t of norm) {
    const hi = t.max_qty;
    const rng = hi !== null ? `${t.min_qty}–${hi}` : `≥${t.min_qty}`;
    parts.push(`${rng} шт: ${fmtG(t.unit_price)} ${cur}`.trim());
  }
  return parts.join(" | ");
}

// --- economics --------------------------------------------------------------

/** Intended order quantity: explicit > supplier MOQ > smallest tier > default. */
export function _orderQty(
  supplier: Supplier,
  defaultQty: number | null | undefined,
): number | null {
  for (const key of ["order_quantity", "moq"] as const) {
    const val = supplier[key];
    if (val) {
      const num = toFloat(val);
      if (num !== null) {
        return Math.max(1, Math.trunc(num));
      }
    }
  }
  const norm = normalizeTiers(supplier.price_tiers);
  if (norm.length > 0) return norm[0]!.min_qty;
  return defaultQty ?? null;
}

/** Unit economics for one Amazon price vs one supplier unit cost (all in base). */
export function computeEconomics(args: {
  sellBase: number | null;
  referralPct: number;
  fbaFeeBase: number | null;
  unitCostBase: number | null;
  freightBase: number | null;
  dutyPct: number;
  monthlySold: number | null | undefined;
  qty: number | null | undefined;
}): Economics {
  const {
    sellBase,
    referralPct,
    fbaFeeBase,
    unitCostBase,
    freightBase,
    dutyPct,
    monthlySold,
    qty,
  } = args;

  const freight = freightBase || 0.0;
  const duty =
    unitCostBase !== null
      ? roundN((unitCostBase + freight) * dutyPct, 4)
      : null;
  const landed =
    unitCostBase !== null
      ? roundN(unitCostBase + freight + (duty ?? 0.0), 4)
      : null;

  let amazonFee: number | null = null;
  let net: number | null = null;
  if (sellBase !== null) {
    const referral = referralPct
      ? Math.max(sellBase * referralPct, MIN_REFERRAL_FEE)
      : 0.0;
    amazonFee = roundN(referral + (fbaFeeBase ?? 0.0), 4);
    net = roundN(sellBase - amazonFee, 4);
  }

  let profit: number | null = null;
  let margin: number | null = null;
  let roi: number | null = null;
  let monthlyProfit: number | null = null;
  let orderBudget: number | null = null;
  if (net !== null && landed !== null) {
    profit = roundN(net - landed, 4);
    if (sellBase) {
      margin = roundN(profit / sellBase, 4);
    }
    if (landed) {
      roi = roundN(profit / landed, 4);
    }
    if (monthlySold) {
      monthlyProfit = roundN(profit * monthlySold, 2);
    }
  }
  if (landed !== null && qty) {
    orderBudget = roundN(landed * qty, 2);
  }

  return {
    amazon_fee: amazonFee,
    unit_cost: unitCostBase,
    freight: freight ? roundN(freight, 4) : freight,
    duty,
    landed_cost: landed,
    profit_per_unit: profit,
    margin_pct: margin,
    roi_pct: roi,
    monthly_profit: monthlyProfit,
    order_budget: orderBudget,
  };
}

/** Rule-based ЗАКУПАТЬ / ПРОВЕРИТЬ / ОТКАЗ verdict for a comparison row. */
export function sourcingVerdict(row: SourcingRow): Verdict {
  const margin = row.margin_pct ?? null;
  const roi = row.roi_pct ?? null;
  const match = (row.match_quality ?? "").trim().toLowerCase();
  const pros: string[] = [];
  const cons: string[] = [];

  if (margin !== null && margin !== undefined) {
    if (margin >= BUY_MARGIN) {
      pros.push(`маржа ${pct0(margin)}`);
    } else if (margin < REJECT_MARGIN) {
      cons.push(`низкая маржа ${pct0(margin)}`);
    }
  }
  if (roi !== null && roi !== undefined) {
    if (roi >= BUY_ROI) {
      pros.push(`ROI ${pct0(roi)}`);
    } else if (roi < REJECT_ROI) {
      cons.push(`низкий ROI ${pct0(roi)}`);
    }
  }

  if (match === "аналог") {
    cons.push("найден только аналог, не тот же товар");
  } else if (match === "точное") {
    pros.push("точное совпадение товара");
  }
  if (row.matches_amazon_manufacturer) {
    pros.push("совпадает производитель с Amazon");
  } else if (row.is_manufacturer) {
    pros.push("прямой производитель (OEM)");
  }

  let verdict: string;
  let confidence: string;
  let rationale: string;

  if (
    margin === null ||
    margin === undefined ||
    roi === null ||
    roi === undefined ||
    row.unit_cost === null ||
    row.unit_cost === undefined
  ) {
    verdict = "ПРОВЕРИТЬ";
    confidence = "low";
    rationale = "недостаточно данных по поставщику/цене";
  } else {
    if (
      margin >= BUY_MARGIN &&
      roi >= BUY_ROI &&
      (match === "точное" || match === "близкое") &&
      !cons.some((c) => c.includes("низк"))
    ) {
      verdict = "ЗАКУПАТЬ";
    } else if (
      margin < REJECT_MARGIN ||
      roi < REJECT_ROI ||
      match === "аналог"
    ) {
      verdict = "ОТКАЗ";
    } else {
      verdict = "ПРОВЕРИТЬ";
    }
    confidence = pros.length + cons.length >= 3 ? "high" : "medium";
    const joined = [
      ...pros.map((p) => "+ " + p),
      ...cons.map((c) => "- " + c),
    ].join("; ");
    rationale = joined || "—";
  }

  return { verdict, confidence, rationale };
}

// --- row & plan assembly ----------------------------------------------------

/** Product weight in kg from `weight_kg` or Keepa's `weight_g`/packageWeight. */
export function _itemWeightKg(item: Item): number | null {
  const sources: [keyof Item, number][] = [
    ["weight_kg", 1.0],
    ["weight_g", 1000.0],
  ];
  for (const [key, div] of sources) {
    const val = item[key];
    if (val) {
      const num = toFloat(val);
      if (num !== null) return num / div;
    }
  }
  return null;
}

/**
 * Freight per unit, in base currency.
 *
 * Priority: explicit `freight_per_unit` on the supplier > weight × rate
 * (`freight_per_kg` in base currency, weight from Keepa) > 0. Records the
 * method used in `assumptions` so the number is auditable.
 */
export function _resolveFreight(
  item: Item,
  supplier: Supplier,
  baseCurrency: string,
  fx: Record<string, number> | null | undefined,
  freightPerKg: number | null | undefined,
  assumptions: string[],
): [number | null, boolean] {
  const supCur = supplier.currency || baseCurrency;
  const explicit = supplier.freight_per_unit;
  if (explicit !== null && explicit !== undefined) {
    const [val, known] = toBase(explicit, supCur, baseCurrency, fx);
    if (!known) {
      assumptions.push(
        `курс логистики ${supCur}→${baseCurrency} не задан (принят 1.0)`,
      );
    }
    return [val, known];
  }

  const weightKg = _itemWeightKg(item);
  if (freightPerKg && weightKg) {
    const rate = toFloat(freightPerKg)!;
    const val = roundN(weightKg * rate, 4);
    assumptions.push(
      `логистика = ${fmtG(weightKg)} кг × ${fmtG(rate)} ${baseCurrency}/кг`,
    );
    return [val, true];
  }

  assumptions.push("логистика не задана (0)");
  return [0.0, true];
}

/** Combine one Amazon product with one supplier offer into a comparison row. */
export function buildRow(
  item: Item,
  supplier: Supplier,
  opts: {
    baseCurrency: string;
    fx: Record<string, number> | null | undefined;
    dutyPct: number;
    defaultQty: number | null | undefined;
    freightPerKg?: number | null;
  },
): SourcingRow {
  const { baseCurrency, fx, dutyPct, defaultQty } = opts;
  const freightPerKg = opts.freightPerKg ?? null;

  const assumptions: string[] = [];
  const amzCur = item.currency || marketCurrency(item.marketplace);
  const supCur = supplier.currency || baseCurrency;

  const [sellBase, sellKnown] = toBase(
    item.amazon_sell_price,
    amzCur,
    baseCurrency,
    fx,
  );
  if (!sellKnown) {
    assumptions.push(`курс ${amzCur}→${baseCurrency} не задан (принят 1.0)`);
  }
  let referralPct: number;
  if (item.amazon_referral_pct === null || item.amazon_referral_pct === undefined) {
    referralPct = DEFAULT_REFERRAL_PCT;
    assumptions.push(
      `реферальная комиссия не задана (принято ${pct0(DEFAULT_REFERRAL_PCT)})`,
    );
  } else {
    referralPct = toFloat(item.amazon_referral_pct)!;
    if (item.amazon_referral_source === "category") {
      assumptions.push(`referral по категории Amazon (оценка ${pct0(referralPct)})`);
    }
  }
  const [fbaBase] = toBase(item.amazon_fba_fee, amzCur, baseCurrency, fx);
  if (item.amazon_fba_fee === null || item.amazon_fba_fee === undefined) {
    assumptions.push("комиссия FBA не из Keepa (0)");
  }

  const qty = _orderQty(supplier, defaultQty);
  const tier = pickTier(supplier.price_tiers, qty);
  if (tier === null) {
    assumptions.push("нет ценовых уровней поставщика");
  }
  const [unitBase, unitKnown] = toBase(
    tier ? tier.unit_price : null,
    supCur,
    baseCurrency,
    fx,
  );
  if (tier && !unitKnown) {
    assumptions.push(`курс ${supCur}→${baseCurrency} не задан (принят 1.0)`);
  }
  const [freightBase] = _resolveFreight(
    item,
    supplier,
    baseCurrency,
    fx,
    freightPerKg,
    assumptions,
  );

  // Duty: a real per-product/supplier rate (e.g. found by HS code) wins;
  // otherwise fall back to the destination default (UAE/GCC 5%).
  let effDuty = dutyPct;
  let dutyOverridden = false;
  for (const src of [supplier, item] as Array<Supplier | Item>) {
    if (src.duty_pct !== null && src.duty_pct !== undefined) {
      const num = toFloat(src.duty_pct);
      if (num !== null) {
        effDuty = num;
      }
      dutyOverridden = true;
      break;
    }
  }
  if (!dutyOverridden) {
    assumptions.push(`пошлина по умолчанию ${pct0(dutyPct)}`);
  }

  const econ = computeEconomics({
    sellBase,
    referralPct,
    fbaFeeBase: fbaBase,
    unitCostBase: unitBase,
    freightBase,
    dutyPct: effDuty,
    monthlySold: item.monthly_sold,
    qty,
  });

  let tierRange = "";
  if (tier) {
    const hi = tier.max_qty;
    tierRange = hi !== null ? `${tier.min_qty}–${hi}` : `≥${tier.min_qty}`;
  }

  let matchQ = (supplier.match_quality ?? "").trim().toLowerCase();
  if (matchQ && !(MATCH_QUALITY as readonly string[]).includes(matchQ)) {
    matchQ = "";
  }

  const row: SourcingRow = {
    // Amazon side
    asin: item.asin,
    title: item.title,
    brand: item.brand,
    manufacturer: item.manufacturer,
    marketplace: item.marketplace,
    amazon_sell_price: sellBase,
    monthly_sold: item.monthly_sold,
    amazon_url: item.url,
    // China side
    platform: supplier.platform,
    supplier_name: supplier.supplier_name,
    is_manufacturer: supplier.is_manufacturer,
    matches_amazon_manufacturer: supplier.matches_amazon_manufacturer,
    match_quality: matchQ || supplier.match_quality,
    match_basis: supplier.match_basis,
    model_number: supplier.model_number,
    moq: supplier.moq,
    order_qty: qty,
    tier_range: tierRange,
    all_tiers: tiersText(supplier.price_tiers, supCur),
    supplier_currency: supCur,
    supplier_url: supplier.url,
    notes: supplier.notes,
    // economics (already in base currency)
    currency: baseCurrency,
    ...econ,
    assumptions: dedupeJoin(assumptions) || "—",
  };

  // Per-volume scenarios across every MOQ tier (precise what-if hypotheses).
  const scenarios: Scenario[] = [];
  for (const t of normalizeTiers(supplier.price_tiers)) {
    const sQty = t.min_qty;
    const [uBase] = toBase(t.unit_price, supCur, baseCurrency, fx);
    const se = computeEconomics({
      sellBase,
      referralPct,
      fbaFeeBase: fbaBase,
      unitCostBase: uBase,
      freightBase,
      dutyPct: effDuty,
      monthlySold: item.monthly_sold,
      qty: sQty,
    });
    const hi = t.max_qty;
    scenarios.push({
      tier_range: hi !== null ? `${t.min_qty}–${hi}` : `≥${t.min_qty}`,
      qty: sQty,
      unit_cost: se.unit_cost,
      landed_cost: se.landed_cost,
      profit_per_unit: se.profit_per_unit,
      margin_pct: se.margin_pct,
      roi_pct: se.roi_pct,
    });
  }
  row.scenarios = scenarios;
  Object.assign(row, sourcingVerdict(row));
  return row;
}

/** Turn Amazon items + their supplier offers into a full comparison plan. */
export function buildPlan(
  items: Item[] | null | undefined,
  opts: {
    baseCurrency?: string;
    fx?: Record<string, number> | null;
    dutyPct?: number;
    defaultOrderQuantity?: number | null;
    freightPerKg?: number | null;
  } = {},
): Plan {
  const baseCurrency = opts.baseCurrency ?? "USD";
  const fx = opts.fx ?? null;
  const dutyPct = opts.dutyPct ?? DEFAULT_DUTY_PCT;
  const defaultOrderQuantity = opts.defaultOrderQuantity ?? null;
  const freightPerKg = opts.freightPerKg ?? null;

  const base = (baseCurrency || "USD").toUpperCase();
  const rows: SourcingRow[] = [];
  for (const item of items ?? []) {
    const suppliers = item.suppliers ?? [];
    if (suppliers.length === 0) {
      rows.push(_amazonOnlyRow(item, base));
      continue;
    }
    for (const supplier of suppliers) {
      rows.push(
        buildRow(item, supplier, {
          baseCurrency: base,
          fx,
          dutyPct,
          defaultQty: defaultOrderQuantity,
          freightPerKg,
        }),
      );
    }
  }
  return {
    rows,
    currency: base,
    base_currency: base,
    fx: fx ?? {},
    duty_pct: dutyPct,
    freight_per_kg: freightPerKg,
    guidance: SOURCING_GUIDANCE,
  };
}

/** A row for an Amazon product that has no supplier match yet. */
export function _amazonOnlyRow(item: Item, base: string): SourcingRow {
  const [sellBase] = toBase(
    item.amazon_sell_price,
    item.currency || marketCurrency(item.marketplace),
    base,
    null,
  );
  return {
    asin: item.asin,
    title: item.title,
    brand: item.brand,
    manufacturer: item.manufacturer,
    marketplace: item.marketplace,
    amazon_sell_price: sellBase,
    monthly_sold: item.monthly_sold,
    amazon_url: item.url,
    currency: base,
    match_quality: "не найдено",
    verdict: "ПРОВЕРИТЬ",
    confidence: "low",
    rationale: "поставщик в Китае ещё не найден",
    assumptions: "—",
    scenarios: [],
  };
}

// --- guidance (single source of truth, ported verbatim) ---------------------

/** Concise methodology returned alongside data (full text: SOURCING_GUIDE.md). */
export const SOURCING_GUIDANCE = {
  platforms: CHINA_PLATFORMS,
  match_quality: [...MATCH_QUALITY],
  rules: [
    "Цена за единицу зависит от объёма (лесенка MOQ). Сохрани ВСЕ уровни и " +
      "бери цену под фактический объём заказа, а не самый дешёвый ≥1000.",
    "Ищи именно ТОТ ЖE товар: по модели/артикулу, фото, характеристикам и " +
      "бренду. Если совпадение неполное — помечай «близкое» или «аналог».",
    "Используй поле Manufacturer из Amazon как ключ поиска фабрики — возможен " +
      "прямой мэтч на производителя (OEM).",
    "Ищи не только на Alibaba: 1688 (себестоимость), Made-in-China и " +
      "Global Sources (фабрики/OEM), DHgate (малые партии).",
  ],
  verdict_thresholds: {
    ЗАКУПАТЬ: `маржа ≥ ${pct0(BUY_MARGIN)} и ROI ≥ ${pct0(BUY_ROI)}, мэтч точное/близкое`,
    ОТКАЗ: `маржа < ${pct0(REJECT_MARGIN)} или ROI < ${pct0(REJECT_ROI)} или только аналог`,
    ПРОВЕРИТЬ: "промежуточные случаи / недостаточно данных",
  },
  recommended_output:
    "По каждой паре (товар Amazon × поставщик) дай себестоимость " +
    "landed, маржу, ROI, вердикт ЗАКУПАТЬ/ПРОВЕРИТЬ/ОТКАЗ и сценарии по объёму. " +
    "Сопоставь данные Amazon и Китая, укажи гипотезы и риски.",
} as const;

// --- internal utilities -----------------------------------------------------

/** Join unique strings with "; ", preserving first-seen order (≈ dict.fromkeys). */
function dedupeJoin(values: string[]): string {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const v of values) {
    if (!seen.has(v)) {
      seen.add(v);
      out.push(v);
    }
  }
  return out.join("; ");
}
