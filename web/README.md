# Keepa Web — подбор товаров и сорсинг для команды

Веб-приложение поверх алгоритмов Keepa: живой поиск товаров Amazon, расчёт
сорсинга в Китае (landed / маржа / ROI), отчёты с разбивкой по категориям,
управление пользователями и журнал действий. Алгоритмы аналитики и сорсинга
портированы из Python-пакета `keepa_mcp` в TypeScript (см. `src/lib`).

## Что внутри

- **Вход по логину и паролю** (email = логин). Регистрации нет — учётные записи
  заводит администратор.
- **Роли и права (RBAC):** `ADMIN` и `USER`. Админ создаёт пользователей, задаёт
  и сбрасывает пароли, включает/отключает доступ, меняет роли.
- **Журнал действий (audit log):** входы (в т.ч. неудачные), создание/изменение
  пользователей, поиски, создание/просмотр/удаление отчётов — с IP и деталями.
- **Живой поиск Keepa:** фильтры (категория, цена, рейтинг, sales rank, отзывы,
  предложения, продажи/мес), метрики решения и авто-вердикт **BUY / WATCH / SKIP**.
  Комиссия Amazon — referral по категории + FBA.
- **Сохранённые поиски:** частые наборы фильтров сохраняются и запускаются в один
  клик (общие для команды). Категории кэшируются в БД (`KeepaCategory`) — подсказки
  по категориям работают и как офлайн-фолбэк, когда ключ Keepa недоступен.
- **Сорсинг в Китае:** MOQ-уровни, landed-стоимость, маржа, ROI, сценарии и
  вердикт **ЗАКУПАТЬ / ПРОВЕРИТЬ / ОТКАЗ** (порт `sourcing.py`, байт-в-байт по тестам).
- **Отчёты по категориям:** сохранение результатов в БД, фильтрация по типу,
  категории, рынку и тексту; страница отчёта с группировкой по категориям,
  фильтром по вердикту и **экспортом в CSV** — для демонстрации команде.

## Архитектура

| Слой | Технология |
|------|------------|
| UI / сервер | Next.js 15 (App Router, React 19, TypeScript) |
| БД | PostgreSQL + Prisma ORM (миграции) |
| Аутентификация | Сессия в httpOnly-cookie, JWT через `jose`, пароли — `bcryptjs` |
| Алгоритмы | TypeScript-порт `analysis.py`, `fees.py`, `sourcing.py` |
| Keepa | прямые REST-запросы к `api.keepa.com` (`src/lib/keepa.ts`) |
| Развёртывание | Docker Compose (Postgres + web) |

## Быстрый старт (Docker Compose)

```bash
cd web
cp .env.example .env            # задайте AUTH_SECRET, ADMIN_PASSWORD, KEEPA_API_KEY
docker compose up --build
```

При старте контейнер сам применяет миграции и создаёт администратора из
`ADMIN_EMAIL` / `ADMIN_PASSWORD`. Откройте http://localhost:3000 и войдите.

> Сгенерируйте секрет: `openssl rand -base64 48` → в `AUTH_SECRET`.

## Локальная разработка

```bash
cd web
npm install
# поднимите Postgres (любой), пропишите DATABASE_URL в .env
npx prisma migrate deploy        # применить миграции
npm run db:seed                  # создать администратора
npm run dev                      # http://localhost:3000
```

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | строка подключения PostgreSQL |
| `AUTH_SECRET` | секрет подписи сессионных JWT (длинная случайная строка) |
| `AUTH_SESSION_HOURS` | срок жизни сессии в часах (по умолчанию 12) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | начальный администратор (seed) |
| `KEEPA_API_KEY` | ключ Keepa API для живого поиска |
| `KEEPA_DEFAULT_DOMAIN` | рынок по умолчанию (US, GB, DE, FR, IT, ES, …) |
| `KEEPA_STATS_DAYS` | окно статистики цен/ранга (по умолчанию 90) |

Администратор по умолчанию — `kadievdavid37@gmail.com`. **Смените пароль после
первого входа** (страница «Мой аккаунт»).

## Тесты

```bash
npm test          # vitest: порты sourcing/fees (56 тестов)
npm run build     # продакшен-сборка + проверка типов
```

## Структура

```
web/
├── prisma/
│   ├── schema.prisma         # User, AuditLog, Report, ReportItem, SavedQuery, KeepaCategory
│   ├── migrations/           # SQL-миграции (коммитятся)
│   └── seed.ts               # идемпотентное создание администратора
├── src/
│   ├── middleware.ts         # защита маршрутов + гейтинг админ-зоны
│   ├── lib/
│   │   ├── db.ts             # клиент Prisma
│   │   ├── jwt.ts            # подпись/проверка сессии (edge-safe)
│   │   ├── auth.ts           # пароли, cookie сессии, текущий пользователь
│   │   ├── audit.ts          # запись в журнал действий
│   │   ├── keepa.ts          # REST-клиент Keepa (поиск, товары, категории)
│   │   ├── analysis.ts       # порт analysis.py (метрики + авто-вердикт)
│   │   ├── fees.ts           # порт fees.py (referral по категории)
│   │   ├── sourcing.ts       # порт sourcing.py (landed/маржа/ROI/сценарии)
│   │   └── report-mapper.ts  # запись записей в ReportItem
│   ├── app/
│   │   ├── login/            # экран входа
│   │   ├── (app)/            # защищённая зона (dashboard, search, reports, admin, account)
│   │   └── api/              # auth, users, search, reports, categories, audit, sourcing, tokens
│   └── components/           # UI (таблицы, формы, навигация)
└── docker-compose.yml, Dockerfile, docker-entrypoint.sh
```

## Замечания по безопасности

- Пароли хранятся как bcrypt-хэши; сессия — подписанный JWT в httpOnly-cookie
  (в проде — `Secure`).
- Самозащита: админ не может отключить/понизить сам себя и нельзя убрать
  последнего активного администратора.
- Все обращения к Keepa идут с сервера — ключ API не попадает в браузер.
