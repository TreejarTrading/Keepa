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
# Active hyperlink styling for the clickable ASIN cell (Excel "Hyperlink" blue).
_LINK_FONT = Font(color="0563C1", underline="single")
_VERDICT_FILLS = {
    "BUY": PatternFill("solid", fgColor="C6EFCE"),
    "WATCH": PatternFill("solid", fgColor="FFEB9C"),
    "SKIP": PatternFill("solid", fgColor="FFC7CE"),
}

# (header, accessor) — accessor is a dotted path into the analysis record.
_COLUMNS: list[tuple[str, str]] = [
    ("ASIN", "asin"),
    ("Title", "title"),
    ("Brand", "brand"),
    ("Category", "category_top"),
    ("Bucket", "discovery.tags"),
    ("Momentum", "discovery.momentum_score"),
    ("Rank trend %", "metrics.sales_rank.trend_pct"),
    ("New?", "discovery.is_new"),
    ("Rating", "metrics.reviews.rating_current"),
    ("Reviews", "metrics.reviews.review_count_current"),
    ("Monthly sold", "metrics.demand.monthly_sold_estimate"),
    ("Price (New)", "metrics.pricing.new.current"),
    ("New avg", "metrics.pricing.new.avg"),
    ("Price volat.", "metrics.pricing.new.volatility"),
    ("BB=Amazon", "metrics.competition.buy_box_is_amazon"),
    ("Offers", "metrics.competition.offer_count.current"),
    ("Sales rank", "metrics.sales_rank.current"),
    ("Rank drops/30d", "metrics.sales_rank.drops_30d"),
    ("Verdict", "verdict"),
    ("Confidence", "confidence"),
    ("Rationale", "rationale"),
    ("Alibaba", "alibaba_keywords"),
    ("Image", "image_label"),
]
# Columns whose cell text links somewhere: header -> record field holding the
# URL. The ASIN links to Amazon; Alibaba links to a supplier search; Image
# opens the main product image. There is intentionally no plain-text URL column.
_LINK_COLUMNS: dict[str, str] = {
    "ASIN": "url",
    "Alibaba": "alibaba_url",
    "Image": "image",
}


def _dig(record: dict[str, Any], path: str) -> Any:
    """Resolve a dotted accessor against a record, tolerating missing keys."""
    if path == "category_top":
        tree = record.get("category_tree") or []
        return tree[-1] if tree else None
    if path == "image_label":
        # Short clickable label instead of a long raw image URL.
        return "image ↗" if record.get("image") else None
    cur: Any = record
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _linkify(cell, url: str | None) -> None:
    """Turn ``cell`` into an active (clickable) Amazon hyperlink.

    Used to make every ASIN cell a live link to its Amazon product page. If no
    URL is available the cell is left as plain text.
    """
    if url:
        cell.hyperlink = url
        cell.font = _LINK_FONT


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
    link_cols = {h: headers.index(h) + 1 for h in _LINK_COLUMNS if h in headers}
    for rec in records:
        row = [_format(_dig(rec, path)) for _, path in _COLUMNS]
        ws.append(row)
        # Active links: ASIN→Amazon, Alibaba→supplier search, Image→main image.
        for header, col in link_cols.items():
            _linkify(ws.cell(row=ws.max_row, column=col), rec.get(_LINK_COLUMNS[header]))
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
        # Keep the ASIN clickable here too, for consistency with the main sheet.
        _linkify(ws2.cell(row=ws2.max_row, column=1), rec.get("url"))
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


# --- DOCX buyer brief --------------------------------------------------------
# A visual, hand-to-the-buyer document: per-product cards with key demand
# metrics, the verdict, a clickable Amazon link and a clickable Alibaba
# supplier-search link (plus an embedded thumbnail when reachable).


def _docx_hyperlink(paragraph, url: str, text: str) -> None:
    """Append a clickable hyperlink run to a python-docx paragraph.

    python-docx has no first-class hyperlink API, so we build the OOXML element
    by hand and register an external relationship.
    """
    from docx.oxml.ns import qn
    from docx.oxml.shared import OxmlElement

    r_id = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    rpr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    run.append(rpr)
    text_el = OxmlElement("w:t")
    text_el.text = text
    run.append(text_el)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _fetch_image(url: str, timeout: float = 4.0):
    """Best-effort thumbnail download; returns a BytesIO or None (never raises)."""
    import io

    try:
        import httpx

        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and resp.content:
            return io.BytesIO(resp.content)
    except Exception:
        return None
    return None


