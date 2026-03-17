# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Next.js production build (fallback-compatible with non-Next setups during transition).
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi
COPY --from=builder /app .

EXPOSE 3000

# Prefer Next.js start; fallback to Vite preview if start script is not present yet.
CMD ["sh", "-c", "if npm run | grep -q '^  start'; then npm run start -- -p ${PORT}; else npm run preview -- --host 0.0.0.0 --port ${PORT}; fi"]
