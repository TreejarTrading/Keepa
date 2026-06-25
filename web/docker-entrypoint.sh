#!/bin/sh
set -e

echo "→ Applying database migrations..."
npx prisma migrate deploy

echo "→ Seeding administrator account (idempotent)..."
npx tsx prisma/seed.ts || echo "seed skipped"

echo "→ Starting Next.js..."
exec "$@"
