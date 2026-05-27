# Nuxt 4 SSR (Nitro node-server) for Cloud Run — see deploy/gcp/README.md
FROM node:22-alpine AS build

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

FROM node:22-alpine

WORKDIR /app

ENV HOST=0.0.0.0
ENV PORT=8080

COPY --from=build /app/.output ./.output

EXPOSE 8080

CMD ["node", ".output/server/index.mjs"]
