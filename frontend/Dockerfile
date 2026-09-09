FROM node:22-bookworm-slim AS builder
WORKDIR /app/frontend
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
COPY scripts/prepare-standalone.mjs /app/scripts/prepare-standalone.mjs
RUN npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3117
COPY --from=builder --chown=node:node /app/frontend/.next/standalone ./
USER node
EXPOSE 3117
CMD ["node", "server.js"]
