"""Stage 5: агрегаты через DuckDB → отчёт Excel.

Листы:
  - TAM            : ёмкость ниши в шт/мес и $/мес по маркетам
  - Margin_Top100  : маржинальность после FBA + Referral
  - CN_vs_Local    : доля продавцов CN/Local по штукам и $
  - Sellers_Detail : полная таблица продавцов с классификацией
  - Alibaba        : найденные поставщики
  - Products_All   : полная таблица товаров
"""
from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

log = logging.getLogger(__name__)


def run(out_dir: Path) -> Path:
    # Загружаем сохранённые parquet'ы
    products = pd.read_parquet(out_dir / "stage2_products.parquet")

    offers_path = out_dir / "stage3_offers.parquet"
    sellers_path = out_dir / "stage3_sellers.parquet"
    offers = pd.read_parquet(offers_path) if offers_path.exists() else pd.DataFrame()
    sellers = pd.read_parquet(sellers_path) if sellers_path.exists() else pd.DataFrame()

    alibaba_path = out_dir / "stage4_alibaba.parquet"
    alibaba = pd.read_parquet(alibaba_path) if alibaba_path.exists() else pd.DataFrame()

    con = duckdb.connect(":memory:")
    con.register("products", products)
    con.register("offers", offers) if not offers.empty else None
    con.register("sellers", sellers) if not sellers.empty else None

    # === TAM ============================================================
    tam = con.execute("""
        SELECT
            marketplace,
            COUNT(*)                                              AS asin_count,
            SUM(monthly_sold_estimated)                           AS units_per_month,
            ROUND(SUM(monthly_sold_estimated * buybox_price_usd), 0) AS gmv_usd_per_month,
            ROUND(AVG(buybox_price_usd), 2)                       AS avg_price,
            ROUND(MEDIAN(buybox_price_usd), 2)                    AS median_price,
            ROUND(AVG(rating), 2)                                 AS avg_rating,
            ROUND(AVG(review_count), 0)                           AS avg_reviews
        FROM products
        WHERE buybox_price_usd IS NOT NULL
        GROUP BY marketplace
        ORDER BY gmv_usd_per_month DESC
    """).df()

    # === Margin Top-100 ================================================
    margin = con.execute("""
        SELECT
            marketplace,
            asin,
            title,
            brand,
            buybox_price_usd                                       AS price,
            referral_fee_pct,
            ROUND(buybox_price_usd * referral_fee_pct / 100.0, 2)  AS referral_fee_usd,
            fba_pick_pack_usd,
            ROUND(
              buybox_price_usd
              - COALESCE(buybox_price_usd * referral_fee_pct / 100.0, 0)
              - COALESCE(fba_pick_pack_usd, 0)
            , 2)                                                   AS revenue_after_amazon_fees,
            monthly_sold_estimated,
            bsr_avg90,
            rating,
            review_count,
            amazon_url,
            main_image_url
        FROM products
        WHERE buybox_price_usd IS NOT NULL
        ORDER BY monthly_sold_estimated DESC NULLS LAST
        LIMIT 100
    """).df()

    # === CN vs Local ===================================================
    if not sellers.empty and not offers.empty:
        cn_split = con.execute("""
            WITH bb_owners AS (
                SELECT
                    o.marketplace,
                    o.asin,
                    o.seller_id
                FROM offers o
                WHERE o.is_buy_box_winner = TRUE
            ),
            joined AS (
                SELECT
                    p.marketplace,
                    p.asin,
                    p.monthly_sold_estimated,
                    p.buybox_price_usd,
                    COALESCE(s.seller_class, 'Unknown')  AS seller_class,
                    COALESCE(s.country_code, '')         AS country_code
                FROM products p
                LEFT JOIN bb_owners bb ON bb.asin = p.asin AND bb.marketplace = p.marketplace
                LEFT JOIN sellers s    ON s.seller_id = bb.seller_id AND s.marketplace = p.marketplace
            )
            SELECT
                marketplace,
                seller_class,
                COUNT(*)                                                       AS asins,
                SUM(monthly_sold_estimated)                                    AS units_per_month,
                ROUND(SUM(monthly_sold_estimated * buybox_price_usd), 0)       AS gmv_usd_per_month,
                ROUND(100.0 * SUM(monthly_sold_estimated)
                      / SUM(SUM(monthly_sold_estimated)) OVER (PARTITION BY marketplace), 1) AS pct_units,
                ROUND(100.0 * SUM(monthly_sold_estimated * buybox_price_usd)
                      / SUM(SUM(monthly_sold_estimated * buybox_price_usd)) OVER (PARTITION BY marketplace), 1) AS pct_gmv
            FROM joined
            WHERE monthly_sold_estimated IS NOT NULL
            GROUP BY marketplace, seller_class
            ORDER BY marketplace, gmv_usd_per_month DESC
        """).df()
    else:
        cn_split = pd.DataFrame([{"note": "offers/sellers data not available — run stages 3"}])

    # === Запись Excel ===================================================
    report_path = out_dir / "report.xlsx"
    with pd.ExcelWriter(report_path, engine="openpyxl") as w:
        tam.to_excel(w, sheet_name="TAM", index=False)
        margin.to_excel(w, sheet_name="Margin_Top100", index=False)
        cn_split.to_excel(w, sheet_name="CN_vs_Local", index=False)
        if not sellers.empty:
            sellers.to_excel(w, sheet_name="Sellers_Detail", index=False)
        if not alibaba.empty:
            alibaba.to_excel(w, sheet_name="Alibaba", index=False)
        # ограничим Products_All первыми 5000 строк чтобы Excel не подвис
        products.head(5000).to_excel(w, sheet_name="Products_All", index=False)

    log.info("Stage 5 done → %s", report_path)
    return report_path
