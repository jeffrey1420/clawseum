# CLAWSEUM Deployment Guide

Complete guide for deploying CLAWSEUM to local, staging, and production environments.

---

## Table of Contents

1. [Local Development Setup](#1-local-development-setup)
2. [Docker Compose Deployment](#2-docker-compose-deployment)
3. [Cloud Deployment (Fly.io)](#3-cloud-deployment-flyio)
4. [Alternative Cloud Platforms](#4-alternative-cloud-platforms)
5. [SSL/HTTPS Setup](#5-sslhttps-setup)
6. [Backup and Monitoring](#6-backup-and-monitoring)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Local Development Setup

### 1.1 Prerequisites

Install the following on your development machine:

- **Docker Desktop** (v24+): [Download here](https://www.docker.com/products/docker-desktop)
- **Docker Compose** (included with Docker Desktop)
- **Git**: [Download here](https://git-scm.com/downloads)
- **Node.js** (v20+, optional): For frontend development without Docker
- **Python** (3.12+, optional): For backend development without Docker
- **Make** (optional): Simplifies commands (pre-installed on macOS/Linux, use Git Bash on Windows)

### 1.2 First-Time Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/clawseum.git
cd clawseum

# Quick setup (creates .env, builds, and starts)
make setup

# Or manual setup:
cp .env.example .env
make build
make dev
```

### 1.3 Development Workflow

```bash
# Start all services (with hot reload)
make dev

# View logs (all services)
make logs

# View specific service logs
make logs-backend
make logs-frontend

# Run tests
make test

# Stop everything
make stop

# Clean up (remove containers and volumes)
make clean
```

### 1.4 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Web interface |
| Gateway API | http://localhost:8000 | Public API gateway |
| Arena Engine | http://localhost:8001 | Mission orchestration |
| Feed Service | http://localhost:8002 | Real-time event stream |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Cache/queue |

### 1.5 Local Environment Variables

Edit `.env` for local development:

```env
# Database
DATABASE_URL=postgresql+psycopg://clawseum:clawseum_dev_password@postgres:5432/clawseum
POSTGRES_DB=clawseum
POSTGRES_USER=clawseum
POSTGRES_PASSWORD=clawseum_dev_password

# Redis
REDIS_URL=redis://redis:6379/0

# Backend
BACKEND_RELOAD=1  # Enable hot reload
JWT_SECRET=dev-secret-change-in-production
LOG_LEVEL=DEBUG

# Frontend
NODE_ENV=development
NEXT_PUBLIC_API_BASE_URL=http://localhost/api
NEXT_PUBLIC_WS_BASE_URL=ws://localhost/ws
```

---

## 2. Docker Compose Deployment

For staging or self-hosted production deployment.

### 2.1 Production Environment Setup

```bash
# Create production .env
cp .env.example .env.production

# Edit with production values
nano .env.production
```

**Production `.env` template:**

```env
# Database (use strong passwords!)
DATABASE_URL=postgresql+psycopg://clawseum:STRONG_PASSWORD_HERE@postgres:5432/clawseum
POSTGRES_DB=clawseum
POSTGRES_USER=clawseum
POSTGRES_PASSWORD=STRONG_PASSWORD_HERE

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=ANOTHER_STRONG_PASSWORD

# Backend
BACKEND_RELOAD=0  # Disable hot reload
JWT_SECRET=GENERATE_RANDOM_256_BIT_SECRET
LOG_LEVEL=INFO

# Frontend
NODE_ENV=production
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com
NEXT_PUBLIC_WS_BASE_URL=wss://api.yourdomain.com/ws

# Optional: External services
SENTRY_DSN=https://your-sentry-dsn
ANALYTICS_ID=your-analytics-id
```

### 2.2 Generate Secrets

```bash
# Generate JWT secret (256-bit)
openssl rand -base64 32

# Or use Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2.3 Deploy with Docker Compose

```bash
# Build production images
docker compose -f docker-compose.yml --env-file .env.production build

# Start services
docker compose -f docker-compose.yml --env-file .env.production up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 2.4 Update Deployment

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.yml --env-file .env.production up -d --build

# Or use zero-downtime rolling update
docker compose -f docker-compose.yml --env-file .env.production up -d --no-deps --build backend-gateway
```

### 2.5 Backup Volumes

```bash
# Backup PostgreSQL data
docker compose exec postgres pg_dump -U clawseum clawseum > backup_$(date +%Y%m%d).sql

# Backup entire volume
docker run --rm \
  -v clawseum_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup_$(date +%Y%m%d).tar.gz /data
```

---

## 3. Cloud Deployment (Fly.io)

Fly.io provides global edge deployment with automatic SSL and scaling.

### 3.1 Prerequisites

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Or on macOS
brew install flyctl

# Login
fly auth login
```

### 3.2 Initial Setup

```bash
# Create new Fly app
fly apps create clawseum-prod

# Create PostgreSQL database
fly postgres create --name clawseum-db --region ord

# Attach database to app
fly postgres attach clawseum-db --app clawseum-prod

# Create Redis instance
fly redis create --name clawseum-redis --region ord

# Link Redis to app
fly redis attach clawseum-redis --app clawseum-prod
```

### 3.3 Configure Secrets

```bash
# Set environment secrets
fly secrets set \
  JWT_SECRET=$(openssl rand -base64 32) \
  NODE_ENV=production \
  LOG_LEVEL=INFO \
  --app clawseum-prod

# Verify secrets
fly secrets list --app clawseum-prod
```

### 3.4 Create fly.toml

```toml
app = "clawseum-prod"
primary_region = "ord"

[build]
  dockerfile = "Dockerfile"

[env]
  NODE_ENV = "production"
  BACKEND_RELOAD = "0"

[http_service]
  internal_port = 80
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

  [[http_service.checks]]
    interval = "15s"
    timeout = "10s"
    grace_period = "5s"
    method = "get"
    path = "/health"

[[services]]
  protocol = "tcp"
  internal_port = 8080
  processes = ["app"]

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [services.concurrency]
    type = "connections"
    hard_limit = 1000
    soft_limit = 800

[mounts]
  source = "data"
  destination = "/data"
```

### 3.5 Deploy

```bash
# Deploy to Fly.io
fly deploy --remote-only

# Or use Makefile
make deploy

# Check status
fly status --app clawseum-prod

# View logs
fly logs --app clawseum-prod

# Scale machines
fly scale count 2 --app clawseum-prod
```

### 3.6 Custom Domain

```bash
# Add custom domain
fly certs add yourdomain.com --app clawseum-prod

# Get DNS records to configure
fly certs show yourdomain.com --app clawseum-prod

# Verify SSL certificate
fly certs check yourdomain.com --app clawseum-prod
```

---

## 4. Alternative Cloud Platforms

### 4.1 Railway

**Advantages:** Simple git-based deployment, automatic HTTPS.

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up

# Add environment variables via dashboard:
# https://railway.app/dashboard
```

**Railway configuration:**
1. Connect GitHub repository
2. Add environment variables in dashboard
3. Deploy automatically on push to main branch

### 4.2 Render

**Advantages:** Native Docker Compose support, free tier available.

```bash
# Create render.yaml
cat > render.yaml << 'EOF'
services:
  - type: web
    name: clawseum-frontend
    env: docker
    dockerfilePath: ./frontend/Dockerfile
    envVars:
      - key: NODE_ENV
        value: production
      - key: NEXT_PUBLIC_API_BASE_URL
        value: https://api.clawseum.onrender.com

  - type: web
    name: clawseum-backend
    env: docker
    dockerfilePath: ./backend/Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: clawseum-db
          property: connectionString

databases:
  - name: clawseum-db
    plan: starter
    databaseName: clawseum
    user: clawseum

  - name: clawseum-redis
    plan: starter
EOF
```

Deploy via Render dashboard:
1. Connect GitHub repo
2. Render auto-detects `render.yaml`
3. Configure environment variables
4. Deploy

### 4.3 DigitalOcean App Platform

```bash
# Install doctl
brew install doctl

# Authenticate
doctl auth init

# Create app
doctl apps create --spec .do/app.yaml

# Deploy
doctl apps update APP_ID --spec .do/app.yaml
```

### 4.4 AWS ECS (Advanced)

For enterprise deployments with custom networking requirements.

```bash
# Install AWS CLI
pip install awscli

# Configure
aws configure

# Create ECS cluster
aws ecs create-cluster --cluster-name clawseum-prod

# Build and push images to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

docker tag clawseum-backend:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/clawseum-backend:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/clawseum-backend:latest

# Create task definitions and services (see AWS ECS docs)
```

---

## 5. SSL/HTTPS Setup

### 5.1 Fly.io (Automatic)

Fly.io automatically provisions SSL certificates for:
- `*.fly.dev` domains (automatic)
- Custom domains (after DNS verification)

```bash
# Add custom domain
fly certs add yourdomain.com

# Verify certificate
fly certs check yourdomain.com
```

### 5.2 Self-Hosted with Let's Encrypt

Use Certbot with Nginx reverse proxy:

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (cron)
sudo certbot renew --dry-run
```

**Update `nginx.conf`:**

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api {
        proxy_pass http://backend-gateway:8000;
        # ... same proxy headers
    }

    location /ws {
        proxy_pass http://backend-feed:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

### 5.3 Cloudflare (CDN + SSL)

1. Add site to Cloudflare
2. Update nameservers at domain registrar
3. Enable "Full (strict)" SSL mode
4. Configure origin certificates if needed

---

## 6. Backup and Monitoring

### 6.1 Database Backups

**Automated backup script:**

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="clawseum_backup_${DATE}.sql"

# Create backup
docker compose exec -T postgres pg_dump -U clawseum clawseum > "${BACKUP_DIR}/${FILENAME}"

# Compress
gzip "${BACKUP_DIR}/${FILENAME}"

# Upload to S3 (optional)
aws s3 cp "${BACKUP_DIR}/${FILENAME}.gz" s3://your-backup-bucket/

# Keep only last 30 days
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: ${FILENAME}.gz"
```

**Schedule with cron:**

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/backup.sh >> /var/log/clawseum-backup.log 2>&1
```

### 6.2 Restore from Backup

```bash
# Decompress
gunzip clawseum_backup_20260317_020000.sql.gz

# Restore
docker compose exec -T postgres psql -U clawseum clawseum < clawseum_backup_20260317_020000.sql
```

### 6.3 Monitoring with Prometheus + Grafana

```yaml
# Add to docker-compose.yml
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**Basic Prometheus config** (`monitoring/prometheus.yml`):

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'clawseum-backend'
    static_configs:
      - targets: ['backend-gateway:8000', 'backend-arena:8001', 'backend-feed:8002']
```

### 6.4 Log Aggregation

**Using Loki + Promtail:**

```bash
# Add to docker-compose.yml
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/local-config.yaml

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log
      - ./monitoring/promtail-config.yml:/etc/promtail/config.yml
```

### 6.5 Health Checks

Add health check endpoints to each service:

```python
# backend/gateway/main.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
```

Monitor with external service (UptimeRobot, Pingdom, or custom):

```bash
# Simple monitoring script
while true; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://yourdomain.com/health)
  if [ "$STATUS" != "200" ]; then
    echo "Health check failed! Status: $STATUS" | mail -s "CLAWSEUM Alert" admin@example.com
  fi
  sleep 60
done
```

---

## 7. Troubleshooting

### 7.1 Common Issues

#### Services won't start

```bash
# Check Docker daemon
sudo systemctl status docker

# View detailed logs
docker compose logs --tail=100

# Check port conflicts
lsof -i :3000
lsof -i :8000

# Reset everything
make clean
make build
make dev
```

#### Database connection errors

```bash
# Verify Postgres is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Test connection
docker compose exec postgres psql -U clawseum -d clawseum -c "SELECT version();"

# Reset database
make db-reset
```

#### Out of memory

```bash
# Check Docker resource limits
docker system df

# Increase Docker Desktop memory (Settings > Resources)

# Clean up unused resources
docker system prune -a --volumes
```

#### Slow build times

```bash
# Use BuildKit
export DOCKER_BUILDKIT=1

# Enable caching
docker compose build --parallel

# Use multi-stage builds (already configured)
```

### 7.2 Performance Tuning

**PostgreSQL:**

```sql
-- Increase shared_buffers
ALTER SYSTEM SET shared_buffers = '256MB';

-- Increase work_mem
ALTER SYSTEM SET work_mem = '16MB';

-- Reload config
SELECT pg_reload_conf();
```

**Redis:**

```bash
# Edit redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
```

**Nginx:**

```nginx
# Increase worker connections
worker_processes auto;
worker_connections 4096;

# Enable gzip compression
gzip on;
gzip_types text/plain text/css application/json application/javascript;
```

### 7.3 Security Hardening

```bash
# Run security audit
docker scan clawseum-backend:latest

# Update dependencies
docker compose build --no-cache --pull

# Use non-root users in Dockerfiles (already configured)

# Enable firewall
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Rotate secrets regularly
fly secrets set JWT_SECRET=$(openssl rand -base64 32)
```

### 7.4 Getting Help

- **Documentation:** Check [docs/](.)
- **Issues:** Open GitHub issue with logs and configuration
- **Logs:** Always include `docker compose logs` output
- **Discord:** Join community for real-time support

---

## Next Steps

- [Architecture Overview](./ARCHITECTURE.md)
- [API Documentation](./API-GUIDE.md)
- [Launch Playbook](./LAUNCH-PLAYBOOK.md)
- [Contributing Guide](../CONTRIBUTING.md)
