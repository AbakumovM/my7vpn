FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Копируем файлы зависимостей отдельно для кэширования слоя
COPY pyproject.toml uv.lock ./

# Устанавливаем только prod-зависимости из lockfile
RUN uv sync --no-dev --frozen

# Копируем весь исходный код
COPY . .

# Добавляем venv в PATH
ENV PATH="/app/.venv/bin:$PATH"
