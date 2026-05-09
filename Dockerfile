# --- Build stage ----------------------------------------------------------
# A multi-stage build keeps the final image small: we install build tools
# (gcc, libpq headers) here, but the runtime stage only carries the wheels.
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps — psycopg2 & Pillow need these.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./
RUN pip wheel --wheel-dir=/wheels -r requirements.txt


# --- Runtime stage --------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=socialhub.settings \
    PORT=8000

# Runtime libs only — no compilers in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user.
RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=app:app . .

USER app

# Persistent data directories.
RUN mkdir -p /app/media /app/staticfiles /app/logs

EXPOSE 8000

# Healthcheck hits the /healthz endpoint we added earlier.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/healthz/ || exit 1

# Default command: collect static, run migrations, then start gunicorn.
# In production override with `command:` in docker-compose to skip migrate.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn socialhub.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --access-logfile - --error-logfile -"]
