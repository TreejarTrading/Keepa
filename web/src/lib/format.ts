export function money(v: number | null | undefined, currency = "USD"): string {
  if (v == null || Number.isNaN(v)) return "—";
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(v);
  } catch {
    return `${v.toFixed(2)} ${currency}`;
  }
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function num(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat("ru-RU").format(v);
}

export function dateTime(d: Date | string | null | undefined): string {
  if (!d) return "—";
  const dt = typeof d === "string" ? new Date(d) : d;
  return dt.toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" });
}

// Marketplace → Amazon TLD (mirrors DOMAIN_TLDS in lib/keepa.ts; kept here as a
// pure, client-safe helper so report tables can link to the right storefront).
const AMAZON_TLDS: Record<string, string> = {
  US: "com", GB: "co.uk", UK: "co.uk", DE: "de", FR: "fr", JP: "co.jp",
  CA: "ca", IT: "it", ES: "es", IN: "in", MX: "com.mx", BR: "com.br",
};

/** Amazon product URL for the given marketplace (defaults to amazon.com). */
export function amazonUrl(asin: string, marketplace?: string | null): string {
  const tld = AMAZON_TLDS[(marketplace || "US").toUpperCase()] ?? "com";
  return `https://www.amazon.${tld}/dp/${asin}`;
}

export function verdictClass(verdict?: string | null): string {
  const v = (verdict || "").toUpperCase();
  if (v === "BUY" || v === "ЗАКУПАТЬ") return "badge-buy";
  if (v === "WATCH" || v === "ПРОВЕРИТЬ") return "badge-watch";
  if (v === "SKIP" || v === "ОТКАЗ") return "badge-skip";
  return "badge-neutral";
}
