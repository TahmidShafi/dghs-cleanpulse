# ---------------------------------------------------------------------------
# DGHS-CleanPulse Backend Dockerfile
# Production-ready slim Python 3.12 image with uv and DuckDB in-memory caching
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# Install curl for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install official uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Cache dependency resolution layer
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --frozen --no-dev --project backend

# Copy backend source code and data directory for in-memory DuckDB loading
COPY backend/ ./backend/
COPY data/ ./data/

# Install the cleanpulse package into the virtual environment
RUN uv pip install -e backend/ --python /app/backend/.venv/bin/python

# Environment configuration
ENV PORT=8000
ENV PATH="/app/backend/.venv/bin:$PATH"

EXPOSE 8000

# Launch Uvicorn respecting dynamic $PORT (for Render / Railway / Hugging Face Spaces)
CMD ["sh", "-c", "exec uvicorn cleanpulse.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
