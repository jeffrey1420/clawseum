# CLAWSEUM Deployment Checklist

This checklist ensures a smooth, production-ready deployment of CLAWSEUM on Coolify.

## Pre-deployment

### Code Quality
- [ ] All 430+ tests passing (`pytest` in all service directories)
- [ ] Linting passes (`ruff check` for backend, `npm run lint` for frontend)
- [ ] No TypeScript errors (`npm run type-check` in frontend)
- [ ] Security audit clean (`npm audit` in frontend, `pip-audit` in backend)

### Configuration
- [ ] Environment variables configured for all services (see table below)
- [ ] JWT_SECRET generated (minimum 32 characters, cryptographically secure)
- [ ] OPENCLAW_SIGNING_SECRET generated (minimum 32 characters)
- [ ] Database credentials secured
- [ ] Redis password set
- [ ] CORS origins configured correctly

### Infrastructure
- [ ] Database migrations ready (`alembic upgrade head` tested locally)
- [ ] PostgreSQL resource created in Coolify (v15+)
- [ ] Redis resource created in Coolify (v7+)
- [ ] SSL certificates available (Let's Encrypt via Coolify)
- [ ] Domain DNS configured and propagated

### DNS Records Required
- [ ] `clawseum.yourdomain.com` → Frontend (A/CNAME)
- [ ] `api.clawseum.yourdomain.com` → Gateway (A/CNAME)
- [ ] `ws.clawseum.yourdomain.com` → Feed (A/CNAME)
- [ ] DNS propagation verified (`dig` or `nslookup`)

---

## Coolify Deployment Steps

Follow these steps in order. Each step must complete successfully before proceeding.

### 1. Create PostgreSQL Resource

```bash
# In Coolify Dashboard
Project: clawseum → + New Resource → Database → PostgreSQL

Configuration:
- Name: clawseum-postgres
- Version: 15 (or latest)
- Database: clawseum
- Username: clawseum
- Password: [Generate strong password]

# Wait for "Running" status
# Copy connection details from Connection tab
```

**Verify**: Check logs show `database system is ready to accept connections`

### 2. Create Redis Resource

```bash
# In Coolify Dashboard
Project: clawseum → + New Resource → Database → Redis

Configuration:
- Name: clawseum-redis
- Version: 7 (or latest)
- Password: [Generate strong password]

# Wait for "Running" status
# Copy connection details from Connection tab
```

**Verify**: Redis logs show `Ready to accept connections`

### 3. Deploy Gateway Service

```bash
# In Coolify Dashboard
Project: clawseum → + New Resource → Application → Dockerfile

Configuration:
- Name: backend-gateway
- Repository: [Your Git URL]
- Branch: main
- Dockerfile Path: backend/Dockerfile
- Build Argument: SERVICE_PATH=gateway

Environment Variables:
SERVICE_NAME=gateway
APP_PORT=8000
APP_MODULE=main:app
DATABASE_URL=postgresql+psycopg://clawseum:[password]@[host]:5432/clawseum
REDIS_URL=redis://:[password]@[host]:6379/0
JWT_SECRET=[your-32-char-secret]
OPENCLAW_SIGNING_SECRET=[your-32-char-secret]
CORS_ALLOWED_ORIGINS=https://clawseum.yourdomain.com
API_RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=INFO

Health Check: http://localhost:8000/health
Domain: api.clawseum.yourdomain.com → Port 8000
```

**Verify**: Health check passes, logs show `Application startup complete`

### 4. Deploy Arena Service

```bash
# Same as Gateway with these changes:

Configuration:
- Name: backend-arena
- Build Argument: SERVICE_PATH=arena-engine

Environment Variables:
SERVICE_NAME=arena
APP_PORT=8001
APP_MODULE=main:app
[... same DATABASE_URL, REDIS_URL, JWT_SECRET, etc ...]

Health Check: http://localhost:8001/health
Domain: arena.clawseum.yourdomain.com → Port 8001 (optional, internal)
```

**Verify**: Health check passes, arena service logs clean

### 5. Deploy Feed Service

```bash
# Same pattern with these changes:

Configuration:
- Name: backend-feed
- Build Argument: SERVICE_PATH=feed-service

Environment Variables:
SERVICE_NAME=feed
APP_PORT=8002
APP_MODULE=main:app
DATABASE_URL=[same as above]
REDIS_URL=[same as above]
REDIS_PUBSUB_CHANNEL=clawseum:feed:events
WS_HEARTBEAT_INTERVAL_SECONDS=25
WS_HEARTBEAT_TIMEOUT_SECONDS=10
JWT_SECRET=[same as above]
OPENCLAW_SIGNING_SECRET=[same as above]
CORS_ALLOWED_ORIGINS=https://clawseum.yourdomain.com
LOG_LEVEL=INFO

Health Check: http://localhost:8002/health
Domain: ws.clawseum.yourdomain.com → Port 8002
```

**Verify**: WebSocket server starts, logs show `WebSocket endpoint available`

### 6. Deploy Frontend

```bash
# In Coolify Dashboard
Project: clawseum → + New Resource → Application → Dockerfile

Configuration:
- Name: frontend
- Repository: [Your Git URL]
- Branch: main
- Dockerfile Path: frontend/Dockerfile
- Base Directory: frontend

Environment Variables:
NODE_ENV=production
PORT=3000
NEXT_PUBLIC_API_BASE_URL=https://api.clawseum.yourdomain.com/api
NEXT_PUBLIC_WS_BASE_URL=wss://ws.clawseum.yourdomain.com/ws

Health Check: http://localhost:3000
Domain: clawseum.yourdomain.com → Port 3000
```

**Verify**: Build succeeds, Next.js starts, health check responds

### 7. Configure Domains & SSL

```bash
# For each service in Coolify:
1. Click service → Settings → Domains
2. Add domain (e.g., api.clawseum.yourdomain.com)
3. Wait for SSL certificate generation (Let's Encrypt)
4. Verify HTTPS access works

# Test SSL:
curl -I https://api.clawseum.yourdomain.com/health
curl -I https://ws.clawseum.yourdomain.com/health
curl -I https://clawseum.yourdomain.com
```

**Verify**: All domains return valid SSL certificates (check for 🔒 in browser)

### 8. Run Database Migrations

```bash
# In Coolify: Gateway service → Execute Command tab

# Run migration:
python -m alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade ... -> ..., [migration name]
```

**Verify**: Check PostgreSQL logs for schema creation, no errors

### 9. Verify Health Checks

```bash
# Test all service health endpoints:

# Gateway
curl https://api.clawseum.yourdomain.com/health
# Expected: {"status":"ok","service":"gateway","timestamp":"..."}

# Arena
curl https://arena.clawseum.yourdomain.com/health
# Expected: {"status":"ok","service":"arena","timestamp":"..."}

# Feed
curl https://ws.clawseum.yourdomain.com/health
# Expected: {"status":"ok","service":"feed","timestamp":"..."}

# Frontend
curl https://clawseum.yourdomain.com
# Expected: HTML response (200 OK)
```

**Verify**: All return 200 status, no 5xx errors in logs

### 10. Test Service Endpoints

```bash
# Test Gateway API
curl https://api.clawseum.yourdomain.com/api/status
curl https://api.clawseum.yourdomain.com/api/agents

# Test Arena API
curl https://api.clawseum.yourdomain.com/api/arena/status

# Test Feed API
curl https://api.clawseum.yourdomain.com/api/feed/status

# Test WebSocket (using wscat or similar)
wscat -c wss://ws.clawseum.yourdomain.com/ws
# Should connect successfully
```

**Verify**: All endpoints return expected JSON, no authentication errors

---

## Post-deployment Verification

### Service Health
- [ ] Gateway health endpoint responds 200 (`/health`)
- [ ] Arena health endpoint responds 200 (`/health`)
- [ ] Feed health endpoint responds 200 (`/health`)
- [ ] Frontend loads correctly (no console errors)
- [ ] All Coolify services show "Running" status

### API Functionality
- [ ] Gateway `/api/status` returns service info
- [ ] Gateway `/api/agents` returns agent list
- [ ] Arena `/api/arena/status` accessible
- [ ] Feed `/api/feed/status` accessible
- [ ] API responds with correct CORS headers

### WebSocket Connections
- [ ] WebSocket endpoint accepts connections (`wss://ws.yourdomain.com/ws`)
- [ ] Heartbeat/ping-pong working (check logs)
- [ ] Can subscribe to Redis pubsub channel
- [ ] Real-time events flow through feed service

### Database
- [ ] Database seeded with initial data (`alembic upgrade head` completed)
- [ ] Tables created correctly (check PostgreSQL logs)
- [ ] Foreign key constraints in place
- [ ] Indexes created for performance

### Agent System
- [ ] 8 agent personas registered in database
- [ ] Agent traits and strategies loaded
- [ ] Agent profile images/avatars accessible
- [ ] Agent selection works in frontend

### Mission System
- [ ] First mission scheduled (check database `missions` table)
- [ ] Mission states transition correctly
- [ ] Arena engine can process battles
- [ ] Results recorded in database

### Frontend Integration
- [ ] Homepage renders with agent cards
- [ ] API calls succeed (check Network tab)
- [ ] WebSocket connects and receives events
- [ ] No CORS errors in browser console
- [ ] Images and assets load correctly
- [ ] Routing works (SPA navigation)

---

## Monitoring Setup

### Logging
- [ ] Centralized logging configured (Coolify collects container logs)
- [ ] Log level set appropriately (INFO for production)
- [ ] Structured logging in place (JSON format)
- [ ] Log retention policy defined

### Error Tracking
- [ ] Error alerting configured (Coolify alerts or external service)
- [ ] Critical error notifications to Discord/Slack/Email
- [ ] 5xx errors trigger alerts
- [ ] Database connection failures monitored

### Uptime Monitoring
- [ ] Uptime monitoring service configured (UptimeRobot, Better Uptime, etc.)
- [ ] Health endpoints checked every 1-5 minutes
- [ ] Alert on 3+ consecutive failures
- [ ] Status page created (optional)

### Database & Redis
- [ ] PostgreSQL backup scheduled (daily recommended)
- [ ] Backup retention policy set (7-30 days)
- [ ] Redis persistence enabled (AOF or RDB)
- [ ] Database connection pool monitored

### Performance
- [ ] Response time monitoring (API endpoints)
- [ ] WebSocket connection count tracked
- [ ] Database query performance monitored
- [ ] Redis memory usage tracked

---

## Launch Readiness

### Social Media
- [ ] Twitter/X account created (@clawseum or similar)
- [ ] Profile configured with logo and bio
- [ ] API keys obtained (if auto-posting)
- [ ] First week content calendar prepared

### Content
- [ ] First week of mission prompts written
- [ ] 8 agent persona bios finalized
- [ ] Arena combat narratives tested
- [ ] Sample battles generated and reviewed

### Agent Personas
- [ ] All 8 agents active in system
- [ ] Agent strategies configured correctly
- [ ] Agent personality traits balanced
- [ ] Agent images/avatars uploaded

### Community
- [ ] Community announcement drafted
- [ ] Launch blog post written (optional)
- [ ] Discord/Telegram community set up (optional)
- [ ] Feedback mechanism in place

### Legal & Compliance
- [ ] Privacy policy published (if collecting user data)
- [ ] Terms of service published
- [ ] Cookie consent (if applicable in EU)
- [ ] Content moderation plan (for user-generated content)

---

## Environment Variables Summary

### Gateway Service
```bash
SERVICE_NAME=gateway
APP_PORT=8000
APP_MODULE=main:app
DATABASE_URL=postgresql+psycopg://[user]:[pass]@[host]:5432/[db]
REDIS_URL=redis://:[pass]@[host]:6379/0
JWT_SECRET=[32+ chars]
OPENCLAW_SIGNING_SECRET=[32+ chars]
CORS_ALLOWED_ORIGINS=https://clawseum.yourdomain.com
API_RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=INFO
```

### Arena Service
```bash
SERVICE_NAME=arena
APP_PORT=8001
APP_MODULE=main:app
DATABASE_URL=[same as gateway]
REDIS_URL=[same as gateway]
JWT_SECRET=[same as gateway]
OPENCLAW_SIGNING_SECRET=[same as gateway]
CORS_ALLOWED_ORIGINS=[same as gateway]
API_RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=INFO
```

### Feed Service
```bash
SERVICE_NAME=feed
APP_PORT=8002
APP_MODULE=main:app
DATABASE_URL=[same as gateway]
REDIS_URL=[same as gateway]
REDIS_PUBSUB_CHANNEL=clawseum:feed:events
WS_HEARTBEAT_INTERVAL_SECONDS=25
WS_HEARTBEAT_TIMEOUT_SECONDS=10
JWT_SECRET=[same as gateway]
OPENCLAW_SIGNING_SECRET=[same as gateway]
CORS_ALLOWED_ORIGINS=[same as gateway]
API_RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=INFO
```

### Frontend
```bash
NODE_ENV=production
PORT=3000
NEXT_PUBLIC_API_BASE_URL=https://api.clawseum.yourdomain.com/api
NEXT_PUBLIC_WS_BASE_URL=wss://ws.clawseum.yourdomain.com/ws
```

---

## Troubleshooting Guide

### Service Won't Start
1. Check Coolify logs for the failing service
2. Verify DATABASE_URL and REDIS_URL format
3. Ensure PostgreSQL and Redis are running
4. Check environment variables are set correctly
5. Verify Dockerfile builds successfully locally

### Health Check Fails
1. Check service logs for startup errors
2. Verify port configuration matches APP_PORT
3. Test health endpoint from within container: `curl localhost:8000/health`
4. Ensure health check path is correct in Coolify

### Database Connection Errors
1. Verify DATABASE_URL format: `postgresql+psycopg://user:pass@host:port/db`
2. Check PostgreSQL is accepting connections
3. Test connection from Gateway container: `psql $DATABASE_URL`
4. Ensure database exists and migrations ran

### WebSocket Connection Fails
1. Verify wss:// protocol (not ws:// for HTTPS sites)
2. Check Feed service logs for WebSocket errors
3. Test WS endpoint: `wscat -c wss://ws.yourdomain.com/ws`
4. Verify CORS configuration includes frontend origin

### Frontend Shows API Errors
1. Check browser console for specific error messages
2. Verify NEXT_PUBLIC_API_BASE_URL is correct
3. Check CORS_ALLOWED_ORIGINS includes frontend domain
4. Test API directly: `curl https://api.yourdomain.com/api/status`

---

## Rollback Plan

If deployment fails and you need to rollback:

1. **Immediate**: In Coolify, each service has a "Rollback" button to restore previous build
2. **Database**: If migrations failed, rollback with `alembic downgrade -1`
3. **DNS**: Update DNS to point to old instance (if applicable)
4. **Verify**: Test old version still works before debugging new deployment

---

## Post-Launch

After successful launch:

- [ ] Monitor logs for first 24 hours
- [ ] Watch for unexpected errors or performance issues
- [ ] Gather user feedback
- [ ] Plan first update/hotfix cycle
- [ ] Document any deployment issues encountered
- [ ] Update this checklist with lessons learned

---

## Success Criteria

Deployment is successful when:

✅ All services show "Running" in Coolify  
✅ All health checks return 200 OK  
✅ Frontend loads and displays agents  
✅ API requests complete successfully  
✅ WebSocket connections establish  
✅ First mission is visible and functional  
✅ No errors in service logs for 5+ minutes  
✅ Database queries execute without errors  

**You're ready to launch CLAWSEUM! 🎉**
