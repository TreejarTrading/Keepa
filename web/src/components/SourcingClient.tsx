"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import VerdictBadge from "@/components/VerdictBadge";
import { money, num, pct } from "@/lib/format";

type Tier = { min_qty: string; max_qty: string; unit_price: string };
type Supplier = {
  platform: string;
  supplier_name: string;
  match_quality: string;
  currency: string;
  moq: string;
  freight_per_unit: string;
  duty_pct: string;
  tiers: Tier[];
};

const PLATFORMS = ["1688", "Alibaba", "Made-in-China", "Global Sources", "DHgate"];
const MATCHES = ["точное", "близкое", "аналог"];

function emptySupplier(): Supplier {
  return {
    platform: "1688", supplier_name: "", match_quality: "близкое", currency: "USD",
    moq: "", freight_per_unit: "", duty_pct: "",
    tiers: [{ min_qty: "1", max_qty: "", unit_price: "" }],
  };
}
const n = (s: string): number | undefined => {
  const v = Number(s);
  return s.trim() === "" || Number.isNaN(v) ? undefined : v;
};

export default function SourcingClient() {
  const router = useRouter();
  // Amazon product
  const [asin, setAsin] = useState("");
  const [title, setTitle] = useState("");
  const [sellPrice, setSellPrice] = useState("");
  const [monthlySold, setMonthlySold] = useState("");
  const [weightG, setWeightG] = useState("");
  // params
  const [baseCurrency, setBaseCurrency] = useState("USD");
  const [dutyPct, setDutyPct] = useState("5");
  const [freightPerKg, setFreightPerKg] = useState("");
  const [defaultQty, setDefaultQty] = useState("");
  const [suppliers, setSuppliers] = useState<Supplier[]>([emptySupplier()]);

  const [rows, setRows] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveTitle, setSaveTitle] = useState("");
  const [saving, setSaving] = useState(false);

  function patchSupplier(i: number, p: Partial<Supplier>) {
    setSuppliers((prev) => prev.map((s, idx) => (idx === i ? { ...s, ...p } : s)));
  }
  function patchTier(si: number, ti: number, p: Partial<Tier>) {
    setSuppliers((prev) =>
      prev.map((s, idx) =>
        idx === si ? { ...s, tiers: s.tiers.map((t, j) => (j === ti ? { ...t, ...p } : t)) } : s,
      ),
    );
  }

  function buildPayload(withSave: boolean) {
    const items = [
      {
        asin: asin || "—",
        title: title || undefined,
        amazon_sell_price: n(sellPrice),
        monthly_sold: n(monthlySold),
        package_weight_g: n(weightG),
        marketplace: "US",
        suppliers: suppliers.map((s) => ({
          platform: s.platform,
          supplier_name: s.supplier_name || undefined,
          match_quality: s.match_quality,
          currency: s.currency || baseCurrency,
          moq: n(s.moq),
          freight_per_unit: n(s.freight_per_unit),
          duty_pct: s.duty_pct.trim() === "" ? undefined : (n(s.duty_pct) ?? 0) / 100,
          price_tiers: s.tiers
            .filter((t) => t.unit_price.trim() !== "")
            .map((t) => ({ min_qty: n(t.min_qty) ?? 1, max_qty: n(t.max_qty) ?? null, unit_price: n(t.unit_price) })),
        })),
      },
    ];
    return {
      items,
      baseCurrency,
      dutyPct: dutyPct.trim() === "" ? undefined : (n(dutyPct) ?? 0) / 100,
      freightPerKg: n(freightPerKg),
      defaultOrderQuantity: n(defaultQty),
      ...(withSave ? { save: { title: saveTitle || `Сорсинг ${title || asin} — ${new Date().toLocaleDateString("ru-RU")}` } } : {}),
    };
  }

  function validate(): string | null {
    if (n(sellPrice) === undefined) return "Укажите цену продажи Amazon.";
    const hasTier = suppliers.some((s) => s.tiers.some((t) => n(t.unit_price) !== undefined));
    if (!hasTier) return "Добавьте хотя бы один ценовой уровень с ценой за единицу.";
    return null;
  }

  async function compute() {
    const problem = validate();
    if (problem) { setError(problem); setRows([]); return; }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/sourcing/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload(false)),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Ошибка расчёта"); setRows([]); return; }
      setRows(data.plan?.rows || []);
      if (!saveTitle) setSaveTitle(`Сорсинг ${title || asin} — ${new Date().toLocaleDateString("ru-RU")}`);
    } catch {
      setError("Сеть недоступна");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (rows.length === 0) return;
    setSaving(true);
    try {
      const res = await fetch("/api/sourcing/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload(true)),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Не удалось сохранить"); return; }
      if (data.reportId) { router.push(`/reports/${data.reportId}`); return; }
    } finally {
      setSaving(false);
    }
  }

  const cur = baseCurrency;

  return (
    <div className="space-y-5">
      {/* Amazon product */}
      <div className="card p-4">
        <h2 className="mb-3 font-semibold text-slate-800">Товар Amazon</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <div><label className="label">ASIN</label><input className="input" value={asin} onChange={(e) => setAsin(e.target.value)} /></div>
          <div className="md:col-span-2"><label className="label">Название</label><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
          <div><label className="label">Цена продажи, {cur}</label><input className="input" inputMode="decimal" value={sellPrice} onChange={(e) => setSellPrice(e.target.value)} /></div>
          <div><label className="label">Продаж/мес</label><input className="input" inputMode="numeric" value={monthlySold} onChange={(e) => setMonthlySold(e.target.value)} /></div>
          <div><label className="label">Вес, г</label><input className="input" inputMode="numeric" value={weightG} onChange={(e) => setWeightG(e.target.value)} placeholder="для логистики по весу" /></div>
        </div>
      </div>

      {/* Params */}
      <div className="card p-4">
        <h2 className="mb-3 font-semibold text-slate-800">Параметры расчёта</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div><label className="label">Базовая валюта</label><input className="input" value={baseCurrency} onChange={(e) => setBaseCurrency(e.target.value.toUpperCase())} /></div>
          <div><label className="label">Пошлина по умолчанию, %</label><input className="input" inputMode="decimal" value={dutyPct} onChange={(e) => setDutyPct(e.target.value)} /></div>
          <div><label className="label">Логистика, {cur}/кг</label><input className="input" inputMode="decimal" value={freightPerKg} onChange={(e) => setFreightPerKg(e.target.value)} placeholder="если нет точной" /></div>
          <div><label className="label">Объём заказа по умолч.</label><input className="input" inputMode="numeric" value={defaultQty} onChange={(e) => setDefaultQty(e.target.value)} /></div>
        </div>
      </div>

      {/* Suppliers */}
      <div className="card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">Поставщики из Китая</h2>
          <button className="btn-ghost" onClick={() => setSuppliers((p) => [...p, emptySupplier()])}>+ поставщик</button>
        </div>
        <div className="space-y-4">
          {suppliers.map((s, si) => (
            <div key={si} className="rounded-lg border border-slate-200 p-3">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
                <div>
                  <label className="label">Площадка</label>
                  <select className="input" value={s.platform} onChange={(e) => patchSupplier(si, { platform: e.target.value })}>
                    {PLATFORMS.map((p) => <option key={p}>{p}</option>)}
                  </select>
                </div>
                <div className="md:col-span-2"><label className="label">Поставщик</label><input className="input" value={s.supplier_name} onChange={(e) => patchSupplier(si, { supplier_name: e.target.value })} /></div>
                <div>
                  <label className="label">Соответствие</label>
                  <select className="input" value={s.match_quality} onChange={(e) => patchSupplier(si, { match_quality: e.target.value })}>
                    {MATCHES.map((m) => <option key={m}>{m}</option>)}
                  </select>
                </div>
                <div><label className="label">Валюта</label><input className="input" value={s.currency} onChange={(e) => patchSupplier(si, { currency: e.target.value.toUpperCase() })} /></div>
                <div><label className="label">MOQ</label><input className="input" inputMode="numeric" value={s.moq} onChange={(e) => patchSupplier(si, { moq: e.target.value })} /></div>
                <div><label className="label">Логистика/ед., {s.currency}</label><input className="input" inputMode="decimal" value={s.freight_per_unit} onChange={(e) => patchSupplier(si, { freight_per_unit: e.target.value })} placeholder="если известно" /></div>
                <div><label className="label">Пошлина (товар), %</label><input className="input" inputMode="decimal" value={s.duty_pct} onChange={(e) => patchSupplier(si, { duty_pct: e.target.value })} placeholder="напр. по HS-коду" /></div>
              </div>

              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-600">Ценовые уровни (MOQ)</span>
                  <button className="text-xs text-brand hover:underline" onClick={() => patchSupplier(si, { tiers: [...s.tiers, { min_qty: "", max_qty: "", unit_price: "" }] })}>+ уровень</button>
                </div>
                <div className="space-y-2">
                  {s.tiers.map((t, ti) => (
                    <div key={ti} className="flex items-center gap-2">
                      <input className="input" placeholder="от кол-ва" inputMode="numeric" value={t.min_qty} onChange={(e) => patchTier(si, ti, { min_qty: e.target.value })} />
                      <input className="input" placeholder="до кол-ва (пусто = ∞)" inputMode="numeric" value={t.max_qty} onChange={(e) => patchTier(si, ti, { max_qty: e.target.value })} />
                      <input className="input" placeholder={`цена/ед., ${s.currency}`} inputMode="decimal" value={t.unit_price} onChange={(e) => patchTier(si, ti, { unit_price: e.target.value })} />
                      {s.tiers.length > 1 && (
                        <button className="text-slate-400 hover:text-red-600" onClick={() => patchSupplier(si, { tiers: s.tiers.filter((_, j) => j !== ti) })}>✕</button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {suppliers.length > 1 && (
                <div className="mt-2 text-right">
                  <button className="text-xs text-red-600 hover:underline" onClick={() => setSuppliers((p) => p.filter((_, j) => j !== si))}>удалить поставщика</button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button className="btn-primary" onClick={compute} disabled={busy}>{busy ? "Расчёт…" : "Рассчитать"}</button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </div>

      {/* Result */}
      {rows.length > 0 && (
        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
            <h2 className="font-semibold text-slate-900">Экономика по поставщикам</h2>
            <div className="flex items-center gap-2">
              <input className="input w-64" value={saveTitle} onChange={(e) => setSaveTitle(e.target.value)} placeholder="Название отчёта" />
              <button className="btn-primary" onClick={save} disabled={saving}>{saving ? "Сохранение…" : "Сохранить отчёт"}</button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="th">Поставщик</th>
                  <th className="th">Заказ</th>
                  <th className="th">Себест./ед.</th>
                  <th className="th">Логистика</th>
                  <th className="th">Пошлина</th>
                  <th className="th">Landed</th>
                  <th className="th">Прибыль/ед.</th>
                  <th className="th">Маржа</th>
                  <th className="th">ROI</th>
                  <th className="th">Вердикт</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r: any, i: number) => (
                  <tr key={i} className="border-b border-slate-50 align-top hover:bg-slate-50">
                    <td className="td">
                      <div className="font-medium">{r.supplier_name || "—"}</div>
                      <div className="text-xs text-slate-400">{r.platform} · {r.match_quality || "—"}</div>
                    </td>
                    <td className="td">{num(r.order_qty)}</td>
                    <td className="td">{money(r.unit_cost, cur)}</td>
                    <td className="td">{money(r.freight, cur)}</td>
                    <td className="td">{money(r.duty, cur)}</td>
                    <td className="td font-medium">{money(r.landed_cost, cur)}</td>
                    <td className="td">{money(r.profit_per_unit, cur)}</td>
                    <td className="td">{pct(r.margin_pct)}</td>
                    <td className="td">{pct(r.roi_pct)}</td>
                    <td className="td"><VerdictBadge verdict={r.verdict} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows[0]?.assumptions && rows[0].assumptions !== "—" && (
            <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
              Допущения: {rows[0].assumptions}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
