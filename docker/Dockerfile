# ============================================================================
# Dockerfile for Development
# Single stage with hot-reload support
# ============================================================================

FROM python:3.12-slim-bookworm

WORKDIR /app

# 1. Install system dependencies and Node.js (required for Tailwind CSS)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl gnupg build-essential libpq-dev libmagic1 \
    netcat-openbsd postgresql-client && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# 2. Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/ssn

# 3. Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 4. Copy application code
COPY . .

# 5. Create directories and non-root user
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} -o python && \
    useradd --create-home -u ${UID} -g ${GID} -s /bin/bash python && \
    mkdir -p /app/ssn/media /app/ssn/logs /app/static && \
    chown -R python:python /app

COPY --chown=python:python entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER python

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
# Development: runserver with auto-reload
CMD ["python", "ssn/manage.py", "runserver", "0.0.0.0:8000"]
