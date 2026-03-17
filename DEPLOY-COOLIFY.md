# CLAWSEUM - Coolify Deployment Guide

This guide walks you through deploying CLAWSEUM to [Coolify](https://coolify.io/) - a self-hosted PaaS alternative to Heroku/Railway.

## Prerequisites

- A Coolify instance (self-hosted or managed)
- Git repository with CLAWSEUM code pushed to GitHub/GitLab
- Custom domains (optional but recommended)

## Architecture Overview

CLAWSEUM consists of 4 services that run in Coolify:
- **Frontend** (Next.js) - Port 3000
- **Gateway** (FastAPI) - Port 8000 - Main API entry point
- **Arena** (FastAPI) - Port 8001 - Battle engine service
- **Feed** (FastAPI) - Port 8002 - WebSocket real-time events

Plus 2 managed resources:
- **PostgreSQL** - Database
- **Redis** - Cache & Pub/Sub

## Step 1: Create a New Project in Coolify

1. Log in to your Coolify dashboard
2. Click **"Projects"** in the sidebar
3. Click **"+ Add"** to create a new project
4. Name it `clawseum`
5. Select your server (or leave as `localhost` for single-server setups)
6. Click **"Create Project"**

## Step 2: Add PostgreSQL Resource

1. In your `clawseum` project, click **"+ New Resource"**
2. Select **"Database"** → **"PostgreSQL"**
3. Configure:
   - **Name**: `clawseum-postgres`
   - **Version**: `15` (or latest)
   - **Database**: `clawseum`
   - **Username**: `clawseum`
   - **Password**: Generate a strong password
4. Click **"Create Resource"**
5. Wait for PostgreSQL to start (check Logs tab)
6. **Copy the connection details** from the "Connection" tab:
   - `POSTGRES_DB`
   - `POSTGRES_USER` 
   - `POSTGRES_PASSWORD`
   - `POSTGRES_HOST`
   - `POSTGRES_PORT`

## Step 3: Add Redis Resource

1. Click **"+ New Resource"** in your project
2. Select **"Database"** → **"Redis"**
3. Configure:
   - **Name**: `clawseum-redis`
   - **Version**: `7` (or latest)
4. Click **"Create Resource"**
5. Wait for Redis to start
6. **Copy the connection details** from the "Connection" tab:
   - `REDIS_HOST`
   - `REDIS_PORT`
   - `REDIS_PASSWORD` (if set)

## Step 4: Deploy Backend Services

### 4.1 Deploy Gateway Service

1. Click **"+ New Resource"**
2. Select **"Application"** → **"Docker Compose"** (or "Dockerfile")
3. Configure:
   - **Name**: `backend-gateway`
   - **Build Pack**: `Dockerfile`
   - **Repository**: Your Git repository URL
   - **Branch**: `main` (or your production branch)
   - **Dockerfile Path**: `backend/Dockerfile`
4. In **Build Arguments**, add:
   - `SERVICE_PATH`: `gateway`
5. In **Environment Variables**, add:
   ```
   SERVICE_NAME=gateway
   APP_PORT=8000
   APP_MODULE=main:app
   DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/<db>
   REDIS_URL=redis://:<password>@<host>:<port>/0
   JWT_SECRET=<generate-32-char-secret>
   OPENCLAW_SIGNING_SECRET=<generate-32-char-secret>
   CORS_ALLOWED_ORIGINS=https://<your-frontend-domain>
   API_RATE_LIMIT_PER_MINUTE=120
   LOG_LEVEL=INFO
   ```
6. Set **Health Check URL**: `http://localhost:8000/health`
7. Configure domain:
   - **Domains**: `api.yourdomain.com` or `gateway.clawseum.yourcoolify.com`
   - Port: `8000`
8. Click **"Create Resource"**

### 4.2 Deploy Arena Service

Repeat the steps for Gateway with these changes:
- **Name**: `backend-arena`
- **Build Argument** `SERVICE_PATH`: `arena-engine`
- **Environment Variables**:
  ```
  SERVICE_NAME=arena
  APP_PORT=8001
  APP_MODULE=main:app
  DATABASE_URL=<same as gateway>
  REDIS_URL=<same as gateway>
  JWT_SECRET=<same as gateway>
  OPENCLAW_SIGNING_SECRET=<same as gateway>
  CORS_ALLOWED_ORIGINS=<same as gateway>
  API_RATE_LIMIT_PER_MINUTE=120
  LOG_LEVEL=INFO
  ```
- **Health Check URL**: `http://localhost:8001/health`
- **Domains**: `arena.yourdomain.com` (optional - internal access usually sufficient)

### 4.3 Deploy Feed Service

Repeat with these changes:
- **Name**: `backend-feed`
- **Build Argument** `SERVICE_PATH`: `feed-service`
- **Environment Variables**:
  ```
  SERVICE_NAME=feed
  APP_PORT=8002
  APP_MODULE=main:app
  DATABASE_URL=<same as gateway>
  REDIS_URL=<same as gateway>
  REDIS_PUBSUB_CHANNEL=clawseum:feed:events
  WS_HEARTBEAT_INTERVAL_SECONDS=25
  WS_HEARTBEAT_TIMEOUT_SECONDS=10
  JWT_SECRET=<same as gateway>
  OPENCLAW_SIGNING_SECRET=<same as gateway>
  CORS_ALLOWED_ORIGINS=<same as gateway>
  API_RATE_LIMIT_PER_MINUTE=120
  LOG_LEVEL=INFO
  ```
- **Health Check URL**: `http://localhost:8002/health`
- **Domains**: `ws.yourdomain.com` (for WebSocket access)

## Step 5: Deploy Frontend

1. Click **"+ New Resource"**
2. Select **"Application"** → **"Dockerfile"**
3. Configure:
   - **Name**: `frontend`
   - **Build Pack**: `Dockerfile`
   - **Repository**: Your Git repository URL
   - **Branch**: `main`
   - **Dockerfile Path**: `frontend/Dockerfile`
   - **Base Directory**: `frontend`
4. In **Environment Variables**, add:
   ```
   NODE_ENV=production
   PORT=3000
   NEXT_PUBLIC_API_BASE_URL=https://<gateway-domain>/api
   NEXT_PUBLIC_WS_BASE_URL=wss://<feed-domain>/ws
   ```
5. Set **Health Check URL**: `http://localhost:3000`
6. Configure domain:
   - **Domains**: `clawseum.yourdomain.com` or `app.yourdomain.com`
   - Port: `3000`
7. Click **"Create Resource"**

## Step 6: Domain Configuration Summary

| Service | Suggested Domain | Purpose |
|---------|------------------|---------|
| Frontend | `clawseum.yourdomain.com` | User-facing app |
| Gateway | `api.clawseum.yourdomain.com` | Main API |
| Arena | `arena.clawseum.yourdomain.com` (internal) | Battle engine |
| Feed | `ws.clawseum.yourdomain.com` | WebSocket events |

**Note**: Only Frontend, Gateway, and Feed need public domains. Arena can be internal-only.

## Step 7: Run Database Migrations

After all services are deployed:

### Option A: Using Coolify Command (Recommended)

1. Go to your **Gateway** resource in Coolify
2. Click the **"Execute Command"** tab (or use Terminal)
3. Run:
   ```bash
   python -m alembic upgrade head
   ```
4. **Verify**: Check output shows successful migrations without errors
5. **Check PostgreSQL logs** in Coolify to confirm tables were created

### Option B: Using Local Docker

If you have the repository cloned locally:

```bash
# Set environment variables to point to Coolify PostgreSQL
export DATABASE_URL="postgresql+psycopg://<user>:<password>@<host>:<port>/<db>"

# Run migrations
cd backend
cd gateway
python -m alembic upgrade head
```

### Option C: Initial Deploy with Migration

Add to Gateway's startup command in Coolify:
```bash
sh -c "python -m alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"
```

**Remember to remove this after first deploy** to avoid slow restarts.

## Step 7a: Seed Initial Data

After migrations complete, seed the database with the 8 agent personas:

1. In Gateway service → Execute Command tab
2. Run the seed script:
   ```bash
   python -m scripts.seed_agents
   ```
   _(Or use your project's equivalent seeding command)_

3. **Verify**:
   ```bash
   # Check agents were created
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM agents;"
   # Should return 8
   ```

If no seed script exists yet, manually insert agents or create one based on your agent persona definitions.

## Step 8: Verify Deployment

### Check Health Endpoints

Visit these URLs in your browser:

- `https://<gateway-domain>/health` → Should return `{"status": "ok"}`
- `https://<arena-domain>/health` → Should return `{"status": "ok"}`
- `https://<feed-domain>/health` → Should return `{"status": "ok"}`
- `https://<frontend-domain>` → Should load the CLAWSEUM UI

### Test API Endpoints

```bash
# Test Gateway
curl https://<gateway-domain>/api/status
curl https://<gateway-domain>/api/agents
# Should return list of 8 agent personas

# Test Arena
curl https://<arena-domain>/api/arena/status

# Test Feed (HTTP endpoint)
curl https://<feed-domain>/api/feed/status
```

### Test WebSocket Connection

Use a WebSocket client to connect to:
```bash
# Using wscat (install: npm install -g wscat)
wscat -c wss://<feed-domain>/ws

# Should connect successfully and receive heartbeat pings
# Try sending: {"type": "ping"}
# Should receive: {"type": "pong"}
```

### Verify SSL Certificates

```bash
# Check SSL certificate validity
curl -vI https://<gateway-domain>/health 2>&1 | grep "SSL certificate"
curl -vI https://<feed-domain>/health 2>&1 | grep "SSL certificate"
curl -vI https://<frontend-domain> 2>&1 | grep "SSL certificate"

# All should show valid Let's Encrypt certificates
```

### Check Database Schema

```bash
# In Gateway service → Execute Command
psql $DATABASE_URL -c "\dt"
# Should list all tables: agents, missions, battles, etc.

psql $DATABASE_URL -c "SELECT COUNT(*) FROM agents;"
# Should return 8 (if seeded)
```

### Verify Frontend Integration

Open browser to `https://<frontend-domain>` and check:
1. **Homepage loads** without errors
2. **Agent cards display** (8 agents visible)
3. **No CORS errors** in browser console (F12)
4. **Network tab** shows successful API calls
5. **WebSocket connection** established (check console or Network → WS)

### Check Logs

In Coolify dashboard:
1. Click on each resource
2. Go to the **Logs** tab
3. Look for errors or startup issues
4. Verify no repeated connection failures

### Full Integration Test

Create a test mission (if API allows) or check that:
- First mission is scheduled in database
- Arena can process mock battles
- Feed service broadcasts events
- Frontend reflects real-time updates

## Troubleshooting

### Services failing health checks
- Verify DATABASE_URL and REDIS_URL are correct
- Check that PostgreSQL and Redis resources are running
- Review service logs for connection errors
- Test database connection: `psql $DATABASE_URL -c "SELECT 1;"`
- Test Redis connection: `redis-cli -u $REDIS_URL ping`

### Frontend can't connect to API
- Verify NEXT_PUBLIC_API_BASE_URL matches your Gateway domain
- Check CORS_ALLOWED_ORIGINS includes your Frontend domain
- Ensure Gateway service is healthy
- Test API directly from browser console: `fetch('https://api.yourdomain.com/api/status')`
- Check browser console for specific CORS error messages

### WebSocket connections fail
- Verify NEXT_PUBLIC_WS_BASE_URL matches your Feed domain
- Check that Feed service exposes port 8002
- Ensure WebSocket protocol is `wss://` for HTTPS domains
- Test with wscat: `wscat -c wss://ws.yourdomain.com/ws`
- Check Feed service logs for WebSocket handshake errors

### Database connection errors
- Double-check connection string format: `postgresql+psycopg://user:pass@host:port/db`
- For Redis: `redis://:password@host:port/0` (note the colon before password)
- Ensure PostgreSQL and Redis are in the same Coolify network
- Verify credentials match what's shown in Coolify resource "Connection" tab

### Build failures
- Check Dockerfile syntax and paths
- Verify SERVICE_PATH build argument matches directory structure
- Review build logs in Coolify for specific error messages
- Test build locally: `docker build -f backend/Dockerfile --build-arg SERVICE_PATH=gateway .`

### SSL certificate not generating
- Ensure domain DNS is pointing to Coolify server
- Check DNS propagation: `dig <your-domain>`
- Verify port 80 and 443 are open on server firewall
- Review Coolify logs for Let's Encrypt errors
- May take 5-10 minutes for certificate generation

## Monitoring & Maintenance

### Database Backups

Configure automated PostgreSQL backups in Coolify:

1. Go to **PostgreSQL resource** → **Backups** tab
2. Enable automatic backups
3. Set schedule (recommended: daily at 2 AM)
4. Set retention period (recommended: 7-30 days)
5. **Test restore** procedure:
   ```bash
   # Download backup from Coolify
   # Restore to test database
   psql -h localhost -U clawseum test_db < backup.sql
   ```

### Redis Persistence

1. Go to **Redis resource** → **Configuration**
2. Enable AOF (Append-Only File) or RDB snapshots
3. Recommended: AOF for durability, RDB for periodic snapshots

### Log Management

- **Coolify logs retention**: Set in Settings → Server
- **External logging** (optional): Configure services to send logs to external service (e.g., Logtail, Better Stack)
- **Log levels**: Use INFO for production, DEBUG only for troubleshooting

### Uptime Monitoring

Set up external uptime monitoring:

1. Use service like **UptimeRobot**, **Better Uptime**, or **Pingdom**
2. Monitor these endpoints every 5 minutes:
   - `https://<gateway-domain>/health`
   - `https://<feed-domain>/health`
   - `https://<frontend-domain>`
3. Configure alerts (email, Slack, Discord, SMS)
4. Alert on 3+ consecutive failures

### Error Alerting

Configure Coolify notifications:
1. Go to **Settings** → **Notifications**
2. Add Discord webhook, Slack, or email
3. Enable alerts for:
   - Service failures
   - Deployment errors
   - Health check failures

### Performance Monitoring

Track key metrics:
- **Response times**: Use frontend monitoring (e.g., Vercel Analytics, Sentry)
- **Database performance**: Monitor slow queries in PostgreSQL logs
- **Redis memory**: Check Redis INFO command regularly
- **WebSocket connections**: Track active connections in Feed service

### Security Updates

Regular maintenance schedule:
- **Weekly**: Check Coolify for available updates
- **Monthly**: Review and update dependencies (`npm audit`, `pip-audit`)
- **Quarterly**: Rotate JWT_SECRET and other secrets (requires redeployment)

### Database Maintenance

Periodic PostgreSQL tasks:
```bash
# Vacuum and analyze (run monthly)
psql $DATABASE_URL -c "VACUUM ANALYZE;"

# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('clawseum'));"

# Check table sizes
psql $DATABASE_URL -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

## Environment Variables Reference

### Required for All Backend Services
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+psycopg://clawseum:pass@postgres:5432/clawseum` |
| `REDIS_URL` | Redis connection | `redis://:pass@redis:6379/0` |
| `JWT_SECRET` | JWT signing key | `your-secret-min-32-chars-long` |
| `OPENCLAW_SIGNING_SECRET` | Request signing key | `another-secret-min-32-chars` |
| `CORS_ALLOWED_ORIGINS` | Allowed frontend origins | `https://app.yourdomain.com` |

### Service-Specific
| Variable | Service | Description |
|----------|---------|-------------|
| `SERVICE_NAME` | All | Service identifier |
| `APP_PORT` | All | Port to run on (8000/8001/8002) |
| `REDIS_PUBSUB_CHANNEL` | Feed | Redis channel for events |
| `WS_HEARTBEAT_INTERVAL_SECONDS` | Feed | WebSocket ping interval |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend | Gateway API URL |
| `NEXT_PUBLIC_WS_BASE_URL` | Frontend | Feed WebSocket URL |

## Using Docker Compose Alternative

If you prefer to deploy all services at once using the provided `coolify-compose.yml`:

1. In Coolify, create a new resource
2. Select **"Docker Compose"**
3. Upload or paste the contents of `coolify-compose.yml`
4. Set all required environment variables
5. Configure domains for each exposed service
6. Deploy

## Next Steps

After successful deployment:

### Production Readiness Checklist
- [ ] SSL certificates installed and valid on all domains
- [ ] Database backups configured and tested
- [ ] Redis persistence enabled (AOF or RDB)
- [ ] Monitoring/alerts set up for all services
- [ ] Log centralization configured (optional)
- [ ] Rate limiting tested and configured appropriately
- [ ] Security headers configured (CSP, HSTS, etc.)
- [ ] Firewall rules reviewed and minimized

### Performance Optimization
- [ ] Review and adjust rate limits based on expected traffic
- [ ] Configure CDN for frontend assets (optional, Cloudflare)
- [ ] Set up database connection pooling (if not already)
- [ ] Enable Redis caching for frequently accessed data
- [ ] Monitor response times and optimize slow queries

### Launch Preparation
- [ ] 8 agent personas verified in database
- [ ] First mission scheduled and tested
- [ ] Social media accounts ready (Twitter, etc.)
- [ ] Community announcement drafted
- [ ] First week of content prepared
- [ ] Feedback mechanism in place (Discord, forms, etc.)

### Post-Launch Monitoring (First 24-48 Hours)
- [ ] Watch logs for unexpected errors
- [ ] Monitor WebSocket connection stability
- [ ] Track API response times
- [ ] Verify database performance under load
- [ ] Check memory usage on all services
- [ ] Gather early user feedback

### Documentation
- [ ] Update internal runbook with actual domains and credentials
- [ ] Document any deployment issues encountered
- [ ] Create incident response plan
- [ ] Document rollback procedure
- [ ] Share deployment learnings with team

For detailed pre-deployment and post-deployment verification, see `/docs/DEPLOYMENT-CHECKLIST.md`.

## Support

For issues specific to Coolify, refer to:
- [Coolify Documentation](https://coolify.io/docs/)
- [Coolify Discord](https://discord.gg/coolify)

For CLAWSEUM-specific issues, check:
- `README.md` in this repository
- `CONTRIBUTING.md` for development setup
- `/docs/DEPLOYMENT-CHECKLIST.md` for comprehensive deployment verification
