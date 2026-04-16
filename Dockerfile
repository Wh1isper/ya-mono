FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace

COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/ya-agent-platform-web/package.json apps/ya-agent-platform-web/package.json

RUN corepack enable && corepack pnpm install --frozen-lockfile --ignore-scripts=false

COPY apps/ya-agent-platform-web ./apps/ya-agent-platform-web

RUN corepack pnpm --dir apps/ya-agent-platform-web build


FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS python-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY . .

RUN uv build --package ya-agent-sdk -o /dist
RUN uv build --package ya-agent-platform -o /dist


FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YA_PLATFORM_ENVIRONMENT=production \
    YA_PLATFORM_HOST=0.0.0.0 \
    YA_PLATFORM_PORT=9042 \
    YA_PLATFORM_AUTO_MIGRATE=true \
    YA_PLATFORM_WEB_DIST_DIR=/srv/ya-agent-platform/web-dist

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/ya-agent-platform

COPY --from=python-builder /dist /tmp/dist
RUN sdk_wheel=$(ls /tmp/dist/ya_agent_sdk-*.whl) \
    && platform_wheel=$(ls /tmp/dist/ya_agent_platform-*.whl) \
    && python -m pip install "ya-agent-sdk[all] @ file://${sdk_wheel}" "${platform_wheel}" \
    && rm -rf /tmp/dist

COPY --from=frontend-builder /workspace/apps/ya-agent-platform-web/dist ./web-dist
COPY packages/ya-agent-platform/start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 9042

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9042/healthz')"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/srv/ya-agent-platform/start.sh"]
