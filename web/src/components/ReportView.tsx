"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import VerdictBadge from "@/components/VerdictBadge";
import { money, num, pct, verdictClass } from "@/lib/format";

type Item = {
  id: string;
  asin: string;
  title: string | null;
  brand: string | null;
  imageUrl: string | null;
  rootCategory: string | null;
  sellPrice: number | null;
  monthlySold: number | null;
  rating: number | null;
  reviewCount: number | null;
  referralPct: number | null;
  fbaFee: number | null;
  landedCost: number | null;
  marginPct: number | null;
  roiPct: number | null;
  verdict: string | null;
  rationale: string | null;
};

export default function ReportView({
  reportId, type, marketplace, items, canDelete,
}: {
  reportId: string;
  type: "AMAZON" | "SOURCING";
  marketplace: string;
  items: Item[];
  canDelete: boolean;
}) {
  const router = useRouter();
  const isSourcing = type === "SOURCING";

  const categories = useMemo(
    () => Array.from(new Set(items.map((i) => i.rootCategory).filter(Boolean))) as string[],
    [items],
  );
  const verdicts = useMemo(
    () => Array.from(new Set(items.map((i) => i.verdict).filter(Boolean))) as string[],
    [items],
  );

  const [category, setCategory] = useState("");
  const [verdict, setVerdict] = useState("");
  const [q, setQ] = useState("");
  const [grouped, setGrouped] = useState(false);

  const filtered = useMemo(() => {
    const qq = q.trim().toLowerCase();
    return items.filter(
      (i) =>
        (!category || i.rootCategory === category) &&
        (!verdict || i.verdict === verdict) &&
        (!qq || (i.title || "").toLowerCase().includes(qq) || i.asin.toLowerCase().includes(qq)),
    );
  }, [items, category, verdict, q]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const i of items) if (i.verdict) c[i.verdict] = (c[i.verdict] || 0) + 1;
    return c;
  }, [items]);

  function exportCsv() {
    const headers = isSourcing
      ? ["asin", "title", "amazon_price", "landed_cost", "margin_pct", "roi_pct", "verdict"]
      : ["asin", "title", "category", "price", "monthly_sold", "rating", "reviews", "referral_pct", "fba_fee", "verdict"];
    const rows = filtered.map((i) =>
      isSourcing
        ? [i.asin, i.title, i.sellPrice, i.landedCost, i.marginPct, i.roiPct, i.verdict]
        : [i.asin, i.title, i.rootCategory, i.sellPrice, i.monthlySold, i.rating, i.reviewCount, i.referralPct, i.fbaFee, i.verdict],
    );
    const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [headers, ...rows].map((r) => r.map(esc).join(",")).join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `report-${reportId}.csv`;
    a.click();
  }

  async function remove() {
    if (!confirm("Удалить отчёт? Действие необратимо.")) return;
    const res = await fetch(`/api/reports/${reportId}`, { method: "DELETE" });
    if (res.ok) {
      router.push("/reports");
      router.refresh();
    } else {
      alert("Не удалось удалить отчёт");
    }
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="badge-neutral">Всего: {items.length}</span>
        {Object.entries(counts).map(([v, n]) => (
          <span key={v} className={verdictClass(v)}>{v}: {n}</span>
        ))}
        {categories.length > 0 && <span className="badge-neutral">Категорий: {categories.length}</span>}
        <div className="ml-auto flex gap-2">
          <button className="btn-ghost" onClick={exportCsv}>Экспорт CSV</button>
          {canDelete && <button className="btn-danger" onClick={remove}>Удалить</button>}
        </div>
      </div>

      {/* Filters */}
      <div className="card grid grid-cols-2 gap-3 p-3 md:grid-cols-4">
        <div>
          <label className="label">Категория</label>
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Все</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Вердикт</label>
          <select className="input" value={verdict} onChange={(e) => setVerdict(e.target.value)}>
            <option value="">Все</option>
            {verdicts.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Поиск</label>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="название или ASIN" />
        </div>
        <label className="flex items-end gap-2 pb-2 text-sm text-slate-600">
          <input type="checkbox" checked={grouped} onChange={(e) => setGrouped(e.target.checked)} />
          группировать по категории
        </label>
      </div>

      {/* Table(s) */}
      {grouped && !isSourcing ? (
        groupByCategory(filtered).map(([cat, rows]) => (
          <div key={cat} className="card">
            <div className="border-b border-slate-200 px-4 py-2 font-semibold text-slate-800">{cat} · {rows.length}</div>
            <ItemsTable items={rows} isSourcing={isSourcing} marketplace={marketplace} />
          </div>
        ))
      ) : (
        <div className="card">
          <ItemsTable items={filtered} isSourcing={isSourcing} marketplace={marketplace} />
        </div>
      )}
    </div>
  );
}

function groupByCategory(items: Item[]): [string, Item[]][] {
  const map = new Map<string, Item[]>();
  for (const i of items) {
    const key = i.rootCategory || "Без категории";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(i);
  }
  return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
}

function ItemsTable({ items, isSourcing, marketplace }: { items: Item[]; isSourcing: boolean; marketplace: string }) {
  const cur = marketplace === "GB" ? "GBP" : ["DE", "FR", "IT", "ES"].includes(marketplace) ? "EUR" : "USD";
  if (items.length === 0) {
    return <div className="px-4 py-10 text-center text-sm text-slate-500">Нет товаров под фильтр.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-100">
            <th className="th">Товар</th>
            {isSourcing ? (
              <>
                <th className="th">Цена Amazon</th>
                <th className="th">Landed</th>
                <th className="th">Маржа</th>
                <th className="th">ROI</th>
              </>
            ) : (
              <>
                <th className="th">Категория</th>
                <th className="th">Цена</th>
                <th className="th">Продаж/мес</th>
                <th className="th">Рейтинг</th>
                <th className="th">Отзывы</th>
                <th className="th">Referral</th>
                <th className="th">FBA</th>
              </>
            )}
            <th className="th">Вердикт</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.id} className="border-b border-slate-50 align-top hover:bg-slate-50">
              <td className="td">
                <div className="flex gap-2">
                  {i.imageUrl && <img src={i.imageUrl} alt="" className="h-10 w-10 rounded object-contain" />}
                  <div>
                    <a href={`https://www.amazon.com/dp/${i.asin}`} target="_blank" rel="noreferrer"
                       className="font-medium text-brand hover:underline line-clamp-2">{i.title || i.asin}</a>
                    <div className="text-xs text-slate-400">{i.asin}{i.brand ? ` · ${i.brand}` : ""}</div>
                  </div>
                </div>
              </td>
              {isSourcing ? (
                <>
                  <td className="td">{money(i.sellPrice, cur)}</td>
                  <td className="td">{money(i.landedCost, cur)}</td>
                  <td className="td">{pct(i.marginPct)}</td>
                  <td className="td">{pct(i.roiPct)}</td>
                </>
              ) : (
                <>
                  <td className="td text-xs text-slate-500">{i.rootCategory || "—"}</td>
                  <td className="td">{money(i.sellPrice, cur)}</td>
                  <td className="td">{num(i.monthlySold)}</td>
                  <td className="td">{i.rating ?? "—"}</td>
                  <td className="td">{num(i.reviewCount)}</td>
                  <td className="td">{pct(i.referralPct)}</td>
                  <td className="td">{money(i.fbaFee, cur)}</td>
                </>
              )}
              <td className="td"><VerdictBadge verdict={i.verdict} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
