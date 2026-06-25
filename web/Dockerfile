# syntax=docker/dockerfile:1

# ---- deps ----------------------------------------------------------------
FROM node:22-alpine AS deps
RUN apk add --no-cache openssl
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- build ---------------------------------------------------------------
FROM node:22-alpine AS build
RUN apk add --no-cache openssl
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npx prisma generate && npm run build

# ---- run -----------------------------------------------------------------
FROM node:22-alpine AS run
RUN apk add --no-cache openssl
WORKDIR /app
ENV NODE_ENV=production
# Standalone server + static assets + prisma engine/schema for migrate & seed.
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=build /app/node_modules/@prisma ./node_modules/@prisma
COPY --from=build /app/node_modules/prisma ./node_modules/prisma
COPY --from=build /app/node_modules/.bin ./node_modules/.bin
COPY --from=build /app/node_modules/tsx ./node_modules/tsx
COPY --from=build /app/prisma ./prisma
COPY --from=build /app/docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh
EXPOSE 3000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["node", "server.js"]
