"""Fetch new-listing product candidates (Feb 2026+) from Keepa for sourcing.

Runs Product Finder searches per market/category, dedupes ASINs, fetches
full product records in cheap batches (no live offers) and dumps raw JSON
for the economics stage (sourcing/economics.py).

Usage:
    uv run python sourcing/fetch_candidates.py [--out DIR] [--budget N]

Filters (the sourcing brief):
    - listing tracked since >= 2026-02-01 (trackingSince_gte, Keepa minutes)
    - rating >= 4.1, proven sales (monthlySold), price band 15-70 USD / 12-55 GBP
    - categories: Home & Kitchen, Tools & Home Improvement (DIY),
      Patio/Lawn/Garden, Office Products + storage/organizer title searches
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keepa_mcp import analysis, keepa_client  # noqa: E402

# 2026-02-01 00:00 UTC in Keepa minutes: unix_sec/60 - 21564000
FEB_2026_KEEPA = int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp() // 60) - 21_564_000

US_SEARCHES = [
    {"name": "US_home_kitchen", "category_id": 1055398, "limit": 50},
    {"name": "US_tools_diy", "category_id": 228013, "limit": 50},
    {"name": "US_garden", "category_id": 2972638011, "limit": 50},
    {"name": "US_office", "category_id": 1064954, "limit": 50},
    {"name": "US_storage", "category_id": 1055398, "title": "storage", "limit": 25},
    {"name": "US_organizer", "category_id": 1055398, "title": "organizer", "limit": 25},
]

# UK root ids resolved dynamically by name (ids differ per marketplace).
UK_ROOTS = {
    "UK_home_kitchen": "Home & Kitchen",
    "UK_tools_diy": "DIY & Tools",
    "UK_garden": "Garden & Outdoors",
    "UK_office": "Stationery & Office Supplies",
}
UK_LIMIT = 35

BASE = {
    "US": {"min_price": 15, "max_price": 70, "min_monthly_sold": 100},
    "UK": {"min_price": 12, "max_price": 55, "min_monthly_sold": 50},
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def tokens() -> int:
    st = keepa_client.tokens_left()
    return st.get("tokens_left") or 0


def resolve_uk_roots() -> dict[str, int]:
    out: dict[str, int] = {}
    for name, root_name in UK_ROOTS.items():
        cats = keepa_client.search_categories(root_name, domain="UK")
        best = None
        for cid, c in (cats or {}).items():
            cname = (c.get("name") or "").strip().lower()
            products = c.get("productCount") or 0
            exact = cname == root_name.lower()
            if exact or root_name.lower() in cname or cname in root_name.lower():
                key = (1 if exact else 0, products)
                if best is None or key > best[1]:
                    best = (int(cid), key, c.get("name"))
        if best:
            out[name] = best[0]
            log(f"UK root '{root_name}' -> {best[0]} ({best[2]}, {best[1]} products)")
        else:
            log(f"UK root '{root_name}' NOT FOUND, skipping")
    return out


def run_search(name: str, domain: str, category_id: int, limit: int, title: str | None) -> list[str]:
    base = BASE[domain]
    sel = keepa_client.build_selection(
        title=title,
        min_price=base["min_price"],
        max_price=base["max_price"],
        min_rating=4.1,
        min_monthly_sold=base["min_monthly_sold"],
        sort_by_sales_rank=False,
        extra_filters={
            # the keepa package validates rootCategory as str / list[str]
            "rootCategory": str(category_id),
            "trackingSince_gte": FEB_2026_KEEPA,
            "sort": [["monthlySold", "desc"]],
        },
    )
    try:
        asins = keepa_client.product_finder(sel, domain=domain, limit=limit)
    except Exception as exc:  # noqa: BLE001
        log(f"{name}: finder FAILED: {exc}")
        return []
    log(f"{name}: {len(asins)} ASINs (tokens left ~{tokens()})")
    return asins


def fetch_records(asins: list[str], domain: str, batch: int = 20) -> list[dict]:
    """Fetch product records without live offers (cheap: ~2 tokens/ASIN)."""
    api = keepa_client.get_client()
    records: list[dict] = []
    for i in range(0, len(asins), batch):
        chunk = asins[i : i + batch]
        try:
            products = api.query(
                chunk,
                domain=keepa_client.normalize_domain(domain),
                stats=90,
                rating=True,
                history=True,
                wait=True,
            )
        except Exception as exc:  # noqa: BLE001
            log(f"fetch {domain} batch {i//batch}: FAILED: {exc}")
            continue
        for p in products or []:
            rec = analysis.build_record(p, stats_days=90, domain=domain)
            rec["monthly_sold"] = p.get("monthlySold")
            rec["listed_since_keepa"] = p.get("listedSince")
            rec["tracking_since_keepa"] = p.get("trackingSince")
            rec["referral_fee_percent"] = p.get("referralFeePercent") or p.get(
                "referralFeePercentage"
            )
            rec["sales_rank_current"] = (rec.get("metrics", {}).get("sales_rank") or {}).get(
                "current"
            )
            records.append(rec)
        log(f"fetch {domain}: {min(i+batch, len(asins))}/{len(asins)} (tokens ~{tokens()})")
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sourcing/data")
    ap.add_argument("--markets", default="US,UK")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    markets = [m.strip().upper() for m in args.markets.split(",") if m.strip()]

    log(f"start; tokens ~{tokens()}; feb2026 keepa minute = {FEB_2026_KEEPA}")

    plan: list[tuple[str, str, int, int, str | None]] = []
    if "US" in markets:
        for s in US_SEARCHES:
            plan.append((s["name"], "US", s["category_id"], s["limit"], s.get("title")))
    if "UK" in markets:
        for name, cid in resolve_uk_roots().items():
            plan.append((name, "UK", cid, UK_LIMIT, None))

    seen: dict[str, set[str]] = {m: set() for m in markets}
    sources: dict[str, dict[str, list[str]]] = {m: {} for m in markets}
    for name, domain, cid, limit, title in plan:
        asins = run_search(name, domain, cid, limit, title)
        fresh = [a for a in asins if a not in seen[domain]]
        seen[domain].update(fresh)
        sources[domain][name] = asins

    for domain in markets:
        asin_list = sorted(seen[domain])
        log(f"{domain}: {len(asin_list)} unique ASINs to fetch")
        records = fetch_records(asin_list, domain)
        # tag each record with the searches that surfaced it
        by_search = {
            a: [s for s, lst in sources[domain].items() if a in lst] for a in asin_list
        }
        for r in records:
            r["found_by"] = by_search.get(r.get("asin"), [])
        path = out_dir / f"candidates_{domain}.json"
        path.write_text(json.dumps(records, ensure_ascii=False, default=str), encoding="utf-8")
        log(f"{domain}: wrote {len(records)} records -> {path}")

    log(f"done; tokens ~{tokens()}")


if __name__ == "__main__":
    main()
