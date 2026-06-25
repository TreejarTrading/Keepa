"""Оркестратор: запускает выбранные стадии 1..5.

Использование:
    python -m src.run_pipeline --config config/niche.yaml
    python -m src.run_pipeline --config config/niche.yaml --stages 1,2
    python -m src.run_pipeline --config config/niche.yaml --stages 5    # только аналитика
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from .keepa_client import KeepaClient
from . import stage1_discover, stage2_enrich, stage3_sellers, stage4_alibaba, stage5_analyze


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--stages", default="1,2,3,4,5", help="Comma-separated stage numbers to run")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("pipeline")

    cfg = load_config(args.config)
    stages = {int(x) for x in args.stages.split(",")}

    out_dir = Path("output") / cfg["niche_name"]
    out_dir.mkdir(parents=True, exist_ok=True)

    keepa_key = os.environ.get(cfg["api_keys"]["keepa_env"])
    if not keepa_key and stages & {1, 2, 3}:
        log.error("Keepa API key not set (env %s)", cfg["api_keys"]["keepa_env"])
        sys.exit(1)

    client = KeepaClient(
        keepa_key,
        sleep_between=cfg["limits"].get("sleep_between_calls_sec", 4.0),
    ) if keepa_key else None

    # ---- Stage 1: discover ASINs --------------------------------------
    if 1 in stages:
        stage1_df = stage1_discover.run(cfg, out_dir, client)
    else:
        path = out_dir / "stage1_asins.parquet"
        stage1_df = pd.read_parquet(path) if path.exists() else None

    # ---- Stage 2: enrich ---------------------------------------------
    if 2 in stages:
        if stage1_df is None or stage1_df.empty:
            log.error("Stage 2 needs Stage 1 output")
            sys.exit(1)
        products_df = stage2_enrich.run(stage1_df, out_dir, client)
    else:
        path = out_dir / "stage2_products.parquet"
        products_df = pd.read_parquet(path) if path.exists() else None

    # ---- Stage 3: sellers --------------------------------------------
    if 3 in stages:
        if products_df is None or products_df.empty:
            log.error("Stage 3 needs Stage 2 output")
            sys.exit(1)
        stage3_sellers.run(products_df, out_dir, client, cfg)

    # ---- Stage 4: Alibaba --------------------------------------------
    if 4 in stages:
        if products_df is None or products_df.empty:
            log.error("Stage 4 needs Stage 2 output")
            sys.exit(1)
        stage4_alibaba.run(products_df, out_dir, cfg)

    # ---- Stage 5: analyze --------------------------------------------
    if 5 in stages:
        report_path = stage5_analyze.run(out_dir)
        log.info("=== DONE === Report: %s", report_path)


if __name__ == "__main__":
    main()
