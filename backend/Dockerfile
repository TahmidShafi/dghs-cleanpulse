# ---------------------------------------------------------------------------
# DGHS-CleanPulse Backend Dockerfile
# Production-ready slim Python 3.12 image with uv and DuckDB in-memory caching
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# Install system dependencies required for build/runtime (curl, build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install official uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy the entire backend folder first so pyproject.toml can find README.md and src/ during build
COPY backend/ ./backend/

# Run uv sync to create virtual environment and install dependencies
RUN uv sync --frozen --no-dev --project backend

# Copy the rest of the workspace data directory (Parquet snapshots & reference data)
COPY data/ ./data/

# Environment configuration
ENV PYTHONPATH=/app/backend/src
ENV PORT=8000
ENV PATH="/app/backend/.venv/bin:$PATH"

EXPOSE 8000

# Launch Uvicorn respecting dynamic $PORT (for Render / Railway / Hugging Face Spaces)
CMD ["sh", "-c", "exec uvicorn cleanpulse.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
