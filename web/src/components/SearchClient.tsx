"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import VerdictBadge from "@/components/VerdictBadge";
import { money, num, pct } from "@/lib/format";

const DOMAINS = ["US", "GB", "DE", "FR", "IT", "ES", "JP", "CA", "IN", "MX", "BR"];

type Category = { catId: string; name: string };
type Rec = any;
// Shape persisted in a SavedQuery (params column) for an Amazon search.
type SearchParams = {
  domain: string; title: string; brand: string; category: Category | null;
  minPrice: string; maxPrice: string; minRating: string; maxSalesRank: string;
  minReviewCount: string; maxOfferCount: string; minMonthlySold: string; limit: string;
};
type SavedQ = { id: string; name: string; params: SearchParams };

export default function SearchClient({ defaultDomain }: { defaultDomain: string }) {
  const router = useRouter();
  const [domain, setDomain] = useState(defaultDomain);
  const [title, setTitle] = useState("");
  const [brand, setBrand] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minRating, setMinRating] = useState("");
  const [maxSalesRank, setMaxSalesRank] = useState("");
  const [minReviewCount, setMinReviewCount] = useState("");
  const [maxOfferCount, setMaxOfferCount] = useState("");
  const [minMonthlySold, setMinMonthlySold] = useState("");
  const [limit, setLimit] = useState("25");

  const [category, setCategory] = useState<Category | null>(null);
  const [catTerm, setCatTerm] = useState("");
  const [catHits, setCatHits] = useState<Category[]>([]);
  const [catBusy, setCatBusy] = useState(false);
  const [catRan, setCatRan] = useState(false);
  const [catSource, setCatSource] = useState<"live" | "cache" | null>(null);

  const [records, setRecords] = useState<Rec[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ran, setRan] = useState(false);

  const [saveTitle, setSaveTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  // Saved searches (shared across the team).
  const [saved, setSaved] = useState<SavedQ[]>([]);
  const [savingQuery, setSavingQuery] = useState(false);

  async function loadSaved() {
    try {
      const res = await fetch("/api/saved-queries?type=AMAZON");
      const data = await res.json();
      if (res.ok) setSaved(data.queries || []);
    } catch {
      /* non-fatal */
    }
  }
  useEffect(() => {
    loadSaved();
  }, []);

  function currentParams(): SearchParams {
    return {
      domain, title, brand, category,
      minPrice, maxPrice, minRating, maxSalesRank,
      minReviewCount, maxOfferCount, minMonthlySold, limit,
    };
  }

  function applyParams(p: SearchParams) {
    setDomain(p.domain ?? defaultDomain);
    setTitle(p.title ?? ""); setBrand(p.brand ?? "");
    setCategory(p.category ?? null); setCatHits([]); setCatRan(false);
    setMinPrice(p.minPrice ?? ""); setMaxPrice(p.maxPrice ?? "");
    setMinRating(p.minRating ?? ""); setMaxSalesRank(p.maxSalesRank ?? "");
    setMinReviewCount(p.minReviewCount ?? ""); setMaxOfferCount(p.maxOfferCount ?? "");
    setMinMonthlySold(p.minMonthlySold ?? ""); setLimit(p.limit ?? "25");
  }

  async function saveQuery() {
    const suggestion = category?.name || title || brand || "Поиск";
    const name = window.prompt("Название сохранённого поиска:", suggestion);
    if (!name || !name.trim()) return;
    setSavingQuery(true);
    try {
      const res = await fetch("/api/saved-queries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), type: "AMAZON", params: currentParams() }),
      });
      const data = await res.json();
      if (res.ok) setSaved((prev) => [data.query, ...prev]);
      else setError(data.error || "Не удалось сохранить поиск");
    } finally {
      setSavingQuery(false);
    }
  }

  async function deleteQuery(id: string) {
    if (!window.confirm("Удалить сохранённый поиск?")) return;
    const res = await fetch(`/api/saved-queries/${id}`, { method: "DELETE" });
    if (res.ok) setSaved((prev) => prev.filter((q) => q.id !== id));
  }

  function numOrUndef(s: string): number | undefined {
    const n = Number(s);
    return s.trim() === "" || Number.isNaN(n) ? undefined : n;
  }

  async function findCategories() {
    if (catTerm.trim().length < 2) return;
    setCatBusy(true);
    setCatRan(false);
    try {
      const res = await fetch(`/api/categories?term=${encodeURIComponent(catTerm)}&domain=${domain}`);
      const data = await res.json();
      setCatHits(res.ok ? data.categories : []);
      setCatSource(res.ok ? data.source ?? null : null);
      setCatRan(true);
    } finally {
      setCatBusy(false);
    }
  }

  async function run() {
    setBusy(true);
    setError(null);
    setSaveMsg(null);
    try {
      const filters = {
        title: title || undefined,
        brand: brand || undefined,
        categoryId: category ? Number(category.catId) : undefined,
        minPrice: numOrUndef(minPrice),
        maxPrice: numOrUndef(maxPrice),
        minRating: numOrUndef(minRating),
        maxSalesRank: numOrUndef(maxSalesRank),
        minReviewCount: numOrUndef(minReviewCount),
        maxOfferCount: numOrUndef(maxOfferCount),
        minMonthlySold: numOrUndef(minMonthlySold),
      };
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filters, domain, limit: Number(limit) || 25 }),
      });
      const data = await res.json();
      setRan(true);
      if (!res.ok) {
        setError(data.error || "Ошибка поиска");
        setRecords([]);
        return;
      }
      setRecords(data.records || []);
      if (!saveTitle) {
        setSaveTitle(
          (category?.name || title || brand || "Подбор") + ` — ${new Date().toLocaleDateString("ru-RU")}`,
        );
      }
    } catch {
      setError("Сеть недоступна");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (records.length === 0) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const res = await fetch("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: saveTitle || "Отчёт",
          type: "AMAZON",
          marketplace: domain,
          query: { category: category?.name },
          records,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSaveMsg(data.error || "Не удалось сохранить");
        return;
      }
      router.push(`/reports/${data.reportId}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {saved.length > 0 && (
        <div className="card p-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Сохранённые поиски
          </div>
          <div className="flex flex-wrap gap-2">
            {saved.map((q) => (
              <span key={q.id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-sm">
                <button type="button" className="font-medium text-slate-700 hover:text-brand" onClick={() => applyParams(q.params)} title="Загрузить фильтры">
                  {q.name}
                </button>
                <button type="button" className="text-slate-400 hover:text-red-600" onClick={() => deleteQuery(q.id)} title="Удалить">✕</button>
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="card p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div>
            <label className="label">Рынок</label>
            <select className="input" value={domain} onChange={(e) => setDomain(e.target.value)}>
              {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="label">Ключевые слова в названии</label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="напр. mini fridge" />
          </div>
          <div>
            <label className="label">Бренд</label>
            <input className="input" value={brand} onChange={(e) => setBrand(e.target.value)} />
          </div>

          <div className="md:col-span-4">
            <label className="label">Категория Keepa</label>
            <div className="flex gap-2">
              <input
                className="input" value={catTerm}
                onChange={(e) => setCatTerm(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), findCategories())}
                placeholder="поиск категории, напр. Appliances"
              />
              <button type="button" className="btn-ghost whitespace-nowrap" onClick={findCategories} disabled={catBusy}>
                {catBusy ? "…" : "Найти"}
              </button>
            </div>
            {category && (
              <div className="mt-2 text-sm">
                Выбрано: <span className="badge-neutral">{category.name}</span>{" "}
                <button className="text-brand hover:underline" onClick={() => setCategory(null)}>сбросить</button>
              </div>
            )}
            {catHits.length > 0 && !category && (
              <div className="mt-2">
                {catSource === "cache" && (
                  <div className="mb-1 text-xs text-slate-400">из кэша (ключ Keepa недоступен)</div>
                )}
                <div className="flex flex-wrap gap-2">
                  {catHits.map((c) => (
                    <button key={c.catId} type="button" className="badge-neutral hover:bg-slate-200"
                      onClick={() => { setCategory(c); setCatHits([]); setCatRan(false); }}>
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {catRan && !catBusy && !category && catHits.length === 0 && (
              <div className="mt-2 text-sm text-slate-400">Категории не найдены — уточните запрос.</div>
            )}
          </div>

          <div><label className="label">Цена от, $</label><input className="input" inputMode="decimal" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} /></div>
          <div><label className="label">Цена до, $</label><input className="input" inputMode="decimal" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} /></div>
          <div><label className="label">Рейтинг ≥</label><input className="input" inputMode="decimal" value={minRating} onChange={(e) => setMinRating(e.target.value)} placeholder="0–5" /></div>
          <div><label className="label">Sales rank ≤</label><input className="input" inputMode="numeric" value={maxSalesRank} onChange={(e) => setMaxSalesRank(e.target.value)} /></div>
          <div><label className="label">Отзывов ≥</label><input className="input" inputMode="numeric" value={minReviewCount} onChange={(e) => setMinReviewCount(e.target.value)} /></div>
          <div><label className="label">Предложений ≤</label><input className="input" inputMode="numeric" value={maxOfferCount} onChange={(e) => setMaxOfferCount(e.target.value)} /></div>
          <div><label className="label">Продаж/мес ≥</label><input className="input" inputMode="numeric" value={minMonthlySold} onChange={(e) => setMinMonthlySold(e.target.value)} /></div>
          <div><label className="label">Лимит</label><input className="input" inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value)} /></div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button className="btn-primary" onClick={run} disabled={busy}>
            {busy ? "Поиск…" : "Искать на Amazon"}
          </button>
          <button type="button" className="btn-ghost" onClick={saveQuery} disabled={savingQuery}>
            {savingQuery ? "Сохранение…" : "Сохранить поиск"}
          </button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </div>

      {ran && (
        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
            <h2 className="font-semibold text-slate-900">
              Результаты: {records.length}
            </h2>
            {records.length > 0 && (
              <div className="flex items-center gap-2">
                <input className="input w-64" value={saveTitle} onChange={(e) => setSaveTitle(e.target.value)} placeholder="Название отчёта" />
                <button className="btn-primary" onClick={save} disabled={saving}>
                  {saving ? "Сохранение…" : "Сохранить отчёт"}
                </button>
              </div>
            )}
          </div>
          {saveMsg && <div className="px-4 py-2 text-sm text-red-600">{saveMsg}</div>}
          {records.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-slate-500">Ничего не найдено по этим фильтрам.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="th">Товар</th>
                    <th className="th">Категория</th>
                    <th className="th">Цена</th>
                    <th className="th">Продаж/мес</th>
                    <th className="th">Рейтинг</th>
                    <th className="th">Отзывы</th>
                    <th className="th">Referral</th>
                    <th className="th">FBA</th>
                    <th className="th">Вердикт</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r: Rec) => {
                    const f = r.metrics?.amazon_fees || {};
                    const rev = r.metrics?.reviews || {};
                    return (
                      <tr key={r.asin} className="border-b border-slate-50 align-top hover:bg-slate-50">
                        <td className="td">
                          <div className="flex gap-2">
                            {r.image && <img src={r.image} alt="" className="h-10 w-10 rounded object-contain" />}
                            <div>
                              <a href={r.url} target="_blank" rel="noreferrer" className="font-medium text-brand hover:underline line-clamp-2">
                                {r.title || r.asin}
                              </a>
                              <div className="text-xs text-slate-400">{r.asin}{r.brand ? ` · ${r.brand}` : ""}</div>
                            </div>
                          </div>
                        </td>
                        <td className="td text-xs text-slate-500">{r.root_category || "—"}</td>
                        <td className="td">{money(f.sell_price_used)}</td>
                        <td className="td">{num(r.metrics?.demand?.monthly_sold_estimate)}</td>
                        <td className="td">{rev.rating_current ?? "—"}</td>
                        <td className="td">{num(rev.review_count_current)}</td>
                        <td className="td">{pct(f.referral_pct)}</td>
                        <td className="td">{money(f.fba_fee)}</td>
                        <td className="td"><VerdictBadge verdict={r.verdict} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
