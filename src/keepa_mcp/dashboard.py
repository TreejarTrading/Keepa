"""Generate a self-contained interactive HTML dashboard from analysis records.

The dashboard is a single ``.html`` file written into the Products/ folder.
It embeds the analysis records as JSON and renders KPI cards, charts (via
Chart.js from a CDN) and a sortable/filterable product table. No server or
build step is needed — just open it in a browser.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import analysis, config


def _slugify(name: str) -> str:
    name = re.sub(r"[^\w\-. ]+", "", name, flags=re.UNICODE).strip()
    name = re.sub(r"\s+", "_", name)
    return name or "dashboard"


def _row(rec: dict[str, Any]) -> dict[str, Any]:
    """Flatten a record into the compact shape the dashboard JS consumes."""
    m = rec.get("metrics") or {}
    pricing = (m.get("pricing") or {}).get("new") or {}
    rank = m.get("sales_rank") or {}
    comp = m.get("competition") or {}
    reviews = m.get("reviews") or {}
    velocity = m.get("velocity") or {}
    inventory = m.get("inventory") or {}
    opp = rec.get("opportunity") or {}
    tree = rec.get("category_tree") or []
    return {
        "asin": rec.get("asin"),
        "title": rec.get("title"),
        "brand": rec.get("brand"),
        "category": tree[-1] if tree else None,
        "price": pricing.get("current"),
        "price_avg": pricing.get("avg"),
        "volatility": pricing.get("volatility"),
        "rating": reviews.get("rating_current"),
        "reviews": reviews.get("review_count_current"),
        "rank": rank.get("current"),
        "drops30": rank.get("drops_30d"),
        "offers": (comp.get("offer_count") or {}).get("current"),
        "bb_amazon": comp.get("buy_box_is_amazon"),
        "monthly_sales": velocity.get("estimated_monthly_sales"),
        "velocity_trend": velocity.get("trend"),
        "days_inventory": inventory.get("days_of_inventory"),
        "reorder_qty": inventory.get("recommended_order_qty"),
        "stockout_risk": inventory.get("stockout_risk"),
        "opportunity": opp.get("score"),
        "opportunity_label": opp.get("label"),
        "verdict": rec.get("verdict"),
        "rationale": rec.get("rationale"),
        "url": rec.get("url"),
        "keepa_url": rec.get("keepa_url"),
        "image": rec.get("image"),
    }


def generate_dashboard(
    records: list[dict[str, Any]],
    *,
    dashboard_name: str | None = None,
    query_summary: str | None = None,
) -> Path:
    """Write a self-contained HTML dashboard and return its path."""
    out_dir = config.ensure_output_dir()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = _slugify(dashboard_name) if dashboard_name else "keepa_dashboard"
    path = out_dir / f"{base}_{stamp}.html"

    rows = [_row(r) for r in records]
    summary = analysis.category_summary(records)
    payload = {
        "rows": rows,
        "summary": summary,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "query": query_summary or "",
        "title": dashboard_name or "Keepa Product Dashboard",
    }
    html = _HTML_TEMPLATE.replace(
        "/*__DATA__*/", json.dumps(payload, ensure_ascii=False, default=str)
    )
    path.write_text(html, encoding="utf-8")
    return path


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Keepa Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --ink:#e2e8f0; --muted:#94a3b8;
          --accent:#38bdf8; --buy:#22c55e; --watch:#eab308; --skip:#ef4444; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif; }
  header { padding:20px 28px; border-bottom:1px solid #334155; }
  h1 { margin:0 0 4px; font-size:20px; }
  .muted { color:var(--muted); font-size:12px; }
  .wrap { padding:20px 28px; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
          gap:12px; margin-bottom:20px; }
  .kpi { background:var(--card); border:1px solid #334155; border-radius:10px; padding:14px; }
  .kpi .v { font-size:24px; font-weight:700; }
  .kpi .l { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }
  .charts { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
            gap:16px; margin-bottom:24px; }
  .chart { background:var(--card); border:1px solid #334155; border-radius:10px; padding:14px; }
  .chart h3 { margin:0 0 10px; font-size:13px; color:var(--muted); font-weight:600; }
  .toolbar { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px; align-items:center; }
  input,select { background:var(--card); color:var(--ink); border:1px solid #334155;
                 border-radius:8px; padding:8px 10px; font-size:13px; }
  table { width:100%; border-collapse:collapse; background:var(--card);
          border-radius:10px; overflow:hidden; }
  th,td { padding:8px 10px; text-align:left; border-bottom:1px solid #334155; white-space:nowrap; }
  th { cursor:pointer; user-select:none; font-size:12px; color:var(--muted); position:sticky; top:0; background:var(--card); }
  th:hover { color:var(--accent); }
  td.title { white-space:normal; max-width:320px; }
  td a { color:var(--accent); text-decoration:none; }
  .pill { padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }
  .BUY,.high { background:rgba(34,197,94,.18); color:var(--buy); }
  .WATCH,.medium { background:rgba(234,179,8,.18); color:var(--watch); }
  .SKIP,.low { background:rgba(239,68,68,.18); color:var(--skip); }
  .bar { height:6px; border-radius:4px; background:#334155; position:relative; min-width:60px; }
  .bar > span { position:absolute; inset:0; border-radius:4px; background:linear-gradient(90deg,#0ea5e9,#22c55e); }
  .tablewrap { max-height:560px; overflow:auto; border-radius:10px; }
</style>
</head>
<body>
<header>
  <h1 id="title">Keepa Product Dashboard</h1>
  <div class="muted" id="meta"></div>
</header>
<div class="wrap">
  <div class="kpis" id="kpis"></div>
  <div class="charts">
    <div class="chart"><h3>Opportunity score</h3><canvas id="oppChart" height="180"></canvas></div>
    <div class="chart"><h3>Распределение цен</h3><canvas id="priceChart" height="180"></canvas></div>
    <div class="chart"><h3>Вердикты</h3><canvas id="verdictChart" height="180"></canvas></div>
    <div class="chart"><h3>Топ по оценке продаж/мес</h3><canvas id="salesChart" height="180"></canvas></div>
  </div>
  <div class="toolbar">
    <input id="q" placeholder="Поиск по названию / бренду / ASIN…" style="flex:1;min-width:220px">
    <select id="verdictFilter">
      <option value="">Все вердикты</option><option>BUY</option><option>WATCH</option><option>SKIP</option>
    </select>
    <select id="oppFilter">
      <option value="">Любая оценка</option><option value="high">Opportunity: high</option>
      <option value="medium">Opportunity: medium</option><option value="low">Opportunity: low</option>
    </select>
  </div>
  <div class="tablewrap"><table id="tbl"><thead></thead><tbody></tbody></table></div>
</div>
<script>
const DATA = /*__DATA__*/;
const rows = DATA.rows || [];
document.getElementById('title').textContent = DATA.title || 'Keepa Product Dashboard';
document.getElementById('meta').textContent =
  `Сгенерировано ${DATA.generated} · товаров: ${rows.length}` + (DATA.query ? ` · ${DATA.query}` : '');

const num = v => (v===null||v===undefined||v==='') ? null : Number(v);
const fmt = v => v===null||v===undefined ? '—' : (typeof v==='number' ? (Number.isInteger(v)?v:v.toFixed(2)) : v);

// ---- KPI cards ----
const s = DATA.summary || {};
const verdicts = rows.reduce((a,r)=>{ if(r.verdict){a[r.verdict]=(a[r.verdict]||0)+1;} return a; },{});
const ph = s.portfolio_health || {};
const kpis = [
  ['Товаров', rows.length],
  ['Avg opportunity', s.avg_opportunity_score ?? '—'],
  ['Конкуренция', s.competition_level ?? '—'],
  ['Качество', s.quality ?? '—'],
  ['Health', ph.rating ?? '—'],
  ['BUY / WATCH / SKIP', `${verdicts.BUY||0} / ${verdicts.WATCH||0} / ${verdicts.SKIP||0}`],
];
document.getElementById('kpis').innerHTML = kpis.map(
  ([l,v])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');

// ---- Charts ----
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';

const oppBuckets = [0,0,0,0,0]; // 0-20,20-40,40-60,60-80,80-100
rows.forEach(r=>{ const o=num(r.opportunity); if(o!==null) oppBuckets[Math.min(4,Math.floor(o/20))]++; });
new Chart(oppChart, { type:'bar', data:{ labels:['0-20','20-40','40-60','60-80','80-100'],
  datasets:[{ data:oppBuckets, backgroundColor:'#38bdf8' }] },
  options:{ plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true,ticks:{precision:0}}} } });

const pb = s.price_bands || {budget:0,mid:0,premium:0,luxury:0};
new Chart(priceChart, { type:'bar', data:{ labels:['Budget <$25','Mid $25-75','Premium $75-200','Luxury $200+'],
  datasets:[{ data:[pb.budget,pb.mid,pb.premium,pb.luxury], backgroundColor:['#64748b','#0ea5e9','#8b5cf6','#f59e0b'] }] },
  options:{ plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true,ticks:{precision:0}}} } });

new Chart(verdictChart, { type:'doughnut',
  data:{ labels:['BUY','WATCH','SKIP'], datasets:[{ data:[verdicts.BUY||0,verdicts.WATCH||0,verdicts.SKIP||0],
    backgroundColor:['#22c55e','#eab308','#ef4444'] }] },
  options:{ plugins:{legend:{position:'bottom'}} } });

const top = [...rows].filter(r=>num(r.monthly_sales)!==null)
  .sort((a,b)=>num(b.monthly_sales)-num(a.monthly_sales)).slice(0,10);
new Chart(salesChart, { type:'bar',
  data:{ labels:top.map(r=>(r.title||r.asin||'').slice(0,22)),
    datasets:[{ data:top.map(r=>num(r.monthly_sales)), backgroundColor:'#22c55e' }] },
  options:{ indexAxis:'y', plugins:{legend:{display:false}}, scales:{x:{beginAtZero:true}} } });

// ---- Table ----
const COLS = [
  ['ASIN','asin'],['Название','title'],['Бренд','brand'],['Opportunity','opportunity'],
  ['Вердикт','verdict'],['Цена','price'],['Volat.','volatility'],['Рейтинг','rating'],
  ['Отзывы','reviews'],['Прод./мес','monthly_sales'],['Тренд','velocity_trend'],
  ['Дни запаса','days_inventory'],['Заказать','reorder_qty'],['Stockout','stockout_risk'],
  ['Офферы','offers'],['Rank','rank'],['Drops30','drops30'],
];
let sortKey='opportunity', sortDir=-1;
document.querySelector('#tbl thead').innerHTML =
  '<tr>'+COLS.map(([l,k])=>`<th data-k="${k}">${l}</th>`).join('')+'</tr>';
document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{
  const k=th.dataset.k; sortDir = (sortKey===k)? -sortDir : -1; sortKey=k; render();
});
['q','verdictFilter','oppFilter'].forEach(id=>document.getElementById(id).oninput=render);

function render(){
  const q=document.getElementById('q').value.toLowerCase();
  const vf=document.getElementById('verdictFilter').value;
  const of=document.getElementById('oppFilter').value;
  let list = rows.filter(r=>{
    const hay=`${r.asin} ${r.title} ${r.brand}`.toLowerCase();
    if(q && !hay.includes(q)) return false;
    if(vf && r.verdict!==vf) return false;
    if(of && r.opportunity_label!==of) return false;
    return true;
  });
  list.sort((a,b)=>{
    let x=a[sortKey], y=b[sortKey];
    const nx=num(x), ny=num(y);
    if(nx!==null && ny!==null) return (nx-ny)*sortDir;
    return String(x??'').localeCompare(String(y??''))*sortDir;
  });
  const body=list.map(r=>{
    const cells=COLS.map(([l,k])=>{
      let v=r[k];
      if(k==='asin') return `<td><a href="${r.keepa_url||'#'}" target="_blank">${v||'—'}</a></td>`;
      if(k==='title') return `<td class="title"><a href="${r.url||'#'}" target="_blank">${v||'—'}</a></td>`;
      if(k==='verdict') return `<td>${v?`<span class="pill ${v}">${v}</span>`:'—'}</td>`;
      if(k==='opportunity'){ const lab=r.opportunity_label||''; const pct=Math.max(0,Math.min(100,num(v)||0));
        return `<td><div class="bar" title="${lab}"><span style="width:${pct}%"></span></div>${fmt(v)}</td>`; }
      if(k==='stockout_risk') return `<td>${v&&v!=='unknown'?`<span class="pill ${v}">${v}</span>`:'—'}</td>`;
      return `<td>${fmt(v)}</td>`;
    });
    return '<tr>'+cells.join('')+'</tr>';
  }).join('');
  document.querySelector('#tbl tbody').innerHTML = body || '<tr><td colspan="17" class="muted">Нет данных</td></tr>';
}
render();
</script>
</body>
</html>"""
