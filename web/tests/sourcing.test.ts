import { describe, it, expect } from "vitest";
import {
  normalizeTiers,
  pickTier,
  toBase,
  fxRate,
  marketCurrency,
  computeEconomics,
  sourcingVerdict,
  buildRow,
  buildPlan,
  _orderQty,
  _resolveFreight,
  _amazonOnlyRow,
  DEFAULT_REFERRAL_PCT,
  MIN_REFERRAL_FEE,
  DEFAULT_DUTY_PCT,
  BUY_MARGIN,
  BUY_ROI,
  REJECT_MARGIN,
  REJECT_ROI,
  type Item,
  type Supplier,
} from "@/lib/sourcing";

// Floating-point approx helper mirroring pytest.approx for the magnitudes here.
function approx(value: number | null, expected: number, abs = 1e-4): void {
  expect(value).not.toBeNull();
  expect(Math.abs((value as number) - expected)).toBeLessThanOrEqual(abs);
}

// Recreate the sample-item helper from tests/test_sourcing.py.
function sampleItem(): Item {
  return {
    asin: "B0EX",
    title: "Dual Monitor Stand",
    brand: "Wantai",
    manufacturer: "Putian Wantai Hardware Co., Ltd.",
    marketplace: "DE",
    currency: "EUR",
    amazon_sell_price: 32.0,
    amazon_referral_pct: 0.15,
    amazon_referral_source: "keepa",
    amazon_fba_fee: 4.5,
    monthly_sold: 400,
    weight_g: 2500,
    url: "https://www.amazon.de/dp/B0EX",
    suppliers: [
      {
        platform: "1688",
        supplier_name: "Putian Wantai Hardware",
        is_manufacturer: true,
        matches_amazon_manufacturer: true,
        match_quality: "точное",
        match_basis: "MS008 + фото",
        model_number: "MS008",
        currency: "CNY",
        moq: 100,
        price_tiers: [
          { min_qty: 1, max_qty: 100, unit_price: 48 },
          { min_qty: 101, max_qty: 999, unit_price: 45 },
          { min_qty: 1000, max_qty: null, unit_price: 42 },
        ],
        url: "https://detail.1688.com/x.html",
      },
    ],
  };
}

// --- MOQ price tiers --------------------------------------------------------

describe("normalizeTiers", () => {
  it("infers max_qty from the next tier and keeps the last open", () => {
    const tiers = normalizeTiers([
      { min_qty: 1, max_qty: 100, unit_price: 9.91 },
      { min_qty: 1000, unit_price: 9.53 }, // open tier, no max
      { min_qty: 101, max_qty: 999, unit_price: 9.78 },
    ]);
    expect(tiers.map((t) => t.min_qty)).toEqual([1, 101, 1000]);
    expect(tiers[0]!.max_qty).toBe(100);
    expect(tiers[2]!.max_qty).toBeNull(); // last tier stays open
  });

  it("skips malformed tiers and clamps min_qty to >= 1", () => {
    const tiers = normalizeTiers([
      { min_qty: 0, unit_price: 5 }, // 0 -> 1
      { min_qty: 2, unit_price: "oops" as unknown as number }, // bad price -> dropped
      { unit_price: 7 }, // missing min_qty -> 1
    ]);
    expect(tiers.every((t) => t.min_qty >= 1)).toBe(true);
    expect(tiers.length).toBe(2);
  });
});

describe("pickTier", () => {
  const tiers = [
    { min_qty: 1, max_qty: 100, unit_price: 9.91 },
    { min_qty: 101, max_qty: 999, unit_price: 9.78 },
    { min_qty: 1000, max_qty: null, unit_price: 9.53 },
  ];

  it("matches the order quantity to the right tier", () => {
    // 100 units -> first tier (NOT the cheapest >=1000 tier) — the core fix.
    expect(pickTier(tiers, 100)!.unit_price).toBe(9.91);
    expect(pickTier(tiers, 500)!.unit_price).toBe(9.78);
    expect(pickTier(tiers, 5000)!.unit_price).toBe(9.53);
  });

  it("falls back to the MOQ (smallest) tier when qty is null", () => {
    expect(pickTier(tiers, null)!.unit_price).toBe(9.91);
  });

  it("returns null when there are no tiers", () => {
    expect(pickTier([], 10)).toBeNull();
    expect(pickTier(null, 10)).toBeNull();
  });
});

// --- currency ---------------------------------------------------------------

