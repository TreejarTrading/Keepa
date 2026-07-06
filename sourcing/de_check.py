"""Cross-check top US/UK candidates on amazon.de (demand validation).

Takes the fetched US/UK candidate files, ranks them by monthly-net potential
(same scoring as economics.py), and fetches the same ASINs on the DE
marketplace. Products missing on DE are reported too — absence is itself a
signal (free niche vs no demand).

Keepa has no Amazon.ae coverage: UAE demand is estimated separately in the
report from US/DE proxies.

Usage:
    uv run python sourcing/de_check.py [--top 60]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from keepa_mcp import analysis, keepa_client  # noqa: E402
import economics  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="sourcing/data")
    ap.add_argument("--top", type=int, default=60)
    args = ap.parse_args()
    data_dir = Path(args.data)

    scored: list[tuple[float, str]] = []
    for f in sorted(data_dir.glob("candidates_*.json")):
        market = f.stem.split("_")[-1]
        if market == "DE":
            continue
        for rec in json.loads(f.read_text(encoding="utf-8")):
            if not economics.listed_since_ok(rec):
                continue
            row = economics.compute(rec, market)
            if row and row["verdict"] != "SKIP":
                scored.append((row["monthly_net_potential_usd"] or 0, rec["asin"]))
    scored.sort(reverse=True)
    already: set[str] = set()
    prev_records: list[dict] = []
    prev_missing: list[str] = []
    p_de, p_miss = data_dir / "candidates_DE.json", data_dir / "de_missing.json"
    if p_de.exists():
        prev_records = json.loads(p_de.read_text(encoding="utf-8"))
        already |= {r["asin"] for r in prev_records}
    if p_miss.exists():
        prev_missing = json.loads(p_miss.read_text(encoding="utf-8"))
        already |= set(prev_missing)

    seen: set[str] = set()
    asins: list[str] = []
    for _, a in scored:
        if a in seen:
            continue
        seen.add(a)
        if len(seen) > args.top:
            break
        if a not in already:
            asins.append(a)
    print(f"checking {len(asins)} new top ASINs on DE ({len(already)} already checked)")

    api = keepa_client.get_client()
    records = list(prev_records)
    for i in range(0, len(asins), 20):
        chunk = asins[i : i + 20]
        products = api.query(
            chunk, domain="DE", stats=90, rating=True, history=True, wait=True
        )
        for p in products or []:
            if not p.get("title"):
                continue  # not listed on DE
            rec = analysis.build_record(p, stats_days=90, domain="DE")
            rec["monthly_sold"] = p.get("monthlySold")
            rec["listed_since_keepa"] = p.get("listedSince")
            rec["referral_fee_percent"] = p.get("referralFeePercent")
            records.append(rec)
        print(f"DE {min(i+20, len(asins))}/{len(asins)}")

    out = data_dir / "candidates_DE.json"
    out.write_text(json.dumps(records, ensure_ascii=False, default=str), encoding="utf-8")
    found = {r["asin"] for r in records}
    missing = sorted((set(prev_missing) | set(asins)) - found)
    (data_dir / "de_missing.json").write_text(json.dumps(missing), encoding="utf-8")
    print(f"DE listed: {len(found)}; not listed on DE: {len(missing)} -> {out}")


if __name__ == "__main__":
    main()
