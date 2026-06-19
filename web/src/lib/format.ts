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

export function verdictClass(verdict?: string | null): string {
  const v = (verdict || "").toUpperCase();
  if (v === "BUY" || v === "ЗАКУПАТЬ") return "badge-buy";
  if (v === "WATCH" || v === "ПРОВЕРИТЬ") return "badge-watch";
  if (v === "SKIP" || v === "ОТКАЗ") return "badge-skip";
  return "badge-neutral";
}
