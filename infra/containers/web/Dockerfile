FROM node:22.22.0-alpine3.23@sha256:e4bf2a82ad0a4037d28035ae71529873c069b13eb0455466ae0bc13363826e34 AS build

WORKDIR /build

RUN apk upgrade --no-cache

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY index.html env.d.ts tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts ./
COPY public ./public
COPY src ./src

ARG VITE_APP_ENV
ARG VITE_API_BASE_URL
ARG VITE_API_MODE=live
ARG VITE_ENABLE_DEVTOOLS=false
ARG VITE_ENABLE_MOCK_LATENCY=false
ENV VITE_APP_ENV=${VITE_APP_ENV} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_API_MODE=${VITE_API_MODE} \
    VITE_ENABLE_DEVTOOLS=${VITE_ENABLE_DEVTOOLS} \
    VITE_ENABLE_MOCK_LATENCY=${VITE_ENABLE_MOCK_LATENCY}

RUN npm run build

FROM nginx:1.29.4-alpine3.23@sha256:4870c12cd2ca986de501a804b4f506ad3875a0b1874940ba0a2c7f763f1855b2 AS runtime

ARG API_ORIGIN

RUN apk upgrade --no-cache \
    && apk del curl

COPY infra/containers/web/nginx.conf.template /tmp/nginx.conf.template
RUN test -n "${API_ORIGIN}" \
    && sed "s|__API_ORIGIN__|${API_ORIGIN}|g" /tmp/nginx.conf.template > /etc/nginx/nginx.conf \
    && rm /tmp/nginx.conf.template \
    && chown -R nginx:nginx /var/cache/nginx /var/run /etc/nginx
COPY --from=build --chown=nginx:nginx /build/dist /usr/share/nginx/html

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1

ENTRYPOINT ["nginx", "-g", "daemon off;"]
