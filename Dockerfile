FROM python:3.11-slim

# curl needed for HEALTHCHECK; no GIS native libs needed (GIS code uses stdlib sqlite3+struct)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifest first for layer caching
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy application source
COPY . .

# Overlay docker-safe config (no hardcoded secrets) as the active config
RUN cp config.docker.py config.py

# Create a non-root user and transfer ownership
RUN useradd --create-home --shell /bin/bash zorora && \
    chown -R zorora:zorora /app

USER zorora

# Ensure ~/.zorora state directories exist for the runtime user
RUN mkdir -p /home/zorora/.zorora/logs

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "--config", "gunicorn.conf.py", "ui.web.app:app"]
