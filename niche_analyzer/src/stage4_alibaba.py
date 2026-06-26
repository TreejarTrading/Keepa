"""Stage 4: матчинг товаров с поставщиками Alibaba.

Использует Apify actor (по умолчанию `epctex/alibaba-scraper`).
Без APIFY_TOKEN стадия пропускается с предупреждением.

Можно подменить actor через env APIFY_ALIBABA_ACTOR.
Альтернатива — собственный Playwright-скрипт (см. notes/playwright_alibaba.py).
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

STOPWORDS = {
    "the", "for", "with", "and", "of", "pack", "premium", "pro", "set",
    "new", "best", "high", "quality", "size", "large", "small", "extra",
    "your", "you", "our", "all", "non", "anti", "free", "made", "use",
}


def normalize_search_query(title: str, brand: str | None = None, max_words: int = 4) -> str:
    """Берёт самые значимые слова из тайтла для поиска на Alibaba."""
    if not title:
        return brand or ""
    # выкидываем размеры, числа, кавычки
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    words = [w for w in cleaned.split() if w not in STOPWORDS and not w.isdigit() and len(w) > 2]

    # удаляем бренд из запроса, если он есть (мы хотим найти generic поставщика)
    if brand:
        bwords = set(brand.lower().split())
        words = [w for w in words if w not in bwords]

    return " ".join(words[:max_words])


def run_apify(queries: list[str], apify_token: str, actor: str, limit_per_query: int = 10) -> list[dict]:
    """Запускает Apify actor для списка запросов."""
    try:
        from apify_client import ApifyClient
    except ImportError:
        log.error("apify-client not installed; pip install apify-client")
        return []

    client = ApifyClient(apify_token)
    all_items: list[dict] = []

    for q in queries:
        if not q:
            continue
        log.info("Alibaba search: %r", q)
        run_input = {
            "searchQueries": [q],
            "maxItems": limit_per_query,
            "endPage": 1,
        }
        try:
            run = client.actor(actor).call(run_input=run_input, timeout_secs=300)
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                item["_search_query"] = q
                all_items.append(item)
        except Exception as e:
            log.warning("Apify run failed for %r: %s", q, e)

    return all_items


def parse_alibaba_item(it: dict) -> dict:
    """Нормализует поля. Структура зависит от конкретного actor'а,
    держим defensive-парсинг с множественными возможными ключами."""
    def first(*keys):
        for k in keys:
            v = it.get(k)
            if v not in (None, "", []):
                return v
        return None

    return {
        "search_query": it.get("_search_query"),
        "title": first("title", "productTitle", "name"),
        "url": first("url", "productUrl", "link"),
        "image": first("image", "mainImage", "imageUrl"),
        "category": first("category", "categoryName", "categories"),
        "category_url": first("categoryUrl", "categoryLink"),
        "price_min_fob": first("priceMin", "minPrice", "lowPrice"),
        "price_max_fob": first("priceMax", "maxPrice", "highPrice"),
        "moq": first("minOrder", "minOrderQuantity", "moq"),
        "supplier_name": first("supplierName", "companyName", "supplier"),
        "supplier_url": first("supplierUrl", "companyUrl"),
        "supplier_country": first("supplierCountry", "country") or "CN",
        "supplier_years": first("supplierYears", "yearsOnAlibaba"),
        "supplier_verified": first("isVerified", "goldSupplier"),
        "raw": it,
    }


def run(products_df: pd.DataFrame, out_dir: Path, cfg: dict) -> pd.DataFrame:
    token = os.environ.get(cfg["api_keys"]["apify_env"])
    if not token:
        log.warning("APIFY_TOKEN not set, skipping Stage 4")
        return pd.DataFrame()

    actor = os.environ.get("APIFY_ALIBABA_ACTOR", "epctex/alibaba-scraper")
    limit = cfg["limits"]["alibaba_searches"]

    # формируем уникальные запросы: top-N по monthly_sold, по 1 запросу на бренд
    top = (
        products_df.dropna(subset=["monthly_sold_estimated"])
                   .sort_values("monthly_sold_estimated", ascending=False)
                   .head(limit * 2)  # с запасом, потом дедупим
    )

    queries: list[tuple[str, str]] = []  # (query, source_asin)
    seen = set()
    for _, r in top.iterrows():
        q = normalize_search_query(r["title"], r.get("brand"))
        if q and q not in seen:
            seen.add(q)
            queries.append((q, r["asin"]))
        if len(queries) >= limit:
            break

    log.info("Stage 4: running %d Alibaba searches via Apify (%s)", len(queries), actor)
    raw = run_apify([q for q, _ in queries], token, actor)
    parsed = [parse_alibaba_item(it) for it in raw]
    df = pd.DataFrame(parsed)
    if not df.empty:
        df = df.drop(columns=["raw"], errors="ignore")
    out = out_dir / "stage4_alibaba.parquet"
    df.to_parquet(out, index=False)
    log.info("Stage 4 done: %d Alibaba items → %s", len(df), out)
    return df