describe("currency conversion", () => {
  it("converts via fx and flags unknown rates", () => {
    const [val, known] = toBase(9.91, "EUR", "USD", { EUR: 1.08 });
    approx(val, 10.7028);
    expect(known).toBe(true);

    // Missing rate -> assume 1.0 and flag it.
    const [val2, known2] = toBase(100, "CNY", "USD", {});
    expect(val2).toBe(100);
    expect(known2).toBe(false);
  });

  it("returns [1.0, true] for the base currency itself", () => {
    expect(fxRate("USD", "USD", {})).toEqual([1.0, true]);
    expect(fxRate(null, "USD", { EUR: 1.08 })).toEqual([1.0, true]);
  });

  it("returns [null, true] for a null amount", () => {
    expect(toBase(null, "EUR", "USD", { EUR: 1.08 })).toEqual([null, true]);
  });

  it("maps marketplace codes to currencies (default USD)", () => {
    expect(marketCurrency("DE")).toBe("EUR");
    expect(marketCurrency("us")).toBe("USD");
    expect(marketCurrency("JP")).toBe("JPY");
    expect(marketCurrency("ZZ")).toBe("USD");
    expect(marketCurrency(null)).toBe("USD");
  });
});

// --- economics --------------------------------------------------------------

describe("computeEconomics", () => {
  it("computes landed cost, margin and ROI in base currency", () => {
    // unit 6.72, freight 3, duty (6.72+3)*0.05=0.486, landed=10.206
    const econ = computeEconomics({
      sellBase: 32.0 * 1.08, // 34.56
      referralPct: 0.15,
      fbaFeeBase: 4.5 * 1.08, // 4.86
      unitCostBase: 48 * 0.14, // 6.72
      freightBase: 3.0,
      dutyPct: 0.05,
      monthlySold: 400,
      qty: 100,
    });
    approx(econ.unit_cost, 6.72);
    approx(econ.freight, 3.0);
    approx(econ.duty, 0.486);
    approx(econ.landed_cost, 10.206);
    // amazon_fee = max(34.56*0.15, 0.30) + 4.86 = 5.184 + 4.86 = 10.044
    approx(econ.amazon_fee, 10.044);
    // profit = (34.56 - 10.044) - 10.206 = 14.31
    approx(econ.profit_per_unit, 14.31);
    expect(econ.margin_pct!).toBeGreaterThan(0.3);
    expect(econ.roi_pct!).toBeGreaterThan(0.6);
    approx(econ.order_budget, 1020.6, 0.01); // landed * qty
  });

  it("applies the Amazon minimum referral fee", () => {
    const econ = computeEconomics({
      sellBase: 1.0, // 1 * 0.15 = 0.15 < MIN_REFERRAL_FEE
      referralPct: 0.15,
      fbaFeeBase: 0,
      unitCostBase: 0.5,
      freightBase: 0,
      dutyPct: 0,
      monthlySold: null,
      qty: null,
    });
    approx(econ.amazon_fee, MIN_REFERRAL_FEE);
  });

  it("leaves derived fields null when unit cost is missing", () => {
    const econ = computeEconomics({
      sellBase: 30,
      referralPct: 0.15,
      fbaFeeBase: 2,
      unitCostBase: null,
      freightBase: 5,
      dutyPct: 0.05,
      monthlySold: 100,
      qty: 50,
    });
    expect(econ.landed_cost).toBeNull();
    expect(econ.duty).toBeNull();
    expect(econ.profit_per_unit).toBeNull();
    expect(econ.order_budget).toBeNull();
  });
});

describe("_orderQty", () => {
  it("prefers explicit order_quantity over moq and tiers", () => {
    expect(
      _orderQty(
        { order_quantity: 250, moq: 100, price_tiers: [{ min_qty: 5, unit_price: 1 }] },
        null,
      ),
    ).toBe(250);
  });
  it("uses moq when no explicit quantity", () => {
    expect(_orderQty({ moq: 100 }, null)).toBe(100);
  });
  it("falls back to the smallest tier, then the default", () => {
    expect(_orderQty({ price_tiers: [{ min_qty: 50, unit_price: 1 }] }, 999)).toBe(50);
    expect(_orderQty({}, 999)).toBe(999);
  });
});

// --- full plan: economics + verdict -----------------------------------------

