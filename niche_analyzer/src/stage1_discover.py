"""Stage 1: дискавери ASIN'ов через Keepa Product Finder.

На вход — конфиг ниши, на выход — список ASIN по каждому маркету,
сохранённый в output/<niche>/stage1_asins.parquet
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .keepa_client import KeepaClient

log = logging.getLogger(__name__)


def build_selection(market_cfg: dict) -> dict:
    """Превращает блок маркета из YAML в keepa selection-объект.
    Цены/BSR Keepa ждёт в центах для USD/EUR/GBP."""
    sel = {
        "current_SALES_lte": market_cfg["bsr_max"],
        "current_SALES_gte": market_cfg["bsr_min"],
        "current_BUY_BOX_SHIPPING_gte": int(market_cfg["price_min_usd"] * 100),
        "current_BUY_BOX_SHIPPING_lte": int(market_cfg["price_max_usd"] * 100),
        "current_COUNT_REVIEWS_gte": market_cfg["review_min"],
        "productType": [0],            # 0 = standard product
        "sort": [["current_SALES", "asc"]],
    }
    if market_cfg.get("root_category"):
        sel["rootCategory"] = market_cfg["root_category"]
    return sel


def discover_market(client: KeepaClient, market: str, market_cfg: dict, max_asins: int) -> list[str]:
    sel = build_selection(market_cfg)
    domain = market_cfg["domain"]
    asins: list[str] = []
    per_page = 1000

    for page in range(20):
        batch = client.product_finder(domain, sel, page=page, per_page=per_page)
        if not batch:
            log.info("[%s] page %d empty, stopping", market, page)
            break
        asins.extend(batch)
        log.info("[%s] page %d: +%d (total %d)", market, page, len(batch), len(asins))
        if len(asins) >= max_asins or len(batch) < per_page:
            break

    return asins[:max_asins]


def run(cfg: dict, out_dir: Path, client: KeepaClient) -> pd.DataFrame:
    rows = []
    max_asins = cfg["limits"]["max_asins_per_market"]

    for market, market_cfg in cfg["marketplaces"].items():
        log.info("=== Stage 1: discovering %s ===", market)
        asins = discover_market(client, market, market_cfg, max_asins)
        for a in asins:
            rows.append({"marketplace": market, "domain": market_cfg["domain"], "asin": a})

    df = pd.DataFrame(rows)
    out = out_dir / "stage1_asins.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Stage 1 done: %d ASIN saved to %s", len(df), out)
    return df
