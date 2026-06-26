# CLAUDE.md — правила и конфигурация проекта

Инструкции для Claude Code по этому репозиторию. Читаются автоматически в
начале сессии. Держи их в синхроне с `SEARCH_GUIDE.md` и кодом.

## Что это за проект

Инструменты для продуктового ресёрча на Amazon на данных Keepa. Две части:

1. **Keepa MCP-сервер** (`src/keepa_mcp/`) — основной интерактивный инструмент.
   Подключается через `/mcp` (см. `.mcp.json`). Ищет товары, считает
   purchase-decision метрики, выносит вердикты и пишет XLSX-отчёты в `Products/`.
   - `server.py` — MCP-инструменты (`search_products`, `search_multi_market`,
     `discover_products`, `category_best_sellers`, `get_products`,
     `analyze_and_report`, `save_report`, `save_buyer_report`,
     `run_auto_search`, `find_categories`, `token_status`, `server_info`).
   - `sourcing.py` — ссылки на поиск поставщиков Alibaba по ключевым словам
     из тайтла (для отчёта закупщику).
   - `analysis.py` — извлечение метрик, `auto_verdict` (правила вердиктов),
     `DECISION_GUIDANCE` (что вернуть пользователю).
   - `reports.py` — генерация XLSX (листы «Анализ», «Характеристики», «Сводка»).
   - `auto_search.py` — авторежим по `auto_searches.json` (каждые 2 дня).
   - `config.py` — конфигурация из env/`.env`/`ENV DOCS`.
2. **Niche Analyzer** (`niche_analyzer/`) — отдельный батч-пайплайн (Keepa +
   Alibaba) на 5 стадий, финальный отчёт `report.xlsx` пишет `stage5_analyze.py`.

## Правила аналитики (обязательно)

- **Активная ссылка на Amazon на каждом ASIN.** В любом аналитическом отчёте
  ячейка с ASIN должна быть **кликабельной ссылкой** на страницу товара
  `https://www.amazon.<tld>/dp/<asin>`. Отдельный текстовый столбец с URL не
  нужен — ссылку несёт сам ASIN. Это реализовано в `reports.py` (`_linkify`,
  оба листа) и `niche_analyzer/src/stage5_analyze.py` (`_linkify_asins`, листы
  `Margin_Top100` и `Products_All`). При добавлении новых листов/отчётов с
  товарами — сохраняй это поведение.
- Каждый record из `analysis.build_record` несёт поле `url` (Amazon) и
  `keepa_url`. URL строится по `<tld>` маркетплейса, а не хардкодом на `.com`.
- Каждый поиск завершается отчётом в `Products/` (или
  `KEEPA_OUTPUT_DIR`). Имя отчёта — краткое описание запроса латиницей.

## Правила вердиктов (BUY / WATCH / SKIP)

По каждому ASIN: вердикт + уверенность (high/medium/low) + 2–3 ключевые метрики
+ активная ссылка на Amazon. Пороговые значения — именованные константы в
`analysis.py` (меняешь число — обнови здесь и в `SEARCH_GUIDE.md`):

Сигналы «ЗА» (pro):
- волатильность цены ≤ `VOLATILITY_STABLE_MAX` (0.25);
- скорость продаж: просадок ранга/30д ≥ `DROPS30_STRONG` (8) **или**
  monthlySold ≥ `MONTHLY_STRONG` (300);
- конкуренция ≤ `OFFERS_LOW_MAX` (12) офферов и Buy Box **не** у Amazon;
- рейтинг ≥ `RATING_GOOD` (4.2) при ≥ `RATING_GOOD_REVIEWS` (100) отзывах.

Сигналы «ПРОТИВ» (con):
- волатильность ≥ `VOLATILITY_RISK_MIN` (0.50);
- затяжной тренд вниз: текущая цена < средней × `PRICE_DOWNTREND_RATIO` (0.85)
  → эрозия маржи;
- слабая динамика: просадок/30д ≤ `DROPS30_WEAK` (2) и monthlySold <
  `MONTHLY_WEAK` (100);
- Buy Box у Amazon;
- ≥ `OFFERS_CROWDED_MIN` (25) офферов (гонка на дно);
- рейтинг < `RATING_WEAK` (4.0);
- габарит/вес: package weight > `HEAVY_ITEM_G` (2500 г) — дорогой FBA.

Итог: `cons ≥ 3` **или** рейтинг < `RATING_SKIP` (3.8) → **SKIP**;
`pros ≥ 3` и `cons ≤ 1` → **BUY**; иначе **WATCH**.

