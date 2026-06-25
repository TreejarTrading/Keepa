# Развёртывание Keepa Web онлайн

Веб-приложение (`web/`) — это Next.js + PostgreSQL, упакованное в Docker.
Ниже — два проверенных способа поднять его **без своего сервера** (хостинг берёт
машину и БД на себя), плюс запуск на собственном сервере через Docker Compose.

## Переменные окружения (нужны при любом способе)

Сначала сгенерируйте секрет сессии:

```bash
openssl rand -base64 48
```

| Переменная | Значение |
|---|---|
| `DATABASE_URL` | строка подключения PostgreSQL (даёт хостинг БД) |
| `AUTH_SECRET` | длинная случайная строка (вывод команды выше) |
| `ADMIN_EMAIL` | `kadievdavid37@gmail.com` (логин администратора) |
| `ADMIN_PASSWORD` | **пароль администратора — задаёте вы** |
| `ADMIN_NAME` | `Administrator` |
| `KEEPA_API_KEY` | ключ Keepa для живого поиска (можно оставить пустым — остальное работает) |
| `KEEPA_DEFAULT_DOMAIN` | `US` |
| `KEEPA_STATS_DAYS` | `90` |

После первого входа смените пароль на странице **«Мой аккаунт»**.

---

## Вариант 1 — Railway (рекомендуется, проще всего)

Railway сам соберёт образ из `web/Dockerfile`, поднимет PostgreSQL, применит
миграции и создаст администратора — это уже зашито в `docker-entrypoint.sh`.

1. Регистрация: <https://railway.app> (вход через GitHub).
2. **New Project → Deploy from GitHub repo** → выберите `TreejarTrading/Keepa`,
   ветку `main` (после мерджа PR #3) или `claude/happy-ramanujan-0cbnsw`.
3. Откройте сервис → **Settings → Root Directory** → впишите `web`
   (Railway найдёт `web/Dockerfile` и будет собирать по нему).
4. В проекте: **New → Database → Add PostgreSQL**.
5. В сервисе приложения → вкладка **Variables** → добавьте переменные из таблицы
   выше. Для `DATABASE_URL` нажмите **Add Reference** и выберите
   `Postgres.DATABASE_URL` — строка подставится автоматически.
   - `PORT` Railway задаёт сам — не трогайте.
   - `HOSTNAME` **не задавайте** (сервер слушает `0.0.0.0` по умолчанию).
6. **Deploy.** В логах появятся «Applying database migrations…» и
   «Seeding administrator…».
7. **Settings → Networking → Generate Domain** — получите публичный URL.
8. Откройте URL, войдите (`ADMIN_EMAIL` / `ADMIN_PASSWORD`), смените пароль.

Стоимость: бесплатный стартовый кредит, дальше ~$5/мес. Ресурсы: хватает
минимального инстанса (приложение в рантайме ~130 МБ, Postgres ~70 МБ).

---

## Вариант 2 — Vercel + Neon (бесплатно, чуть больше шагов)

Vercel хостит приложение, Neon — бесплатный PostgreSQL.

1. **База:** на <https://neon.tech> создайте проект и скопируйте **Connection
   string** (вида `postgresql://…neon.tech/neondb?sslmode=require`). Возьмите
   прямую (не «pooled») строку — она нужна для миграций.
2. **Приложение:** на <https://vercel.com> → **Add New → Project** → импортируйте
   репозиторий `TreejarTrading/Keepa`.
3. **Root Directory** → `web`.
4. **Build & Output Settings → Build Command** замените на:
   ```
   prisma generate && prisma migrate deploy && tsx prisma/seed.ts && next build
   ```
   Миграции применятся и админ создастся при каждом деплое (операции идемпотентны).
5. **Environment Variables** — добавьте переменные из таблицы выше
   (`DATABASE_URL` = строка Neon).
6. **Deploy.** Vercel выдаст публичный URL (`*.vercel.app`).
7. Войдите (`ADMIN_EMAIL` / `ADMIN_PASSWORD`), смените пароль.

Примечания:
- `next.config.mjs` содержит `output: "standalone"` (для Docker) — Vercel его
  игнорирует, мешать не будет.
- Прямой строки Neon достаточно для команды. Под заметную нагрузку перейдите на
  «pooled»-строку Neon и добавьте в `prisma/schema.prisma` `directUrl` для миграций.

---

## Вариант 3 — свой сервер (Docker Compose)

```bash
cd web
cp .env.example .env     # заполните переменные из таблицы выше
docker compose up -d --build
```

Откроется на <http://localhost:3000> (или по адресу сервера). `docker compose`
поднимает и PostgreSQL, и приложение, сам прогоняет миграции и создаёт админа.

Требования к серверу:
- **RAM:** 1 ГБ хватает при запуске готового образа; 2 ГБ — если собирать на самом
  сервере (пик сборки ~0.8 ГБ).
- **Диск:** ~2 ГБ для готовых образов + данные; ~5 ГБ если собирать на месте.
- **Софт:** только Docker + Docker Compose (Node и Postgres — внутри контейнеров).

---

## Проверка после деплоя

- `GET /api/health` → `200`.
- Вход по `ADMIN_EMAIL` / `ADMIN_PASSWORD` → попадаете на «Обзор».
- Раздел «Поиск» без `KEEPA_API_KEY` покажет подсказку — это нормально; отчёты,
  сорсинг, пользователи и журнал работают и без ключа.
