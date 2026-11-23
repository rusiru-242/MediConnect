# MediConnect — Backend Production Deployment Guide

- **Service:** MediConnect Core API
- **Framework:** FastAPI (Python 3.12)
- **Database:** MongoDB Atlas (TLS Enabled Replica Set)
- **Process Manager:** Uvicorn / Gunicorn with `uvicorn.workers.UvicornWorker`
- **Target Environments:** Cloud Run / AWS ECS / Ubuntu Linux with Docker & Nginx

---

## 1. Overview & Architecture

The MediConnect backend is an asynchronous, high-concurrency RESTful API service providing healthcare management, doctor scheduling, Stripe payments, digital prescriptions, and AI assistant capabilities.

```
                      ┌─────────────────────────────────────────┐
                      │            Internet / Clients           │
                      │  (Mobile App, Web Admin, Stripe Webhook)│
                      └────────────────────┬────────────────────┘
                                           │ HTTPS (Port 443)
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │        Reverse Proxy (Nginx / ALB)      │
                      │  - TLS Termination (TLS 1.2 / 1.3)     │
                      │  - HTTP Strict Transport Security (HSTS)│
                      │  - Rate Limiting & Proxy Headers        │
                      └────────────────────┬────────────────────┘
                                           │ HTTP (Port 8000)
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │        ASGI Application Server          │
                      │  - Gunicorn / Uvicorn (Workers: 4)      │
                      │  - FastAPI Lifespan & Reminder Worker   │
                      │  - Non-root Container User (UID 10001)   │
                      └────────────┬───────────────┬────────────┘
                                   │               │
                 TLS MongoDB URI   ▼               ▼  HTTPS Outbound
             ┌───────────────────────┐   ┌───────────────────────────┐
             │     MongoDB Atlas     │   │ External Cloud APIs:      │
             │ - Replica Set         │   │ - Stripe (Payments)       │
             │ - TLS 1.2+ Enforced   │   │ - Firebase (FCM Pushes)   │
             │ - Auto Automated Daily│   │ - Gemini / OpenAI (AI)    │
             │   Backups             │   │ - SendGrid / SES (SMTP)   │
             └───────────────────────┘   └───────────────────────────┘
```

---

## 2. Containerized Deployment (Docker)

### 2.1 Building the Production Container
MediConnect includes a multi-stage, unprivileged `Dockerfile` optimized for minimal size and hardened against container escapes:

```bash
cd backend
docker build -t mediconnect-backend:latest .
```

### 2.2 Running with Docker
Inject environment variables securely via an environment file (e.g., `/etc/mediconnect/.env.production`):

```bash
docker run -d \
  --name mediconnect-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file /etc/mediconnect/.env.production \
  -v /var/mediconnect/uploads:/app/uploads \
  mediconnect-backend:latest
```

> [!IMPORTANT]
> Never copy or bake `.env` or secret keys into the Docker image. All secrets must be injected at runtime via environment variables or secret vaults.

---

## 3. Production Environment Configuration

Copy `backend/.env.production.example` to your deployment environment (e.g. `/etc/mediconnect/.env.production`) and configure all required variables:

| Variable | Required | Description | Example / Recommendation |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | **Yes** | Enables production security checks (HSTS, JWT length >= 32). | `production` |
| `MONGODB_URI` | **Yes** | Atlas TLS connection string with replica set. | `mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority&tls=true` |
| `DATABASE_NAME` | **Yes** | Production database name. | `mediconnect` |
| `JWT_SECRET` | **Yes** | High-entropy signing key (minimum 32 characters). | Generate via `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | **Yes** | Symmetric HMAC algorithm. | `HS256` |
| `ALLOWED_ORIGINS` | **Yes** | Comma-separated list of allowed CORS domains. | `https://app.mediconnect.lk,https://admin.mediconnect.lk` |
| `STRIPE_SECRET_KEY` | **Yes** | Stripe production live secret key. | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | **Yes** | Webhook endpoint secret for signature validation. | `whsec_...` |
| `FIREBASE_CREDENTIALS_PATH` | **Yes** | Path to service account JSON file. | `/etc/mediconnect/secrets/firebase-service-account.json` |

---

## 4. Production ASGI Execution & Reverse Proxy

### 4.1 Recommended Gunicorn Execution
For multi-core production virtual machines:

```bash
# 4 workers running Uvicorn Worker class
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app \
  --bind 0.0.0.0:8000 \
  --access-logfile /var/log/mediconnect/access.log \
  --error-logfile /var/log/mediconnect/error.log \
  --timeout 60 \
  --graceful-timeout 30
```

### 4.2 Nginx Configuration with TLS Termination
```nginx
upstream mediconnect_upstream {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name api.mediconnect.lk;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.mediconnect.lk;

    ssl_certificate /etc/letsencrypt/live/api.mediconnect.lk/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.mediconnect.lk/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    client_max_body_size 15M;

    location / {
        proxy_pass http://mediconnect_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }
}
```

---

## 5. Health Checks & Monitoring

### 5.1 Endpoints
- **Liveness Probe:** `GET /health` or `GET /api/health`
  Returns non-sensitive health metadata without leaking credentials:
  ```json
  {
    "status": "healthy",
    "api": "healthy",
    "database": {
      "connected": true,
      "status": "connected",
      "message": "Database connection is healthy."
    },
    "environment": "production"
  }
  ```
- **Readiness Probe:** `GET /ready` or `GET /api/ready`
  Returns `HTTP 200` with `{"status": "ready"}` if database is reachable; returns `HTTP 503` if database is down.

---

## 6. Disaster Recovery & Rollback Runbook

1. **Rollback Strategy:** Maintain previous Docker tag (e.g. `mediconnect-backend:v1.0.0-rc1`). If a release candidate exhibits unexpected errors:
   ```bash
   docker stop mediconnect-api
   docker run -d --name mediconnect-api --env-file /etc/mediconnect/.env.production mediconnect-backend:v1.0.0-rc1
   ```
2. **MongoDB Atlas Snapshots:** Automated daily backup snapshots are retained in MongoDB Atlas. Use Atlas point-in-time restore to restore database state in case of data corruption.
