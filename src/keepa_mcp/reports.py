"""Generate XLSX purchase-analysis reports into the Products/ folder."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import config

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_VERDICT_FILLS = {
    "BUY": PatternFill("solid", fgColor="C6EFCE"),
    "WATCH": PatternFill("solid", fgColor="FFEB9C"),
    "SKIP": PatternFill("solid", fgColor="FFC7CE"),
}
# China-sourcing match classification colours (EXACT = green, SIMILAR = amber).
_MATCH_FILLS = {
    "EXACT": PatternFill("solid", fgColor="C6EFCE"),
    "SIMILAR": PatternFill("solid", fgColor="FFEB9C"),
}

# (header, accessor) — accessor is a dotted path into the analysis record.
_COLUMNS: list[tuple[str, str]] = [
    ("ASIN", "asin"),
    ("Title", "title"),
    ("Brand", "brand"),
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
        row = [_format(_dig(rec, path)) for _, path in _COLUMNS]
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


_SOURCING_COLUMNS = [
    "Product", "ASIN", "Amazon price", "Amazon cur",
    "Platform", "Supplier", "China title", "Match", "Score", "Img✓",
    "Unit price", "Offer cur", "Unit USD", "Landed USD", "Margin %", "MOQ", "URL",
]


def _pct(value: Any) -> Any:
    """Format a 0-1 fraction as a percent string, else pass through."""
    if isinstance(value, (int, float)):
        return f"{value * 100:.0f}%"
    return value


def _offer_china_title(offer: dict[str, Any]) -> Any:
    title = offer.get("title_en") or offer.get("title")
    return (str(title)[:200]) if title else None


def generate_sourcing_report(
    results: list[dict[str, Any]],
    *,
    report_name: str | None = None,
    query_summary: str | None = None,
) -> Path:
    """Write a China-sourcing XLSX report and return its path.

    ``results`` are :func:`china_sourcing.rank_offers`-shaped dicts (one per
    product): a product label, the Amazon reference price, and the China offers
    enriched with EXACT/SIMILAR match classification and margin estimates.
    Two sheets: Сорсинг (every offer) and Сводка (totals + best offer per
    product).
    """
    out_dir = config.ensure_output_dir()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = _slugify(report_name) if report_name else "china_sourcing"
    path = out_dir / f"{base}_{stamp}.xlsx"

    wb = Workbook()

    # --- Sheet 1: every offer -------------------------------------------
    ws = wb.active
    ws.title = "Сорсинг"
    ws.append(_SOURCING_COLUMNS)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    match_col = _SOURCING_COLUMNS.index("Match") + 1

    for res in results:
        product = res.get("product")
        asin = res.get("asin")
        ref_price = res.get("reference_price")
        ref_cur = res.get("reference_currency") or "USD"
        offers = res.get("offers") or []
        if not offers:
            ws.append([product, asin, _format(ref_price), ref_cur,
                       None, None, "— no China offers found —"])
            continue
        for off in offers:
            ws.append([
                product, asin, _format(ref_price), ref_cur,
                off.get("platform"), off.get("supplier"), _offer_china_title(off),
                off.get("match_type"), _format(off.get("match_score")),
                "Yes" if off.get("image_confirmed") else "No",
                _format(off.get("unit_price")), off.get("currency"),
                _format(off.get("unit_price_usd")), _format(off.get("landed_cost_usd")),
                _pct(off.get("margin_pct")), off.get("moq"), off.get("url"),
            ])
            match = str(off.get("match_type", "")).upper()
            if match in _MATCH_FILLS:
                ws.cell(row=ws.max_row, column=match_col).fill = _MATCH_FILLS[match]
    _autosize(ws, max_width=70)

    # --- Sheet 2: summary / best per product ----------------------------
    ws2 = wb.create_sheet("Сводка")
    ws2.append(["Generated", datetime.now().isoformat(timespec="seconds")])
    ws2.append(["Products", len(results)])
    ws2.append(["Total offers", sum(len(r.get("offers") or []) for r in results)])
    ws2.append(["With EXACT match", sum(1 for r in results if r.get("best_exact"))])
    ws2.append(["SIMILAR only",
                sum(1 for r in results if not r.get("best_exact") and r.get("best_similar"))])
    ws2.append(["No China match",
                sum(1 for r in results if not r.get("offers"))])
    ws2.append(["Query / context", query_summary or "—"])
    ws2.append([])

    head = ["Product", "ASIN", "Amazon price",
            "Best EXACT landed USD", "EXACT platform",
            "Best SIMILAR landed USD", "SIMILAR platform", "Best margin %"]
    ws2.append(head)
    for cell in ws2[ws2.max_row]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for res in results:
        be = res.get("best_exact") or {}
        bs = res.get("best_similar") or {}
        best_margin = be.get("margin_pct")
        if best_margin is None:
            best_margin = bs.get("margin_pct")
        ws2.append([
            res.get("product"), res.get("asin"), _format(res.get("reference_price")),
            _format(be.get("landed_cost_usd")), be.get("platform"),
            _format(bs.get("landed_cost_usd")), bs.get("platform"),
            _pct(best_margin),
        ])
    _autosize(ws2, max_width=70)

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
