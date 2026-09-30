# syntax=docker/dockerfile:1.7
#
# Targets:
#   dev      - Next.js dev server with hot reload, source bind-mounted by Compose
#   runtime  - production image: standalone server output only, non-root

ARG NODE_VERSION=24

# ---------------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

# ---------------------------------------------------------------------------------------
FROM deps AS dev
COPY . .
# .next must exist (owned by node) so Compose's anonymous volume inherits that ownership.
RUN mkdir -p .next && chown -R node:node /app
USER node
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

# ---------------------------------------------------------------------------------------
FROM deps AS builder
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Files stay root-owned and read-only; the server runs as the image's `node` user.
USER node
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/api/health').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

CMD ["node", "server.js"]
