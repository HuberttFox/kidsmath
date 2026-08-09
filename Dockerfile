# syntax=docker/dockerfile:1
# 阶段1：构建（uv 锁版本同步依赖）
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

# 阶段2：运行（精简镜像、非 root）
FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install --no-install-recommends -y tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
RUN useradd -m mathgen && chown -R mathgen:mathgen /app && mkdir -p /data && chown mathgen:mathgen /data
USER mathgen
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"]
CMD ["/app/.venv/bin/mathgen-serve", "--host", "0.0.0.0", "--port", "8080"]
