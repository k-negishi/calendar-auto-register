FROM python:3.12-slim

ARG APP_ENV=prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH" \
    APP_ENV=${APP_ENV}

WORKDIR /workspace

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates; \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -sf /root/.local/bin/uv /usr/local/bin/uv

COPY pyproject.toml README.md ./
COPY app ./app

RUN uv pip install --system .

CMD ["bash"]
