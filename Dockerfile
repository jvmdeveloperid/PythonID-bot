FROM python:3.14-slim

LABEL maintainer="PythonID Bot"
LABEL description="Telegram bot for group profile monitoring"

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files only (these change less frequently)
COPY pyproject.toml uv.lock .python-version README.md ./

# Install dependencies (cached unless pyproject.toml or uv.lock change)
RUN uv sync --frozen

# Create data directory
RUN mkdir -p /app/data

# Copy remaining project files (code changes trigger new layer)
COPY src/ ./src/

# Make app directory writable for any user (supports dynamic UID via docker-compose)
RUN chmod -R a+rw /app

# Set uv cache inside /app so any UID can write to it
ENV UV_CACHE_DIR=/app/.cache/uv

# Run the bot
CMD ["uv", "run", "pythonid-bot"]
