"""Stage 3: офферы продавцов + классификация CN vs Local.

Шаги:
1. Для top-N ASIN (по monthly_sold) тащим offers=20.
2. Собираем уникальные seller_id.
3. Через seller-endpoint достаём адрес + имя бизнеса.
4. Применяем эвристику "скрытый CN" по паттернам имени.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from .keepa_client import KeepaClient
from .stage2_enrich import AMAZON_SELLER_IDS

log = logging.getLogger(__name__)

# Паттерны имени продавца, указывающие на CN происхождение
CN_NAME_PATTERNS = [
    re.compile(r"\b(shenzhen|guangzhou|dongguan|yiwu|ningbo|hangzhou|zhejiang|fujian|jiangsu|shanghai|beijing|chengdu|xiamen)\b", re.I),
    re.compile(r"\b(co\.?,?\s*ltd|trading\s+co|technology\s+co|e-?commerce\s+co|hk limited)\b", re.I),
]

# Случайные капс-бренды типа KAUKKO / ZESICA — паттерн "5-9 заглавных букв"
ALL_CAPS_BRAND = re.compile(r"^[A-Z]{5,9}$")


def classify_seller(seller: dict) -> tuple[str, str, str]:
    """Возвращает (class, country_code, reason).
    class ∈ {Amazon, CN_direct, CN_hidden, Local, Other, Unknown}."""
    if not seller:
        return "Unknown", "", "no_data"

    addr = seller.get("address") or {}
    country = (addr.get("countryCode") or "").upper()
    name = seller.get("sellerName") or ""

    # 1. сам Amazon
    if seller.get("sellerId") in AMAZON_SELLER_IDS.values():
        return "Amazon", country, "amazon_official"

    # 2. явно CN
    if country == "CN":
        return "CN_direct", country, "address_cn"
    if country == "HK":
        return "CN_direct", country, "address_hk"

    # 3. скрытый CN — паттерн имени
    for pat in CN_NAME_PATTERNS:
        if pat.search(name):
            return "CN_hidden", country, f"name_match:{pat.pattern[:40]}"

    if country in ("US", "GB", "DE") and ALL_CAPS_BRAND.match(name):
        return "CN_hidden", country, "all_caps_brand"

    # 4. локальный
    if country in ("US", "DE", "FR", "IT", "ES", "GB", "NL", "BE", "PL", "SE"):
        return "Local", country, "address_local"

    if country:
        return "Other", country, "address_other"

    return "Unknown", "", "no_country"


def collect_offers(client: KeepaClient, products_df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Для топ-N ASIN по monthly_sold тащит детальные офферы."""
    offers_rows = []

    for (marketplace, domain), grp in products_df.groupby(["marketplace", "domain"]):
        top = (
            grp.dropna(subset=["monthly_sold_estimated"])
               .nlargest(top_n, "monthly_sold_estimated")
        )
        asins = top["asin"].tolist()
        log.info("[%s] fetching offers for top-%d ASIN", marketplace, len(asins))

        products = client.product(
            domain=int(domain),
            asins=asins,
            history=0,
            stats=30,
            offers=20,
            buybox=1,
            rating=0,
        )

        for p in products:
            for off in p.get("offers") or []:
                price_cents = None
                offer_csv = off.get("offerCSV") or []
                if len(offer_csv) >= 3:
                    # [ts, price, shipping] последний триплет
                    price_cents = (offer_csv[-2] or 0) + (offer_csv[-1] or 0)

                offers_rows.append({
                    "marketplace": marketplace,
                    "asin": p["asin"],
                    "seller_id": off.get("sellerId"),
                    "condition": off.get("condition"),
                    "is_fba": off.get("isFBA"),
                    "is_prime": off.get("isPrime"),
                    "price_usd": (price_cents / 100) if price_cents else None,
                    "is_buy_box_winner": off.get("isBuyBoxWinner"),
                })
    return pd.DataFrame(offers_rows)


def fetch_seller_metadata(client: KeepaClient, offers_df: pd.DataFrame, domain_map: dict[str, int]) -> pd.DataFrame:
    rows = []
    for marketplace, grp in offers_df.groupby("marketplace"):
        seller_ids = grp["seller_id"].dropna().unique().tolist()
        # фильтруем Amazon-ы
        seller_ids = [s for s in seller_ids if s not in AMAZON_SELLER_IDS.values()]
        if not seller_ids:
            continue

        log.info("[%s] looking up %d unique sellers", marketplace, len(seller_ids))
        sellers = client.seller(domain_map[marketplace], seller_ids)

        for sid, sdata in sellers.items():
            klass, country, reason = classify_seller(sdata)
            addr = sdata.get("address") or {}
            rows.append({
                "marketplace": marketplace,
                "seller_id": sid,
                "seller_name": sdata.get("sellerName"),
                "country_code": country,
                "city": addr.get("city"),
                "state": addr.get("state"),
                "rating": sdata.get("currentRating"),
                "rating_count_30d": sdata.get("currentRatingCount"),
                "rating_count_lifetime": sdata.get("lifetimeRatingsCount"),
                "fba": sdata.get("hasFBA"),
                "track_since": sdata.get("trackedSince"),
                "seller_class": klass,
                "classify_reason": reason,
            })
    return pd.DataFrame(rows)


def run(products_df: pd.DataFrame, out_dir: Path, client: KeepaClient, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    top_n = cfg["limits"]["offers_for_top_n"]
    domain_map = {m: c["domain"] for m, c in cfg["marketplaces"].items()}

    offers_df = collect_offers(client, products_df, top_n)
    offers_out = out_dir / "stage3_offers.parquet"
    offers_df.to_parquet(offers_out, index=False)
    log.info("Stage 3 offers: %d rows → %s", len(offers_df), offers_out)

    sellers_df = fetch_seller_metadata(client, offers_df, domain_map)
    sellers_out = out_dir / "stage3_sellers.parquet"
    sellers_df.to_parquet(sellers_out, index=False)
    log.info("Stage 3 sellers: %d rows → %s", len(sellers_df), sellers_out)

    return offers_df, sellers_df
