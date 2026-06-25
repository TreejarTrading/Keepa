# AE Marketplace (amazon.ae)

Keepa **не поддерживает** Amazon UAE. Варианты:

## 1. Bright Data — Amazon dataset

```python
import requests

# Dataset ID для amazon products
url = "https://api.brightdata.com/datasets/v3/trigger"
headers = {"Authorization": f"Bearer {BRIGHTDATA_TOKEN}"}
payload = {
    "dataset_id": "gd_l7q7dkf244hwjntr0",   # Amazon products dataset
    "filters": [
        {"name": "country", "operator": "=", "value": "AE"},
        {"name": "category", "operator": "in", "value": ["Sports", "Home"]},
    ],
    "limit": 5000,
}
r = requests.post(url, json=payload, headers=headers)
snapshot_id = r.json()["snapshot_id"]
# Дальше poll по snapshot_id
```

Возвращает похожий набор полей (ASIN, title, price, rating, seller, ...).
Стоимость ≈ $1 за 1000 record'ов.

## 2. Apify amazon-crawler

```python
from apify_client import ApifyClient

client = ApifyClient(APIFY_TOKEN)
run = client.actor("vaclavrut/amazon-crawler").call(run_input={
    "categoryOrProductUrls": [
        {"url": "https://www.amazon.ae/s?k=yoga+mat"},
    ],
    "maxItems": 1000,
    "scrapeProductDetails": True,
    "scrapeSellers": True,
    "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
})
items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
```

## 3. SP-API (официально)

Нужен seller account на amazon.ae + onboarding к SP-API. Тогда доступны:
- Catalog API (продукт-данные)
- Reports API (Brand Analytics)
- Product Pricing API

Без seller account — недоступно.

## 4. Адаптация в пайплайн

Чтобы пайплайн поддерживал AE, нужно:
1. Заменить Stage 1+2 для AE-маркета на Bright Data/Apify-источник.
2. Привести output к той же схеме, что и Keepa products (см. `stage2_enrich.parse_product`).
3. Сохранять в тот же `stage2_products.parquet` с `marketplace='AE'`.
4. Дальше Stage 5 (аналитика) работает без изменений.

Пример адаптера:

```python
# src/stage2_enrich_ae.py
from apify_client import ApifyClient

def fetch_ae_products(keywords: list[str], limit: int):
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run_input = {
        "categoryOrProductUrls": [
            {"url": f"https://www.amazon.ae/s?k={k.replace(' ', '+')}"} for k in keywords
        ],
        "maxItems": limit,
        "scrapeProductDetails": True,
        "scrapeSellers": True,
    }
    run = client.actor("vaclavrut/amazon-crawler").call(run_input=run_input)
    return [normalize_ae(it) for it in client.dataset(run["defaultDatasetId"]).iterate_items()]

def normalize_ae(it: dict) -> dict:
    """Приводит структуру Apify к нашему формату products."""
    return {
        "asin": it.get("asin"),
        "marketplace": "AE",
        "domain": None,
        "title": it.get("title"),
        "brand": it.get("brand"),
        "buybox_price_usd": it.get("price", {}).get("value"),  # *0.27 для USD из AED
        "rating": it.get("stars"),
        "review_count": it.get("reviewsCount"),
        "monthly_sold_estimated": None,   # AE не отдаёт BSR estimator
        "amazon_url": f"https://www.amazon.ae/dp/{it.get('asin')}",
        "main_image_url": (it.get("thumbnailImage") or {}).get("link"),
        # ... остальные поля
    }
```

## Сравнение

| Источник | Цена | Качество | История цен | Sellers |
|---|---|---|---|---|
| Bright Data | ~$1/1000 | Высокое | Нет | Базово |
| Apify | ~$5–20/1000 | Среднее | Нет | Есть |
| SP-API | Бесплатно* | Эталон | Нет | Только свои |

*требует seller account.

Для разовой оценки AE-ниши я бы взял Apify (быстрый старт, не нужны прокси).
