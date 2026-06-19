"""Generate XLSX purchase-analysis reports into the Products/ folder."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import config, sourcing

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_VERDICT_FILLS = {
    "BUY": PatternFill("solid", fgColor="C6EFCE"),
    "WATCH": PatternFill("solid", fgColor="FFEB9C"),
    "SKIP": PatternFill("solid", fgColor="FFC7CE"),
    # China-sourcing verdicts (Russian)
    "ЗАКУПАТЬ": PatternFill("solid", fgColor="C6EFCE"),
    "ПРОВЕРИТЬ": PatternFill("solid", fgColor="FFEB9C"),
    "ОТКАЗ": PatternFill("solid", fgColor="FFC7CE"),
}

# (header, accessor) — accessor is a dotted path into the analysis record.
_COLUMNS: list[tuple[str, str]] = [
    ("ASIN", "asin"),
    ("Title", "title"),
    ("Brand", "brand"),
    ("Manufacturer", "manufacturer"),
    ("Category", "category_top"),
    ("Rating", "metrics.reviews.rating_current"),
    ("Reviews", "metrics.reviews.review_count_current"),
    ("Review/mo", "metrics.demand.review_velocity_per_month"),
    ("Monthly sold", "metrics.demand.monthly_sold_estimate"),
    ("Price (New)", "metrics.pricing.new.current"),
    ("New avg", "metrics.pricing.new.avg"),
    ("New min", "metrics.pricing.new.min"),
    ("New max", "metrics.pricing.new.max"),
    ("Price volat.", "metrics.pricing.new.volatility"),
    ("Buy Box", "metrics.pricing.buy_box.current"),
    ("BB=Amazon", "metrics.competition.buy_box_is_amazon"),
    ("Offers", "metrics.competition.offer_count.current"),
    ("Sales rank", "metrics.sales_rank.current"),
    ("Rank drops/30d", "metrics.sales_rank.drops_30d"),
    ("Rank drops/90d", "metrics.sales_rank.drops_90d"),
    ("Referral %", "metrics.amazon_fees.referral_pct"),
    ("FBA fee", "metrics.amazon_fees.fba_fee"),
    ("Amazon fees", "metrics.amazon_fees.total_fees"),
    ("Net after fees", "metrics.amazon_fees.net_proceeds"),
    ("Verdict", "verdict"),
    ("Confidence", "confidence"),
    ("Rationale", "rationale"),
    ("Amazon URL", "url"),
]


def _dig(record: dict[str, Any], path: str) -> Any:
    """Resolve a dotted accessor against a record, tolerating missing keys."""
    if path == "category_top":
        tree = record.get("category_tree") or []
        return tree[-1] if tree else None
    cur: Any = record
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _slugify(name: str) -> str:
    name = re.sub(r"[^\w\-. ]+", "", name, flags=re.UNICODE).strip()
    name = re.sub(r"\s+", "_", name)
    return name or "report"


def _autosize(ws, max_width: int = 60) -> None:
    for col_cells in ws.columns:
        length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=0)
        letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[letter].width = min(max(length + 2, 10), max_width)


def generate_report(
    records: list[dict[str, Any]],
    *,
    report_name: str | None = None,
    query_summary: str | None = None,
) -> Path:
    """Write an XLSX report and return its path.

    ``records`` are analysis records from :func:`analysis.build_record`,
    optionally enriched by Claude with ``verdict`` / ``confidence`` /
    ``rationale`` keys.
    """
    out_dir = config.ensure_output_dir()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = _slugify(report_name) if report_name else "keepa_report"
    path = out_dir / f"{base}_{stamp}.xlsx"

    wb = Workbook()

    # --- Sheet 1: Overview / decision table -----------------------------
    ws = wb.active
    ws.title = "Анализ"
    headers = [h for h, _ in _COLUMNS]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"

    verdict_col = headers.index("Verdict") + 1
    for rec in records:
        row = []
        for header, accessor in _COLUMNS:
            val = _dig(rec, accessor)
            if header == "Referral %" and isinstance(val, (int, float)):
                row.append(f"{val * 100:.1f}%")
            else:
                row.append(_format(val))
        ws.append(row)
        verdict = str(rec.get("verdict", "")).upper()
        if verdict in _VERDICT_FILLS:
            ws.cell(row=ws.max_row, column=verdict_col).fill = _VERDICT_FILLS[verdict]
    _autosize(ws)

    # --- Sheet 2: Specs & customer-need detail --------------------------
    ws2 = wb.create_sheet("Характеристики")
    ws2.append(["ASIN", "Title", "Features", "Description", "Dimensions", "Weight (g)", "Variations"])
    for cell in ws2[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for rec in records:
        dims = rec.get("package_dimensions") or {}
        dim_str = " x ".join(
            str(dims.get(k)) for k in ("length", "width", "height") if dims.get(k)
        )
        ws2.append([
            rec.get("asin"),
            rec.get("title"),
            "\n".join(rec.get("features") or [])[:32000],
            (rec.get("description") or "")[:32000],
            dim_str,
            rec.get("package_weight_g"),
            rec.get("variation_count"),
        ])
    _autosize(ws2, max_width=80)

    # --- Sheet 3: Run metadata ------------------------------------------
    ws3 = wb.create_sheet("Сводка")
    ws3.append(["Generated", datetime.now().isoformat(timespec="seconds")])
    ws3.append(["Products analysed", len(records)])
    ws3.append(["Query / context", query_summary or "—"])
    counts = {"BUY": 0, "WATCH": 0, "SKIP": 0}
    for rec in records:
        v = str(rec.get("verdict", "")).upper()
        if v in counts:
            counts[v] += 1
    ws3.append(["BUY", counts["BUY"]])
    ws3.append(["WATCH", counts["WATCH"]])
    ws3.append(["SKIP", counts["SKIP"]])
    ws3.column_dimensions["A"].width = 22
    ws3.column_dimensions["B"].width = 60

    wb.save(path)
    return path


def _format(value: Any) -> Any:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value


# --- China-sourcing report (Amazon ↔ supplier comparison, Russian) -----------

def _format_kind(value: Any, kind: str) -> Any:
    """Format a value for the sourcing sheet according to its column kind."""
    if value is None or value == "":
        return None
    if kind == "bool":
        if isinstance(value, str):
            return value
        return "Да" if value else "Нет"
    if kind == "pct":
        try:
            return f"{float(value) * 100:.1f}%"
        except (TypeError, ValueError):
            return value
    if kind == "money":
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return value
    if kind == "int":
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return value
    return value


def generate_sourcing_report(
    plan: dict[str, Any],
    *,
    report_name: str | None = None,
    query_summary: str | None = None,
) -> Path:
    """Write the Amazon ↔ China-supplier comparison XLSX and return its path.

    ``plan`` is the structure returned by :func:`sourcing.build_plan` (rows with
    economics, scenarios and verdicts), optionally with Claude's overridden
    ``verdict`` / ``confidence`` / ``rationale``. The workbook has four sheets,
    all in Russian: Сопоставление (comparison), Сценарии (per-volume what-ifs),
    Пояснения (what every column means), Сводка (run summary).
    """
    out_dir = config.ensure_output_dir()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = _slugify(report_name) if report_name else "sourcing_report"
    path = out_dir / f"{base}_{stamp}.xlsx"

    rows = plan.get("rows") or []
    currency = plan.get("currency") or "USD"
    columns = sourcing.REPORT_COLUMNS

    wb = Workbook()

    # --- Sheet 1: Comparison --------------------------------------------
    ws = wb.active
    ws.title = "Сопоставление"
    headers = [c["header"] for c in columns]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"

    verdict_col = headers.index("Вердикт") + 1 if "Вердикт" in headers else None
    for row in rows:
        ws.append([_format_kind(row.get(c["key"]), c["kind"]) for c in columns])
        verdict = str(row.get("verdict", "")).upper()
        if verdict_col and verdict in _VERDICT_FILLS:
            ws.cell(row=ws.max_row, column=verdict_col).fill = _VERDICT_FILLS[verdict]
    _autosize(ws, max_width=42)

    # --- Sheet 2: Per-volume scenarios ----------------------------------
    ws2 = wb.create_sheet("Сценарии")
    ws2.append([f"Сценарии по объёму заказа (валюта: {currency}). "
                "Как меняются себестоимость, маржа и ROI при разных ценовых уровнях MOQ."])
    ws2.append([
        "ASIN", "Товар", "Площадка", "Поставщик", "Ценовой уровень (MOQ)",
        "Кол-во", "Цена за ед.", "Себестоимость (landed)", "Прибыль за ед.",
        "Маржа, %", "ROI, %",
    ])
    for cell in ws2[2]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws2.freeze_panes = "A3"
    for row in rows:
        for s in row.get("scenarios") or []:
            ws2.append([
                row.get("asin"), row.get("title"), row.get("platform"),
                row.get("supplier_name"), s.get("tier_range"), s.get("qty"),
                _format_kind(s.get("unit_cost"), "money"),
                _format_kind(s.get("landed_cost"), "money"),
                _format_kind(s.get("profit_per_unit"), "money"),
                _format_kind(s.get("margin_pct"), "pct"),
                _format_kind(s.get("roi_pct"), "pct"),
            ])
    _autosize(ws2, max_width=42)

    # --- Sheet 3: Column explanations (problem #5) ----------------------
    ws3 = wb.create_sheet("Пояснения")
    ws3.append(["Колонка", "Что означает / как считается"])
    for cell in ws3[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for header, doc in sourcing.COLUMN_DOCS:
        ws3.append([header, doc])
    ws3.append(["", ""])
    ws3.append(["Методика расчёта", ""])
    g = sourcing.SOURCING_GUIDANCE
    for line in [
        f"Базовая валюта отчёта: {currency}. Курсы (fx): {plan.get('fx') or '—'}.",
        f"Себестоимость (landed) = цена за ед. + логистика + пошлина "
        f"(ставка пошлины: {(plan.get('duty_pct') or 0) * 100:.0f}%).",
        f"Логистика за ед. = вес (кг) × ставка {plan.get('freight_per_kg') or '—'} {currency}/кг "
        "(или явная ставка поставщика).",
        "Комиссия Amazon = реферальная (из Keepa) + сбор FBA (из Keepa). "
        "Маржа = прибыль / цена продажи; ROI = прибыль / себестоимость.",
        f"Вердикт ЗАКУПАТЬ: {g['verdict_thresholds']['ЗАКУПАТЬ']}.",
        f"Вердикт ОТКАЗ: {g['verdict_thresholds']['ОТКАЗ']}.",
        "Поиск поставщика ведётся не только на Alibaba: "
        + ", ".join(p["name"] for p in g["platforms"]) + ".",
    ]:
        ws3.append([line, ""])
    ws3.column_dimensions["A"].width = 40
    ws3.column_dimensions["B"].width = 90
    for r in ws3.iter_rows():
        r[0].alignment = Alignment(vertical="top", wrap_text=True)
        r[1].alignment = Alignment(vertical="top", wrap_text=True)

    # --- Sheet 4: Run summary -------------------------------------------
    ws4 = wb.create_sheet("Сводка")
    ws4.append(["Сформировано", datetime.now().isoformat(timespec="seconds")])
    ws4.append(["Строк сопоставления", len(rows)])
    ws4.append(["Базовая валюта", currency])
    ws4.append(["Запрос / контекст", query_summary or "—"])
    counts = {"ЗАКУПАТЬ": 0, "ПРОВЕРИТЬ": 0, "ОТКАЗ": 0}
    for row in rows:
        v = str(row.get("verdict", "")).upper()
        if v in counts:
            counts[v] += 1
    for label in ("ЗАКУПАТЬ", "ПРОВЕРИТЬ", "ОТКАЗ"):
        ws4.append([label, counts[label]])
    ws4.column_dimensions["A"].width = 24
    ws4.column_dimensions["B"].width = 60

    wb.save(path)
    return path
