# syntax=docker/dockerfile:1.7
# Frontend image — multi-stage. dev = vite dev server, prod = node adapter.

ARG NODE_VERSION=20

# ---------------- base ----------------
FROM node:${NODE_VERSION}-slim AS base
WORKDIR /app
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

# ---------------- deps ----------------
FROM base AS deps
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile || pnpm install

# ---------------- dev ----------------
FROM deps AS dev
COPY . .
RUN pnpm exec svelte-kit sync
EXPOSE 5173
# Generate .svelte-kit (tsconfig etc.) then start Vite dev server.
CMD ["sh", "-c", "CI=true pnpm install --frozen-lockfile && pnpm exec svelte-kit sync && pnpm dev --host 0.0.0.0 --port 5173 --strictPort"]

# ---------------- build ----------------
FROM deps AS build
COPY . .
ARG PUBLIC_API_URL=http://localhost:8000
ARG PUBLIC_CARTO_BASEMAP_API_KEY=
ENV PUBLIC_API_URL=$PUBLIC_API_URL
ENV VITE_API_URL=$PUBLIC_API_URL
ENV PUBLIC_CARTO_BASEMAP_API_KEY=$PUBLIC_CARTO_BASEMAP_API_KEY
ENV SVELTE_ADAPTER=node
RUN pnpm exec svelte-kit sync && pnpm build

# ---------------- prod ----------------
FROM base AS prod
ENV NODE_ENV=production
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
COPY --from=build /app/pnpm-lock.yaml* ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --prod --ignore-scripts
EXPOSE 3000
# SvelteKit's node adapter reads PORT, ORIGIN, BODY_SIZE_LIMIT from env.
ENV PORT=3000
CMD ["node", "build"]