def generate_docx_report(
    records: list[dict[str, Any]],
    *,
    report_name: str | None = None,
    query_summary: str | None = None,
    embed_images: bool = True,
) -> Path:
    """Write a visual DOCX buyer brief and return its path."""
    from docx import Document
    from docx.shared import Inches

    out_dir = config.ensure_output_dir()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = _slugify(report_name) if report_name else "buyer_report"
    path = out_dir / f"{base}_{stamp}.docx"

    doc = Document()
    doc.add_heading("Sourcing report — purchasing brief", level=0)
    intro = doc.add_paragraph()
    intro.add_run(
        f"Generated {datetime.now():%Y-%m-%d %H:%M} · {len(records)} products"
    ).italic = True
    if query_summary:
        doc.add_paragraph(query_summary)

    buckets: dict[str, int] = {}
    verdicts: dict[str, int] = {}
    for rec in records:
        for tag in (rec.get("discovery") or {}).get("tags") or []:
            buckets[tag] = buckets.get(tag, 0) + 1
        v = str(rec.get("verdict") or "").upper()
        if v:
            verdicts[v] = verdicts.get(v, 0) + 1
    if buckets:
        doc.add_paragraph(
            "Buckets — " + ", ".join(f"{k}: {n}" for k, n in sorted(buckets.items()))
        )
    if verdicts:
        doc.add_paragraph(
            "Verdicts — " + ", ".join(f"{k}: {n}" for k, n in verdicts.items())
        )
    doc.add_paragraph(
        "US is the lead market; these are candidates to resell in DE/AE. Each "
        "product below links to its Amazon page and to an Alibaba supplier search."
    )

    for i, rec in enumerate(records, 1):
        doc.add_heading(f"{i}. {rec.get('title') or rec.get('asin') or 'Product'}", level=1)
        disc = rec.get("discovery") or {}
        tags = ", ".join(disc.get("tags") or [])
        subtitle = doc.add_paragraph()
        subtitle.add_run(f"{rec.get('brand') or '—'}  ·  {tags}").bold = True

        if embed_images and rec.get("image"):
            buf = _fetch_image(rec["image"])
            if buf is not None:
                try:
                    doc.add_picture(buf, width=Inches(1.6))
                except Exception:
                    pass

        m = rec.get("metrics") or {}
        rk = m.get("sales_rank") or {}
        pr = (m.get("pricing") or {}).get("new") or {}
        rv = m.get("reviews") or {}
        dm = m.get("demand") or {}
        cp = m.get("competition") or {}
        rows = [
            ("Price (New)", pr.get("current")),
            ("Rating / reviews", f"{rv.get('rating_current')} / {rv.get('review_count_current')}"),
            ("Monthly sold", dm.get("monthly_sold_estimate")),
            ("Sales rank (now)", rk.get("current")),
            ("Rank trend %", rk.get("trend_pct")),
            ("Rank drops / 30d", rk.get("drops_30d")),
            ("Offers", (cp.get("offer_count") or {}).get("current")),
            ("Momentum score", disc.get("momentum_score")),
        ]
        table = doc.add_table(rows=0, cols=2)
        try:
            table.style = "Light Grid Accent 1"
        except Exception:
            pass
        for label, val in rows:
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = "" if val is None else str(val)

        if rec.get("verdict"):
            verdict_p = doc.add_paragraph()
            verdict_p.add_run(
                f"Verdict: {rec['verdict']} ({rec.get('confidence', '')}) — "
                f"{rec.get('rationale', '')}"
            ).italic = True

        links = doc.add_paragraph()
        if rec.get("url"):
            _docx_hyperlink(links, rec["url"], "Amazon ↗")
            links.add_run("      ")
        if rec.get("alibaba_url"):
            _docx_hyperlink(
                links, rec["alibaba_url"],
                f"Alibaba: {rec.get('alibaba_keywords') or 'search'} ↗",
            )

    doc.save(path)
    return path


def generate_reports(
    records: list[dict[str, Any]],
    *,
    report_name: str | None = None,
    query_summary: str | None = None,
    formats: tuple[str, ...] = ("xlsx",),
    embed_images: bool = True,
) -> dict[str, str]:
    """Write the report in one or more formats; return ``{format: path}``."""
    out: dict[str, str] = {}
    for fmt in formats:
        if fmt == "xlsx":
            out["xlsx"] = str(
                generate_report(records, report_name=report_name, query_summary=query_summary)
            )
        elif fmt == "docx":
            out["docx"] = str(
                generate_docx_report(
                    records,
                    report_name=report_name,
                    query_summary=query_summary,
                    embed_images=embed_images,
                )
            )
    return out