Когда Claude в цикле — он выносит более богатые вердикты сам; `auto_verdict`
нужен прежде всего для unattended авторежима.

## Профиль поиска по умолчанию

Если пользователь не задал фильтры (подробности — `SEARCH_GUIDE.md`):
цена $15–60, рейтинг ≥ 4.2, отзывы ≥ 200, sales rank ≤ 60 000, офферы ≤ 15.
Маркеты в порядке приоритета: **US, UK, DE, FR, IT, ES**. ID категорий разные
на каждом рынке — сперва `find_categories` для нужного маркета.

## Discovery / сорсинг ($20–500)

Отдельный режим «что закупать» — инструмент `discover_products` (и
`analysis.discovery_signals`). Профиль по умолчанию: цена **$20–500**, рейтинг
≥ 4.0, sales rank ≤ 80 000, домен **US** (рынок-первоисточник). Категории
разные/много — поиск широкий (по фильтрам, не по одной нише).

Каждый товар получает теги-бакеты (может быть несколько) и `momentum_score`
для сортировки «что смотреть первым». Пороги — именованные константы в
`analysis.py`:
- **Bestseller** — sales rank ≤ `BESTSELLER_RANK_MAX` (15 000) **или**
  monthlySold ≥ `BESTSELLER_MONTHLY` (300): уже продаётся.
- **Rising** — тренд ранга вверх ≥ `RISING_TREND_PCT` (20 %) **или**
  просадок/30д ≥ `RISING_DROPS_30` (8): набирает обороты (`trend_pct` в
  `metrics.sales_rank`, считается из истории, а не из Keepa-finder).
- **New** — листинг моложе `NEW_LISTING_DAYS` (180) дней (`trackingSince`).

`focus` в `discover_products`: `"bestsellers" | "rising" | "new" | "all"`.

## Отчёт для закупщика (XLSX + DOCX)

`save_buyer_report` пишет два файла: **XLSX** (фильтруемая таблица) и **DOCX**
(наглядный бриф). На каждый товар: бакет, momentum, ключевые метрики спроса,
**кликабельный ASIN → Amazon** и **кликабельная ссылка на поиск поставщика в
Alibaba** (`alibaba_url` по ключевым словам из тайтла), плюс ссылка на
картинку (в DOCX — встроенная миниатюра, best-effort). Генераторы —
`reports.generate_reports(formats=("xlsx","docx"))`, `generate_docx_report`.
Правило активной ссылки на ASIN (см. выше) распространяется и сюда.

## Стратегия рынков: US → DE/ОАЭ

США — основа поиска (товары появляются здесь первыми). Найденное везём и
продаём в Германию и ОАЭ. Спрос по **DE** валидируем через Keepa (domain=3).
**ОАЭ (AE) Keepa не покрывает** (см. `niche_analyzer/notes/AE.md`) — это
целевой рынок сбыта без собственных Keepa-метрик; для данных по AE нужен
сторонний источник (Bright Data/Apify).

## Конфигурация

- **API-ключ Keepa**: env `KEEPA_API_KEY` → `.env` → файл `ENV DOCS` в корне.
  Эти файлы в git не коммитятся (`.gitignore`). Шаблон — `.env.example`.
- **Дефолты сервера** (`config.py`): `KEEPA_DOMAIN` (US), `KEEPA_STATS_DAYS`
  (90), `KEEPA_SEARCH_LIMIT` (50), `KEEPA_OUTPUT_DIR` (по умолчанию `Products/`).
- **Авторежим**: сохранённые поиски в `auto_searches.json`. Допустимые ключи
  `filters` — см. `_FILTER_KEYS` в `auto_search.py`; сырые ключи Keepa Product
  Finder идут в `extra_filters`.

## Команды разработки

```bash
uv run pytest -q          # офлайн-тесты (без обращения к Keepa API)
uv run keepa-mcp          # MCP-сервер (stdio)
uv run keepa-auto         # прогнать сохранённые авто-поиски
python check_setup.py     # проверка окружения/ключа
```

После изменений в правилах/отчётах прогоняй `uv run pytest -q`. Тесты
`test_offline.py` покрывают `build_record`, генерацию отчёта и `auto_verdict`.

## Git

- Ветка разработки: `claude/fervent-meitner-byj3nz`. Коммить осмысленными
  сообщениями, пушь в неё (`git push -u origin <branch>`).
- PR создавать только по явной просьбе.
