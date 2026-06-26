# Amazon Niche Analyzer (Keepa + Alibaba)

End-to-end пайплайн для оценки ниши на Amazon US/DE с матчингом поставщиков Alibaba и анализом доли китайских продавцов.

> 📊 **Аналитика и дашборды.** Keepa MCP-сервер (`src/keepa_mcp/`) теперь
> считает sales velocity, inventory/stockout, opportunity score 0–100,
> category analysis и portfolio health, а также строит интерактивные
> HTML-дашборды. Подробности и сравнение с `cosjef/Keepa_MCP` — в
> [ANALYTICS.md](ANALYTICS.md).

## Что считает

1. **TAM ниши** — оценка объёма в шт/мес и $/мес по категории или фильтру
2. **Бенчмарки маржинальности** с учётом FBA pick&pack + Referral fee из Keepa
3. **ASIN + URL + главное изображение** для каждого товара
4. **Alibaba matching** — поиск поставщиков по title/brand через Apify
5. **CN vs Local split** — сколько продавцов из Китая (включая "замаскированных" под US/EU LLC) vs локальных

## Поддерживаемые маркеты

| Маркет | Источник | Статус |
|---|---|---|
| US (amazon.com) | Keepa API (domain=1) | ✅ полная поддержка |
| DE (amazon.de) | Keepa API (domain=3) | ✅ полная поддержка |
| AE (amazon.ae) | НЕ ПОДДЕРЖИВАЕТСЯ Keepa | ⚠️ см. notes/AE.md |

## Структура

```
niche_analyzer/
├── README.md
├── requirements.txt
├── config/
│   └── niche.example.yaml      # пример конфига ниши
├── src/
│   ├── __init__.py
│   ├── keepa_client.py         # тонкий клиент с rate-limit
│   ├── stage1_discover.py      # Product Finder → ASIN list
│   ├── stage2_enrich.py        # Product Request → метрики, картинки, fees
│   ├── stage3_sellers.py       # Offers + Seller Query → CN/Local классификация
│   ├── stage4_alibaba.py       # Apify Alibaba scraper
│   ├── stage5_analyze.py       # DuckDB агрегаты + Excel
│   └── run_pipeline.py         # оркестратор: запускает все стадии
└── output/                     # сюда падают CSV/Parquet/Excel
```

## Установка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Конфигурация

Скопируй `config/niche.example.yaml` в `config/niche.yaml` и отредактируй:

```yaml
niche_name: "yoga_mats"
keywords: ["yoga mat", "exercise mat", "fitness mat"]

marketplaces:
  US:
    domain: 1
    root_category: 3375251       # Sports & Outdoors. Найти id: см. ниже
    bsr_max: 50000
    bsr_min: 100
    price_min_usd: 15
    price_max_usd: 80
    review_min: 50
  DE:
    domain: 3
    root_category: 16435051      # Sport & Freizeit
    bsr_max: 30000
    bsr_min: 100
    price_min_usd: 15
    price_max_usd: 80
    review_min: 30

limits:
  max_asins_per_market: 2000
  offers_for_top_n: 300          # для скольких ASIN тащить детальные офферы (дорого!)
  alibaba_searches: 200

api_keys:
  keepa: "${KEEPA_API_KEY}"      # из env
  apify: "${APIFY_TOKEN}"        # опционально, без него Stage 4 пропускается
```

### Как найти root_category ID

```bash
python -m src.keepa_client categories --domain 1 --parent 0
# напечатает дерево корневых категорий с их catId
# дальше можно углубляться: --parent 3375251 покажет под-категории
```

## Запуск

```bash
export KEEPA_API_KEY="xxx"
export APIFY_TOKEN="xxx"   # опционально

# Все стадии:
python -m src.run_pipeline --config config/niche.yaml

# Только конкретная стадия (для отладки):
python -m src.run_pipeline --config config/niche.yaml --stages 1,2
python -m src.run_pipeline --config config/niche.yaml --stages 5  # только аналитика из сохранённых данных
```

Промежуточные данные сохраняются в `output/<niche_name>/`:
- `stage1_asins.parquet` — найденные ASIN
- `stage2_products.parquet` — обогащённые товары
- `stage3_sellers.parquet` — продавцы с классификацией
- `stage4_alibaba.parquet` — поставщики
- `report.xlsx` — финальный отчёт с листами TAM / Margin / CN_vs_Local / Alibaba

## Бюджет токенов Keepa

На 1 нишу × 2 маркета × 2000 ASIN × offers для топ-300:

| Стадия | Tokens |
|---|---|
| Stage 1 (Product Finder) | ~40 |
| Stage 2 (Product Request) | ~3 000 |
| Stage 3 (Offers + Sellers) | ~7 200 |
| **Итого** | **~10 000** |

На Premium плане (20 tokens/min) ≈ **9 часов** работы. Скрипт сам пилит на батчи и спит между запросами.

## Подводные камни

- **monthlySold** есть не для всех товаров и округляется (50+, 100+, 1K+). Для категорий, где Keepa его не отдаёт, используется fallback через BSR → Sales Estimator (приблизительный).
- **Эвристики "CN hidden"** не идеальны. Дают ~70-80% точности. Реальная проверка — глянуть на shopfront продавца глазами.
- **Alibaba matching** работает по семантике (title/brand), не по точному SKU. Один Amazon ASIN может матчиться на 10 разных Alibaba поставщиков и наоборот.
- **AE marketplace** Keepa не покрывает. Решения в `notes/AE.md`:
  - Bright Data Amazon dataset (filter: country=AE) — ~$1/1000 records
  - Apify amazon-crawler с регионом AE
  - Официальный SP-API (нужен seller account в AE)

## Лицензия / Disclaimer

Keepa ToS запрещает перепродажу сырых данных. Аналитику и derived-метрики использовать можно. Alibaba скрапинг — серая зона, используйте Apify/Bright Data для соблюдения их ToS.
