import { describe, it, expect } from "vitest";
import {
  estimateReferralPct,
  DEFAULT_REFERRAL_PCT,
  MIN_REFERRAL_FEE,
  FLAT_RULES,
} from "@/lib/fees";

describe("constants", () => {
  it("exposes the documented default fallback and min-fee values", () => {
    expect(DEFAULT_REFERRAL_PCT).toBe(0.15);
    expect(MIN_REFERRAL_FEE).toBe(0.3);
  });

  it("keeps the flat rule table identical to the Python source (order + values)", () => {
    expect(FLAT_RULES.map((r) => r.pct)).toEqual([
      0.45, 0.2, 0.17, 0.15, 0.06, 0.08, 0.08, 0.12, 0.12, 0.12, 0.15,
    ]);
    expect(FLAT_RULES[0].keywords).toEqual([
      "amazon device",
      "echo ",
      "fire tv",
      "kindle accessor",
    ]);
  });
});

describe("estimateReferralPct - flat category mapping", () => {
  it("maps electronics to 8% (mirrors the offline-test earbuds fixture)", () => {
    // Same shape analysis.py feeds in: categoryTree names + productGroup.
    expect(estimateReferralPct(["Electronics", "Headphones"], "Electronics")).toBe(0.08);
  });

  it("maps apparel/clothing to 17%", () => {
    expect(estimateReferralPct(["Clothing"], null)).toBe(0.17);
    expect(estimateReferralPct(["Men's Fashion"], null)).toBe(0.17);
  });

  it("maps laptops/computers to 6% (more specific rule wins over electronics)", () => {
    expect(estimateReferralPct(["Computers", "Laptop"], null)).toBe(0.06);
  });

  it("maps Amazon devices to 45%", () => {
    expect(estimateReferralPct(["Amazon Devices", "Fire TV"], null)).toBe(0.45);
  });

  it("maps automotive/industrial/power tools to 12%", () => {
    expect(estimateReferralPct(["Automotive"], null)).toBe(0.12);
    expect(estimateReferralPct(["Industrial & Scientific"], null)).toBe(0.12);
    expect(estimateReferralPct(["Power Tools"], null)).toBe(0.12);
  });

  it("maps fine art to 20% and musical instruments to 15%", () => {
    expect(estimateReferralPct(["Fine Art"], null)).toBe(0.2);
    expect(estimateReferralPct(["Musical Instruments"], null)).toBe(0.15);
  });
});

describe("estimateReferralPct - default fallback", () => {
  it("returns 15% when nothing matches", () => {
    expect(estimateReferralPct(["Books"], null)).toBe(DEFAULT_REFERRAL_PCT);
    expect(estimateReferralPct(["Office Products"], "Office Product")).toBe(0.15);
  });

  it("returns the default for empty / missing inputs", () => {
    expect(estimateReferralPct([], null)).toBe(0.15);
    expect(estimateReferralPct(null)).toBe(0.15);
    expect(estimateReferralPct(undefined)).toBe(0.15);
  });
});

describe("estimateReferralPct - case insensitivity & partial keyword matching", () => {
  it("is case-insensitive", () => {
    expect(estimateReferralPct(["ELECTRONICS"], null)).toBe(0.08);
    expect(estimateReferralPct(["eLeCtRoNiCs"], null)).toBe(0.08);
  });

  it("matches a keyword that is a substring of a longer category name", () => {
    // "earbud" is a substring of "Earbuds & In-Ear Headphones".
    expect(estimateReferralPct(["Earbuds & In-Ear Headphones"], null)).toBe(0.08);
    // "shoe" is a substring of "Shoes".
    expect(estimateReferralPct(["Shoes"], null)).toBe(0.15);
  });

  it("matches against the productGroup as well as the tree", () => {
    expect(estimateReferralPct([], "Consumer Electronics")).toBe(0.08);
  });
});

describe("estimateReferralPct - price-tiered categories", () => {
  it("jewelry: 20% at/under $250, 5% above", () => {
    expect(estimateReferralPct(["Jewelry"], null, 250)).toBe(0.2);
    expect(estimateReferralPct(["Jewelry"], null, 250.01)).toBe(0.05);
    // British spelling also matches.
    expect(estimateReferralPct(["Jewellery"], null, 100)).toBe(0.2);
  });

  it("watch: 16% at/under $1500, 3% above", () => {
    expect(estimateReferralPct(["Watches"], null, 1500)).toBe(0.16);
    expect(estimateReferralPct(["Watches"], null, 2000)).toBe(0.03);
  });

  it("furniture/mattress: 15% at/under $200, 10% above", () => {
    expect(estimateReferralPct(["Furniture"], null, 200)).toBe(0.15);
    expect(estimateReferralPct(["Furniture"], null, 500)).toBe(0.1);
    expect(estimateReferralPct(["Mattresses"], null, 999)).toBe(0.1);
  });

  it("electronics accessories: 15% at/under $100, 8% above", () => {
    expect(estimateReferralPct(["Electronics Accessories"], null, 100)).toBe(0.15);
    expect(estimateReferralPct(["Electronics Accessories"], null, 150)).toBe(0.08);
  });

  it("grocery / gourmet food: 8% at/under $15, 15% above", () => {
    expect(estimateReferralPct(["Grocery"], null, 15)).toBe(0.08);
    expect(estimateReferralPct(["Gourmet Food"], null, 50)).toBe(0.15);
  });

  it("health/household/beauty/baby: 8% at/under $10, 15% above", () => {
    expect(estimateReferralPct(["Health & Household"], null, 10)).toBe(0.08);
    expect(estimateReferralPct(["Beauty & Personal Care"], null, 25)).toBe(0.15);
    expect(estimateReferralPct(["Baby"], null, 5)).toBe(0.08);
  });

  it("treats a missing/zero price as 0 for tier selection (price || 0)", () => {
    // No price -> p = 0 -> low tier.
    expect(estimateReferralPct(["Jewelry"], null)).toBe(0.2);
    expect(estimateReferralPct(["Jewelry"], null, 0)).toBe(0.2);
  });
});

describe("estimateReferralPct - department-name neutralization", () => {
  it("does not misread the combined 'Clothing, Shoes & Jewelry' breadcrumb as jewelry", () => {
    // The combined department name is neutralized to "clothing shoes",
    // so a plain apparel item maps to apparel (17%), not jewelry (20%).
    expect(estimateReferralPct(["Clothing, Shoes & Jewelry", "Dresses"], null, 30)).toBe(
      0.17,
    );
    expect(
      estimateReferralPct(["Clothing, Shoes and Jewelry", "T-Shirts"], null, 30),
    ).toBe(0.17);
  });

  it("still detects a real jewelry sub-node under the combined department", () => {
    expect(
      estimateReferralPct(["Clothing, Shoes & Jewelry", "Jewelry", "Rings"], null, 100),
    ).toBe(0.2);
  });
});

describe("estimateReferralPct - first-hit-wins ordering", () => {
  it("price-tiered checks take precedence over flat rules", () => {
    // "Watches" would not hit a flat rule, but the watch tier returns 3% > $1500.
    expect(estimateReferralPct(["Watches"], null, 5000)).toBe(0.03);
  });

  it("an earlier flat rule wins over a later one", () => {
    // Text contains both "laptop" (0.06, listed first) and "computer" (0.08).
    expect(estimateReferralPct(["Laptop Computers"], null)).toBe(0.06);
  });
});