describe("buildPlan economics and verdict", () => {
  it("computes economics, scenarios and a BUY verdict for the sample item", () => {
    const plan = buildPlan([sampleItem()], {
      baseCurrency: "USD",
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      freightPerKg: 1.2,
    });
    const row = plan.rows[0]!;
    expect(row.order_qty).toBe(100);
    expect(row.tier_range).toBe("1–100");
    // unit 48*0.14=6.72; freight 2.5*1.2=3; duty (6.72+3)*0.05=0.486; landed≈10.206
    approx(row.unit_cost ?? null, 6.72);
    approx(row.freight ?? null, 3.0);
    approx(row.landed_cost ?? null, 10.206, 0.01);
    expect(row.margin_pct!).toBeGreaterThan(0.3);
    expect(row.roi_pct!).toBeGreaterThan(0.6);
    expect(row.verdict).toBe("ЗАКУПАТЬ");
    expect(row.scenarios!.length).toBe(3); // one per MOQ tier
    // weight-based freight is recorded in assumptions
    expect(row.assumptions!).toContain("кг ×");
  });

  it("exposes plan-level metadata", () => {
    const plan = buildPlan([sampleItem()], {
      fx: { EUR: 1.08, CNY: 0.14 },
      freightPerKg: 1.2,
    });
    expect(plan.currency).toBe("USD");
    expect(plan.base_currency).toBe("USD");
    expect(plan.duty_pct).toBe(DEFAULT_DUTY_PCT);
    expect(plan.freight_per_kg).toBe(1.2);
    expect(plan.fx).toEqual({ EUR: 1.08, CNY: 0.14 });
  });

  it("produces one scenario per tier with increasing margin as qty grows", () => {
    const plan = buildPlan([sampleItem()], {
      fx: { EUR: 1.08, CNY: 0.14 },
      freightPerKg: 1.2,
    });
    const scenarios = plan.rows[0]!.scenarios!;
    expect(scenarios.map((s) => s.qty)).toEqual([1, 101, 1000]);
    // Cheaper unit cost at higher volume -> higher margin.
    expect(scenarios[2]!.margin_pct!).toBeGreaterThan(scenarios[0]!.margin_pct!);
    expect(scenarios[2]!.unit_cost!).toBeLessThan(scenarios[0]!.unit_cost!);
  });
});

// --- duty override ----------------------------------------------------------

describe("duty override", () => {
  it("a per-supplier duty_pct wins over the country default (duty-free => lower landed)", () => {
    const base = buildPlan([sampleItem()], {
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      freightPerKg: 1.2,
    }).rows[0]!;

    const item2 = sampleItem();
    item2.suppliers![0]!.duty_pct = 0.0; // duty-free for this HS code
    const free = buildPlan([item2], {
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      freightPerKg: 1.2,
    }).rows[0]!;

    expect(base.duty!).toBeGreaterThan(0);
    expect(free.duty).toBe(0);
    expect(free.landed_cost!).toBeLessThan(base.landed_cost!);
  });

  it("a per-item duty_pct also overrides the default", () => {
    const item = sampleItem();
    item.duty_pct = 0.2; // 20% item-level duty
    const row = buildPlan([item], {
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      freightPerKg: 1.2,
    }).rows[0]!;
    // duty = (6.72 + 3) * 0.20 = 1.944
    approx(row.duty ?? null, 1.944);
    expect(row.assumptions!).not.toContain("пошлина по умолчанию");
  });

  it("adds the default-duty assumption when neither supplier nor item overrides", () => {
    const row = buildPlan([sampleItem()], {
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      freightPerKg: 1.2,
    }).rows[0]!;
    expect(row.assumptions!).toContain("пошлина по умолчанию 5%");
  });
});

// --- freight resolution -----------------------------------------------------

describe("freight resolution", () => {
  it("explicit freight_per_unit (converted from supplier currency) wins over weight", () => {
    const item = sampleItem();
    // 10 CNY freight per unit -> 10 * 0.14 = 1.4 USD, ignoring weight*rate (=3).
    item.suppliers![0]!.freight_per_unit = 10;
    const row = buildPlan([item], {
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      freightPerKg: 1.2,
    }).rows[0]!;
    approx(row.freight ?? null, 1.4);
    expect(row.assumptions!).not.toContain("кг ×");
  });

  it("falls back to package weight (kg) × freight_per_kg", () => {
    const row = buildPlan([sampleItem()], {
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      freightPerKg: 1.2,
    }).rows[0]!;
    approx(row.freight ?? null, 3.0); // 2.5 kg * 1.2
    expect(row.assumptions!).toContain("логистика = 2.5 кг × 1.2 USD/кг");
  });

  it("defaults freight to 0 with an assumption note when nothing is given", () => {
    const item = sampleItem();
    item.weight_g = null; // no weight to compute from
    const row = buildPlan([item], {
      fx: { EUR: 1.08, CNY: 0.14 },
      dutyPct: 0.05,
      // no freightPerKg
    }).rows[0]!;
    expect(row.freight).toBe(0.0);
    expect(row.assumptions!).toContain("логистика не задана (0)");
  });

  it("_resolveFreight flags an unknown logistics fx rate", () => {
    const assumptions: string[] = [];
    const supplier: Supplier = { currency: "CNY", freight_per_unit: 10 };
    const [val, known] = _resolveFreight({}, supplier, "USD", {}, 1.2, assumptions);
    expect(known).toBe(false);
    expect(val).toBe(10); // rate assumed 1.0
    expect(assumptions.some((a) => a.includes("курс логистики"))).toBe(true);
  });
});

