FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache --no-install-project
COPY apps/api apps/api
ENV PYTHONPATH=/app/apps/api
COPY alembic.ini ./
COPY scripts scripts
COPY content-sample-assets-folder/brands.json content-sample-assets-folder/brands.json
RUN useradd --create-home --uid 1000 interlude && mkdir -p /app/data /app/reports && chown interlude:interlude /app/data /app/reports
ENV PATH="/app/.venv/bin:$PATH"
USER interlude
CMD ["uvicorn", "interlude.main:app", "--host", "0.0.0.0", "--port", "8000"]
