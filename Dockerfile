FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY apps/api apps/api
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY scripts scripts
COPY content-sample-assets-folder/brands.json content-sample-assets-folder/brands.json
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "interlude.main:app", "--host", "0.0.0.0", "--port", "8000"]
