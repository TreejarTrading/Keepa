"""Stage 2: обогащение ASIN'ов — цены, BSR, monthlySold, fees, картинки.

Тащит batch по 100 ASIN через keepa /product (history=1, stats=90).
Парсит важные поля и сохраняет в parquet.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .keepa_client import CSV, KeepaClient

log = logging.getLogger(__name__)

AMAZON_SELLER_IDS = {
    1: "ATVPDKIKX0DER",        # US
    3: "A3JWKAKR8XB7XF",        # DE
    2: "A3P5ROKL5A1OLE",        # UK
    4: "A1X6FK5RDHNB96",        # FR
    8: "APJ6JRA9NG5V4",         # IT
    9: "A1AT7YVPFBWXBL",        # ES
    6: "A3DWYIK6Y9EEQB",        # CA
}


def _safe_get(arr, idx):
    if not arr or idx is None:
        return None
    try:
        v = arr[idx]
        return v if v is not None and v != -1 else None
    except (IndexError, TypeError):
        return None


def parse_product(p: dict, marketplace: str, domain: int) -> dict:
    stats = p.get("stats") or {}
    current = stats.get("current") or []

    buybox_cents = _safe_get(current, CSV["BUY_BOX_SHIPPING"])
    new_fba_cents = _safe_get(current, CSV["NEW_FBA"])
    amazon_cents = _safe_get(current, CSV["AMAZON"])
    price_cents = buybox_cents or new_fba_cents or amazon_cents

    rating_raw = _safe_get(current, CSV["RATING"])     # 0-50 (×10)
    bsr_current = _safe_get(current, CSV["SALES"])

    avg90 = stats.get("avg90") or []
    bsr_avg90 = _safe_get(avg90, CSV["SALES"])

    images_csv = p.get("imagesCSV") or ""
    main_img = images_csv.split(",")[0] if images_csv else None

    fba_fees = p.get("fbaFees") or {}
    pick_pack_cents = fba_fees.get("pickAndPackFee")
    storage_cents = fba_fees.get("storageFee")

    cat_tree = p.get("categoryTree") or []
    last_cat = cat_tree[-1] if cat_tree else {}

    # buyBoxSellerIdHistory — массив [ts, sellerId, ts, sellerId, ...]
    bb_hist = p.get("buyBoxSellerIdHistory") or []
    last_bb_seller = bb_hist[-1] if bb_hist else None
    is_amazon_winning_bb = last_bb_seller == AMAZON_SELLER_IDS.get(domain)

    tld_map = {1: "com", 3: "de", 2: "co.uk", 4: "fr", 8: "it", 9: "es", 6: "ca"}
    tld = tld_map.get(domain, "com")

    return {
        "asin": p["asin"],
        "marketplace": marketplace,
        "domain": domain,
        "title": p.get("title"),
        "brand": p.get("brand"),
        "manufacturer": p.get("manufacturer"),
        "model": p.get("model"),
        "part_number": p.get("partNumber"),
        "ean_list": ",".join(p.get("eanList") or []),
        "upc_list": ",".join(p.get("upcList") or []),

        # цена и продажи
        "price_current_usd": (price_cents / 100) if price_cents else None,
        "buybox_price_usd": (buybox_cents / 100) if buybox_cents else None,
        "bsr_current": bsr_current,
        "bsr_avg90": bsr_avg90,
        "monthly_sold": p.get("monthlySold"),
        "rating": (rating_raw / 10) if rating_raw else None,
        "review_count": p.get("reviewCount"),

        # категория
        "root_category_id": p.get("rootCategory"),
        "category_id_leaf": last_cat.get("catId"),
        "category_name_leaf": last_cat.get("name"),
        "category_path": " > ".join(c.get("name", "") for c in cat_tree),

        # габариты
        "package_weight_g": p.get("packageWeight"),
        "package_length_mm": p.get("packageLength"),
        "package_width_mm": p.get("packageWidth"),
        "package_height_mm": p.get("packageHeight"),
        "item_weight_g": p.get("itemWeight"),

        # fees
        "referral_fee_pct": p.get("referralFeePercentage"),
        "fba_pick_pack_usd": (pick_pack_cents / 100) if pick_pack_cents else None,
        "fba_storage_usd": (storage_cents / 100) if storage_cents else None,

        # ссылки
        "amazon_url": f"https://www.amazon.{tld}/dp/{p['asin']}",
        "main_image_url": f"https://m.media-amazon.com/images/I/{main_img}" if main_img else None,
        "all_images": images_csv,

        # текущий держатель Buy Box
        "buybox_seller_id": last_bb_seller,
        "amazon_owns_buybox": is_amazon_winning_bb,
        "is_amazon_listed": amazon_cents is not None,

        # доп.
        "variation_count": len(p.get("variationCSV") or []),
        "parent_asin": p.get("parentAsin"),
        "first_seen_timestamp": p.get("trackingSince"),
    }


def estimate_units_from_bsr(bsr: int | None, category_id: int | None) -> int | None:
    """Грубая оценка месячных продаж из BSR.
    Это очень приблизительно и категория-зависимо.
    Реальные таблицы зависят от категории — здесь упрощённая модель."""
    if not bsr or bsr <= 0:
        return None
    if bsr <= 100:
        return int(30000 / (bsr ** 0.4))
    elif bsr <= 1000:
        return int(15000 / (bsr ** 0.5))
    elif bsr <= 10000:
        return int(8000 / (bsr ** 0.55))
    elif bsr <= 100000:
        return int(3000 / (bsr ** 0.5))
    else:
        return max(1, int(500 / (bsr ** 0.4)))


def run(stage1_df: pd.DataFrame, out_dir: Path, client: KeepaClient) -> pd.DataFrame:
    all_rows = []

    for (marketplace, domain), grp in stage1_df.groupby(["marketplace", "domain"]):
        asins = grp["asin"].tolist()
        log.info("=== Stage 2: enriching %s (%d ASIN) ===", marketplace, len(asins))

        products = client.product(
            domain=int(domain),
            asins=asins,
            history=1,
            stats=90,
            offers=0,        # офферы отдельно в Stage 3 (дорого)
            buybox=1,
            rating=1,
        )

        for p in products:
            row = parse_product(p, marketplace, int(domain))
            # если нет monthly_sold — оценим по BSR
            if not row["monthly_sold"]:
                row["monthly_sold_estimated"] = estimate_units_from_bsr(
                    row["bsr_avg90"] or row["bsr_current"], row["root_category_id"]
                )
            else:
                row["monthly_sold_estimated"] = row["monthly_sold"]
            all_rows.append(row)

    df = pd.DataFrame(all_rows)
    out = out_dir / "stage2_products.parquet"
    df.to_parquet(out, index=False)
    log.info("Stage 2 done: %d products → %s", len(df), out)
    return df
