# Аналитика и дашборды (доработка на базе cosjef/Keepa_MCP)

Этот документ описывает аналитический слой нашего Keepa MCP-сервера и
интерактивные дашборды. Часть формул взята и адаптирована из открытого
проекта [`cosjef/Keepa_MCP`](https://github.com/cosjef/Keepa_MCP) (MIT,
TypeScript) и доработана под наши задачи.

## Сравнение с cosjef/Keepa_MCP

| Возможность | cosjef/Keepa_MCP | Наш сервер |
|---|---|---|
| Язык / транспорт | TypeScript, MCP | Python (FastMCP), MCP |
| Поиск товаров (Product Finder) | ✅ | ✅ |
| Мульти-маркет за один вызов | ❌ (по одному региону) | ✅ `search_multi_market` (6 рынков) |
| Sales velocity (оценка продаж) | ✅ (из rank) | ✅ улучшено: приоритет реального `monthlySold`, иначе rank-эвристика |
| Inventory / stockout | ✅ | ✅ `inventory_signals` |
| Opportunity score 0–100 | ✅ | ✅ расширено (конкуренция, качество, цена, волатильность, офферы) |
| Category analysis | ✅ | ✅ `category_summary` (ценовые диапазоны, конкуренция, качество, концентрация брендов) |
| Portfolio health | ✅ | ✅ `portfolio_health` |
| XLSX-отчёты | ❌ | ✅ (3 листа, цветные вердикты) |
| **Интерактивные HTML-дашборды** | ❌ | ✅ **новое** |
| Авто-поиск по расписанию | ❌ | ✅ (XLSX + дашборд на каждый прогон) |
| Ниша + Alibaba + доля CN-продавцов | ❌ | ✅ `niche_analyzer/` |
| Deal discovery | ✅ | ⏳ не портировано (требует Keepa `/deal` endpoint) |
| Seller lookup | ✅ | ⏳ не портировано |

Итог: мы взяли у cosjef ценные аналитические формулы (velocity, inventory,
opportunity, category, portfolio) и добавили то, чего у него нет —
интерактивные дашборды, XLSX, мульти-маркет и авто-режим.

## Новые метрики в каждом record

`build_record` теперь добавляет к каждому товару:

- `metrics.velocity` — `estimated_daily/weekly/monthly_sales`, `trend`
  (accelerating / stable / declining), `change_pct`, `source`
  (`monthly_sold` или `rank_estimate`).
- `metrics.inventory` — `turnover_rate`, `days_of_inventory`,
  `recommended_order_qty`, `out_of_stock_pct`, `stockout_risk`
  (high / medium / low / unknown).
- `opportunity` — `score` (0–100), `label` (high/medium/low) и `drivers`
  (что повлияло на балл).

### Формулы

**Sales velocity.** Если у Keepa есть `monthlySold` — берём его
(`daily = monthlySold / 30`). Иначе rank-эвристика
`daily = max(1, ⌊1e6 / √rank⌋)`. Тренд по сравнению текущего ранга со
средним за окно: ранг ниже среднего → продажи ускоряются.

**Inventory.** `days_of_inventory = ⌈30 / daily⌉`,
`recommended_order_qty = ⌈daily × 30⌉`. Риск out-of-stock по
`out_of_stock_pct` из Keepa stats (>30% high, >15% medium, иначе low).

**Opportunity score** (база 50, клампинг 0–100):
низкая конкуренция (высокий средний ранг) +20…+30; качество с запасом
(rating < 3.8) +15; цена в зоне $20–100 +10; стабильная цена +10 /
волатильная −10; мало офферов (≤12) +10 / много (≥25) −10.
≥70 = high, 45–69 = medium, <45 = low.

## Новые MCP-инструменты

- `category_analysis(category_id, …)` — анализ всей категории: рыночная
  сводка + opportunity по каждому товару.
- `market_summary(records)` — агрегированная сводка по набору records без
  траты токенов Keepa.
- `save_dashboard(records, …)` — записать интерактивный HTML-дашборд.
- `analyze_and_dashboard(asins, …)` — за один вызов: метрики + дашборд
  (+ опционально XLSX).

## Дашборды

`save_dashboard` / `analyze_and_dashboard` создают самодостаточный
`.html`-файл в `Products/`. Особенности:

- KPI-карточки: число товаров, средний opportunity score, уровень
  конкуренции, качество, portfolio health, разбивка BUY/WATCH/SKIP.
- Графики (Chart.js из CDN): распределение opportunity score, ценовые
  диапазоны, вердикты (пончик), топ-10 по оценке продаж/мес.
- Таблица товаров с поиском, фильтрами (вердикт, opportunity) и
  сортировкой по любому столбцу; ссылки на Amazon и Keepa.

Файл открывается в браузере без сервера и установки. Для графиков нужен
доступ в интернет (Chart.js подгружается с jsdelivr CDN).

Авто-поиск (`run_auto_search` / `keepa-auto`) теперь на каждый прогон
кладёт рядом и XLSX, и HTML-дашборд.
