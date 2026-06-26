"""Unattended scheduled product search (the "every 2 days" auto mode).

Reads saved searches from ``auto_searches.json`` in the project root (see
SEARCH_GUIDE.md for the format), runs each one through the Keepa Product
Finder, applies rule-based verdicts and writes one XLSX report per search
into the Products/ folder.

Run manually or from a scheduler:

    uv run keepa-auto                 # all saved searches
    uv run keepa-auto my_file.json    # alternative config file

Schedule every 2 days at 09:00 with cron (crontab -e):

    0 9 */2 * * cd /home/andrea/KEEPA && uv run keepa-auto >> auto_search.log 2>&1
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import analysis, config, dashboard, keepa_client, reports

# build_selection keyword arguments accepted inside a search's "filters".
_FILTER_KEYS = {
    "title",
    "category_id",
    "brand",
    "min_price",
    "max_price",
    "min_rating",
    "max_sales_rank",
    "min_review_count",
    "max_offer_count",
    "min_monthly_sold",
}


def load_searches(searches_file: str | Path | None = None) -> list[dict[str, Any]]:
    """Load and validate the saved-search list from the JSON config file."""
    path = Path(searches_file).expanduser() if searches_file else config.AUTO_SEARCH_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Auto-search config not found: {path}. Create it from the example in "
            "SEARCH_GUIDE.md (section 'Авторежим')."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    searches = data.get("searches") if isinstance(data, dict) else data
    if not isinstance(searches, list) or not searches:
        raise ValueError(f"{path}: expected a non-empty 'searches' list.")

    cleaned: list[dict[str, Any]] = []
    for i, raw in enumerate(searches):
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: search #{i + 1} must be an object.")
        filters = raw.get("filters") or {}
        unknown = set(filters) - _FILTER_KEYS
        if unknown:
            raise ValueError(
                f"{path}: search {raw.get('name', i + 1)!r} has unknown filter(s) "
                f"{sorted(unknown)}; allowed: {sorted(_FILTER_KEYS)} "
                "(raw Keepa keys go into 'extra_filters')."
            )
        cleaned.append(
            {
                "name": str(raw.get("name") or f"search_{i + 1}"),
                "domain": str(raw.get("domain") or config.DEFAULT_DOMAIN),
                "filters": filters,
                "extra_filters": raw.get("extra_filters") or {},
                "limit": int(raw.get("limit") or 15),
            }
        )
    return cleaned


def run_search(search: dict[str, Any]) -> dict[str, Any]:
    """Execute one saved search and write its XLSX report. Returns a summary."""
    domain = keepa_client.normalize_domain(search["domain"])
    selection = keepa_client.build_selection(
        **search["filters"], extra_filters=search["extra_filters"]
    )
    asins = keepa_client.product_finder(selection, domain=domain, limit=search["limit"])
    if not asins:
        return {"name": search["name"], "domain": domain, "asins_found": 0, "saved_to": None}

    products = keepa_client.query_products(asins, domain=domain)
    records = [
        analysis.auto_verdict(analysis.build_record(p, domain=domain)) for p in products
    ]
    summary = (
        f"AUTO {datetime.now():%Y-%m-%d %H:%M} | market={domain} | "
        f"filters={json.dumps(search['filters'], ensure_ascii=False)} | "
        f"extra={json.dumps(search['extra_filters'], ensure_ascii=False)}"
    )
    report_name = f"auto_{search['name']}_{domain}"
    path = reports.generate_report(records, report_name=report_name, query_summary=summary)
    dash_path = dashboard.generate_dashboard(
        records, dashboard_name=report_name, query_summary=summary
    )
    verdicts = {"BUY": 0, "WATCH": 0, "SKIP": 0}
    for r in records:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    return {
        "name": search["name"],
        "domain": domain,
        "asins_found": len(asins),
        "verdicts": verdicts,
        "saved_to": str(path),
        "dashboard": str(dash_path),
    }


def run_all(searches_file: str | Path | None = None) -> dict[str, Any]:
    """Run every saved search; never let one failure kill the whole batch."""
    searches = load_searches(searches_file)
    runs: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for search in searches:
        try:
            runs.append(run_search(search))
        except Exception as exc:  # noqa: BLE001 - report and continue
            errors.append({"name": search["name"], "error": f"{type(exc).__name__}: {exc}"})
    return {
        "started": datetime.now().isoformat(timespec="seconds"),
        "searches_total": len(searches),
        "runs": runs,
        "errors": errors,
        "output_dir": str(config.OUTPUT_DIR),
    }


def main() -> int:
    """Console-script entry point for cron / manual runs."""
    searches_file = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        result = run_all(searches_file)
    except Exception as exc:  # noqa: BLE001 - cron-friendly plain error
        print(f"[X] keepa-auto failed: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] and not result["runs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
