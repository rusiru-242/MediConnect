# ==============================================================================
# MediConnect - Production FastAPI Container
# Base Image: Python 3.12 Slim (Linux Bookworm)
# Security: Unprivileged execution user, no secrets bundled, minimal footprint
# ==============================================================================

FROM python:3.12-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_HOME=/app

# Install minimal OS dependencies and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user and group (UID/GID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d ${APP_HOME} appuser

# Set working directory
WORKDIR ${APP_HOME}

# Install Python production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/

# Create uploads directory with unprivileged ownership
RUN mkdir -p ${APP_HOME}/uploads && \
    chown -R appuser:appgroup ${APP_HOME}

# Switch to unprivileged execution user
USER appuser

# Expose HTTP port
EXPOSE 8000

# Container health check probing the non-sensitive /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production ASGI server execution with proxy header support
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
