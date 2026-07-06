#!/usr/bin/env python3
"""Collect Keepa data: 5 categories x US/UK/DE, bestsellers + new (since Feb 2026).

Idempotent: skips query files that already exist. Waits for token refill.
Output: JSON files in DATA_DIR, progress log to stdout.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

KEY = os.environ["KEEPA_API_KEY"]
BASE = "https://api.keepa.com"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Keepa minutes for 2026-02-01 00:00 UTC: unix_min - 21564000
FEB_2026 = 1769904000 // 60 - 21564000  # = 7934400

DOMAINS = {"US": 1, "UK": 2, "DE": 3}

CATEGORIES = [
    {
        "slug": "seat_cushion",
        "kw": {"US": "seat cushion", "UK": "seat cushion", "DE": "Sitzkissen"},
        "min_price": 15,
    },
    {
        "slug": "ice_maker",
        "kw": {"US": "ice maker", "UK": "ice maker", "DE": "Eiswürfelmaschine"},
        "min_price": 45,
    },
    {
        "slug": "desk_pad",
        "kw": {"US": "desk pad", "UK": "desk mat", "DE": "Schreibtischunterlage"},
        "min_price": 7,
    },
    {
        "slug": "chair_mat",
        "kw": {"US": "office chair mat", "UK": "chair mat floor", "DE": "Bodenschutzmatte"},
        "min_price": 18,
    },
    {
        "slug": "shoe_rack",
        "kw": {"US": "shoe rack", "UK": "shoe rack", "DE": "Schuhregal"},
        "min_price": 14,
    },
]

TOP_N = 12   # products fetched per category-market (bestsellers)
NEW_N = 8   # products fetched per category-market (new since Feb 2026)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def tokens_left():
    r = requests.get(f"{BASE}/token", params={"key": KEY}, timeout=30)
    r.raise_for_status()
    return r.json()["tokensLeft"]


def wait_tokens(need):
    while True:
        left = tokens_left()
        if left >= need:
            return left
        deficit = need - left
        sleep_s = 40 if deficit <= 60 else min(deficit / 20 * 60 * 0.5, 300)
        log(f"tokens {left}, need {need}, sleeping {int(sleep_s)}s")
        time.sleep(sleep_s)


def finder(domain_id, selection, cost=10):
    wait_tokens(cost + 5)
    r = requests.post(
        f"{BASE}/query", params={"key": KEY, "domain": domain_id},
        json=selection, timeout=120,
    )
    j = r.json()
    if "error" in j and j["error"]:
        raise RuntimeError(f"finder error: {j['error']}")
    log(f"  finder tokensLeft={j.get('tokensLeft')}")
    return j.get("asinList", [])


def products(domain_id, asins, with_rating):
    if not asins:
        return []
    cost = len(asins) * (2 if with_rating else 1) + 5
    wait_tokens(cost)
    params = {
        "key": KEY, "domain": domain_id, "asin": ",".join(asins),
        "stats": 90, "history": 0,
    }
    if with_rating:
        params["rating"] = 1
    r = requests.get(f"{BASE}/product", params=params, timeout=180)
    j = r.json()
    if j.get("error"):
        raise RuntimeError(f"product error: {j['error']}")
    log(f"  products tokensLeft={j.get('tokensLeft')}")
    out = []
    for p in j.get("products", []):
        stats = p.get("stats") or {}
        cur = stats.get("current") or []
        avg90 = stats.get("avg90") or []

        def g(arr, i):
            try:
                v = arr[i]
                return None if v in (-1, -2, None) else v
            except (IndexError, TypeError):
                return None

        out.append({
            "asin": p.get("asin"),
            "title": p.get("title"),
            "brand": p.get("brand"),
            "rootCategory": p.get("rootCategory"),
            "categoryTree": [c.get("name") for c in (p.get("categoryTree") or [])],
            "trackingSince": p.get("trackingSince"),
            "listedSince": p.get("listedSince"),
            "monthlySold": p.get("monthlySold"),
            "price_amazon": g(cur, 0),
            "price_new": g(cur, 1),
            "price_bb": (stats.get("buyBoxPrice") if stats.get("buyBoxPrice", -1) > 0 else None),
            "price_new_avg90": g(avg90, 1),
            "rank_cur": g(cur, 3),
            "rank_avg90": g(avg90, 3),
            "offers_new": g(cur, 11),
            "rating": (g(cur, 16) / 10.0 if g(cur, 16) else None),
            "reviews": g(cur, 17),
            "fbaFees": (p.get("fbaFees") or {}).get("pickAndPackFee"),
            "referralFeePercent": p.get("referralFeePercent"),
            "packageWeight_g": p.get("packageWeight"),
            "packageL_mm": p.get("packageLength"),
            "packageW_mm": p.get("packageWidth"),
            "packageH_mm": p.get("packageHeight"),
            "itemWeight_g": p.get("itemWeight"),
            "salesRankReference": p.get("salesRankReference"),
        })
    return out


def build_selection(cat, market, mode):
    kw = cat["kw"][market]
    sel = {"title": kw, "perPage": 50, "page": 0}
    minp = int(cat["min_price"] * 100)
    sel["current_NEW_gte"] = minp
    if mode == "top":
        sel["current_RATING_gte"] = 40
        if market == "US":
            sel["monthlySold_gte"] = 200
            sel["sort"] = [["monthlySold", "desc"]]
            sel["current_COUNT_REVIEWS_gte"] = 100
        else:
            sel["current_COUNT_REVIEWS_gte"] = 30
            sel["current_SALES_gte"] = 1
            sel["current_SALES_lte"] = 50000
            sel["sort"] = [["current_SALES", "asc"]]
    else:  # new since Feb 2026
        sel["trackingSince_gte"] = FEB_2026
        if market == "US":
            sel["monthlySold_gte"] = 50
            sel["sort"] = [["monthlySold", "desc"]]
        else:
            sel["current_SALES_gte"] = 1
            sel["current_SALES_lte"] = 150000
            sel["sort"] = [["current_SALES", "asc"]]
    return sel


def main():
    jobs = []
    for cat in CATEGORIES:
        for market in DOMAINS:
            for mode in ("top", "new"):
                jobs.append((cat, market, mode))
    log(f"{len(jobs)} jobs; tokens now: {tokens_left()}")

    for cat, market, mode in jobs:
        out_file = DATA_DIR / f"{cat['slug']}__{market}__{mode}.json"
        if out_file.exists():
            log(f"skip {out_file.name} (exists)")
            continue
        did = DOMAINS[market]
        sel = build_selection(cat, market, mode)
        try:
            asins = finder(did, sel)
        except Exception as e:
            log(f"FINDER FAIL {cat['slug']} {market} {mode}: {e}")
            continue
        log(f"{cat['slug']} {market} {mode}: {len(asins)} asins")
        # US 'new' fallback: monthlySold filter may kill everything
        if not asins and mode == "new" and market == "US":
            sel.pop("monthlySold_gte", None)
            sel["sort"] = [["current_SALES", "asc"]]
            sel["current_SALES_gte"] = 1
            try:
                asins = finder(did, sel)
                log(f"  fallback (no monthlySold): {len(asins)} asins")
            except Exception as e:
                log(f"  fallback fail: {e}")
        n = TOP_N if mode == "top" else NEW_N
        asins = asins[:n]
        try:
            recs = products(did, asins, with_rating=(mode == "top" and market == "US"))
        except Exception as e:
            log(f"PRODUCTS FAIL {cat['slug']} {market} {mode}: {e}")
            continue
        payload = {
            "category": cat["slug"], "market": market, "mode": mode,
            "keyword": cat["kw"][market], "selection": sel,
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "records": recs,
        }
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        log(f"saved {out_file.name}: {len(recs)} records")

    log(f"DONE. tokens left: {tokens_left()}")


if __name__ == "__main__":
    main()
