# Nuxt 4 SSR (Nitro node-server) for Cloud Run — see deploy/gcp/README.md
FROM node:22-alpine AS build

WORKDIR /app

RUN corepack enable

# pnpm-workspace.yaml holds allowBuilds (esbuild, @parcel/watcher) required for install
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
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
