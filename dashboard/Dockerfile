FROM node:22-alpine AS build

WORKDIR /app/dashboard

ARG NEXT_PUBLIC_API_BASE_URL=https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:22-alpine

WORKDIR /app/dashboard
ENV NODE_ENV=production

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=build /app/dashboard/package.json ./package.json
COPY --from=build /app/dashboard/package-lock.json ./package-lock.json
COPY --from=build /app/dashboard/node_modules ./node_modules
COPY --from=build /app/dashboard/.next ./.next
COPY --from=build /app/dashboard/next.config.mjs ./next.config.mjs

RUN chown -R appuser:appgroup /app
USER appuser

ENV PORT=8080
EXPOSE 8080
CMD ["npm", "run", "start:cloudrun"]