// --- verdict thresholds -----------------------------------------------------

describe("verdict thresholds", () => {
  it("REJECT when only an analog is found", () => {
    const item = sampleItem();
    item.suppliers![0]!.match_quality = "аналог";
    const row = buildPlan([item], {
      fx: { EUR: 1.08, CNY: 0.14 },
      freightPerKg: 1.2,
    }).rows[0]!;
    expect(row.verdict).toBe("ОТКАЗ");
  });

  it("REJECT on a thin margin even with an exact match", () => {
    // Push the unit cost very high so margin falls below REJECT_MARGIN.
    const item = sampleItem();
    item.suppliers![0]!.price_tiers = [{ min_qty: 1, unit_price: 200 }];
    const row = buildPlan([item], {
      fx: { EUR: 1.08, CNY: 0.14 },
      freightPerKg: 1.2,
    }).rows[0]!;
    expect(row.margin_pct!).toBeLessThan(REJECT_MARGIN);
    expect(row.verdict).toBe("ОТКАЗ");
  });

  it("WATCH (ПРОВЕРИТЬ) when no supplier is matched", () => {
    const item = sampleItem();
    item.suppliers = [];
    const row = buildPlan([item], { fx: { EUR: 1.08 } }).rows[0]!;
    expect(row.verdict).toBe("ПРОВЕРИТЬ");
    expect(row.match_quality).toBe("не найдено");
    expect(row.confidence).toBe("low");
  });

  it("sourcingVerdict: BUY needs margin, ROI and an exact/близкое match", () => {
    expect(
      sourcingVerdict({
        margin_pct: 0.4,
        roi_pct: 0.7,
        match_quality: "точное",
        unit_cost: 6.72,
      }).verdict,
    ).toBe("ЗАКУПАТЬ");
    // A great margin/ROI but only an analog -> REJECT.
    expect(
      sourcingVerdict({
        margin_pct: 0.4,
        roi_pct: 0.7,
        match_quality: "аналог",
        unit_cost: 6.72,
      }).verdict,
    ).toBe("ОТКАЗ");
    // Intermediate (близкое, mid margin/ROI) -> WATCH.
    expect(
      sourcingVerdict({
        margin_pct: 0.25,
        roi_pct: 0.5,
        match_quality: "близкое",
        unit_cost: 6.72,
      }).verdict,
    ).toBe("ПРОВЕРИТЬ");
  });

  it("sourcingVerdict: missing data -> ПРОВЕРИТЬ/low", () => {
    const v = sourcingVerdict({ margin_pct: null, roi_pct: null, unit_cost: null });
    expect(v.verdict).toBe("ПРОВЕРИТЬ");
    expect(v.confidence).toBe("low");
    expect(v.rationale).toBe("недостаточно данных по поставщику/цене");
  });
});

// --- amazon-only row --------------------------------------------------------

describe("_amazonOnlyRow", () => {
  it("builds a placeholder row with no supplier", () => {
    const row = _amazonOnlyRow(sampleItem(), "USD");
    expect(row.match_quality).toBe("не найдено");
    expect(row.verdict).toBe("ПРОВЕРИТЬ");
    expect(row.rationale).toBe("поставщик в Китае ещё не найден");
    expect(row.scenarios).toEqual([]);
    // sell price converted with no fx table -> rate 1.0 (EUR unknown).
    approx(row.amazon_sell_price ?? null, 32.0);
  });
});

// --- exported constants -----------------------------------------------------

describe("exported thresholds", () => {
  it("match the Python values", () => {
    expect(DEFAULT_REFERRAL_PCT).toBe(0.15);
    expect(MIN_REFERRAL_FEE).toBe(0.3);
    expect(DEFAULT_DUTY_PCT).toBe(0.05);
    expect(BUY_MARGIN).toBe(0.3);
    expect(BUY_ROI).toBe(0.6);
    expect(REJECT_MARGIN).toBe(0.15);
    expect(REJECT_ROI).toBe(0.3);
  });
});
