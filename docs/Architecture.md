# Architecture Documentation
## Stock Market Analytics Platform

**Version:** 1.0 | **Last Updated:** January 2026

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Next.js Frontend (React)                     │   │
│  │  - UI Components  - State Management  - API Client       │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS/REST API
┌────────────────────────────▼────────────────────────────────────┐
│                         VPS SERVER                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Nginx Reverse Proxy                      │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │              FastAPI Backend (Python)                      │ │
│  │  Auth Service │ Analysis Orchestrator │ Cache Manager      │ │
│  │  Sentimental  │ Fundamental │ Technical Engines            │ │
│  │  External API Client Layer (News, Twitter, Financial)      │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │              PostgreSQL Database                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture Principles
1. **Separation of Concerns:** Isolated frontend, backend, engines, storage
2. **Stateless Services:** Enable horizontal scaling
3. **Caching First:** Minimize external API costs
4. **Microservice-Ready:** Modular design for future extraction
5. **Containerization:** Docker for consistency
6. **Security First:** Auth, validation at every layer

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 14.x, React 18.x, Tailwind CSS, Recharts | SSR, UI, styling, visualization |
| **Backend** | FastAPI, SQLAlchemy 2.x, Pydantic 2.x, httpx | Async API, ORM, validation, HTTP client |
| **Analysis** | transformers, vaderSentiment, pandas, numpy, ta-lib | NLP, financial metrics, technical indicators |
| **Database** | PostgreSQL 16.x | Relational storage |
| **Infrastructure** | Docker, Nginx, Ubuntu 22.04, Let's Encrypt | Containerization, proxy, SSL |

---

## 3. Directory Structure

### Frontend
```
frontend/
├── app/(auth)/, dashboard/, analyze/, history/, profile/
├── components/ui/, charts/, analysis/, layout/
├── lib/api.js, auth.js, utils.js
└── middleware.js
```

### Backend
```
backend/
├── app/
│   ├── main.py, config.py, database.py
│   ├── models/, schemas/, routers/
│   ├── services/auth_service.py, analysis_orchestrator.py, cache_manager.py
│   ├── engines/sentimental/, fundamental/, technical/
│   ├── integrations/news_api.py, twitter_api.py, stock_data_api.py
│   └── utils/, middleware/
├── tests/, alembic/
└── Dockerfile
```

---

## 4. API Endpoints

```
# Auth
POST   /api/auth/register, login, logout, refresh

# Analysis
POST   /api/analyze/sentimental, fundamental, technical, combined

# User
GET    /api/user/profile, history
PUT    /api/user/profile
DELETE /api/user/history/{id}

# Utility
GET    /api/health, /api/tickers/search?q={query}
```

---

## 5. Analysis Engines

### Sentimental Engine
**Input:** `{ticker, market}` → **Process:** Cache check → Fetch news/tweets → Sentiment analysis → Aggregate scores

**Output:** `{overall_sentiment, score (-1 to 1), news/social breakdown, trend, confidence}`

### Fundamental Engine
**Input:** `{ticker, market}` → **Process:** Cache check → Fetch reports → Calculate ratios → Peer comparison → Trend analysis

**Output:** `{rating, score (0-10), key_metrics (PE, ROE, D/E), trends, peer_rank, strengths, concerns}`

### Technical Engine
**Input:** `{ticker, market, timeframe}` → **Process:** Cache check → Fetch OHLCV → Calculate indicators → Detect patterns

**Output:** `{rating, signal_strength, indicators (RSI, MACD, MAs, Bollinger), support/resistance, patterns, signals}`

---

## 6. Database Schema

```sql
-- Core Tables
users (id, email, password_hash, full_name, created_at, is_active)
analysis_history (id, user_id, ticker, market, analysis_types, results, created_at)

-- Cache Tables
cache_news (id, ticker, market, content, source, published_at, cached_at, expires_at)
cache_tweets (id, ticker, market, content, tweet_id, posted_at, cached_at, expires_at)
cache_financial_reports (id, ticker, market, report_type, report_period, content, cached_at, expires_at)
cache_price_data (id, ticker, market, timeframe, ohlcv_data, cached_at, expires_at)

-- Logging
api_logs (id, service, endpoint, ticker, response_status, credits_used, cached, created_at)
```

---

## 7. Data Flow

### Analysis Request Flow
```
User inputs ticker + engines → Auth Middleware (JWT) → Analysis Orchestrator
    ↓
Parallel execution: Sentimental | Fundamental | Technical
    ↓
Each engine: Cache check → If MISS: External APIs → Process → Store cache
    ↓
Aggregate results → Save to history → Return response
```

---

## 8. Security

### Authentication
- JWT tokens: Access (15 min) + Refresh (7 days)
- bcrypt password hashing (cost 12)

### API Security
- Rate limiting: 100 req/hr per user, 20 analysis/hr
- Pydantic validation, ORM (SQL injection), output encoding (XSS)
- CORS restricted to production domains

### Network
- HTTPS/TLS 1.2+, HSTS enabled
- Firewall: 80, 443, 22 (restricted) only
- PostgreSQL: localhost only

---

## 9. Deployment

### Docker Compose Services
- **frontend:** Next.js on port 3000
- **backend:** FastAPI on port 8000
- **db:** PostgreSQL 16-alpine
- **nginx:** Reverse proxy with SSL

### VPS Setup
```bash
# 1. Install Docker
curl -fsSL https://get.docker.com | sh

# 2. Configure firewall
sudo ufw allow 22/tcp 80/tcp 443/tcp && sudo ufw enable

# 3. Deploy
git clone <repo> && cd stock-analytics
cp .env.example .env && docker-compose up -d

# 4. SSL
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com

# 5. Database
docker-compose exec backend alembic upgrade head
```

---

## 10. Scalability

### Current (Phase 1)
Single VPS: Good for 10-50 concurrent users

### Future Scaling Options
1. Separate database server
2. Load balancer + multiple backend instances
3. Extract engines to microservices
4. Add Redis caching layer
5. Celery + Redis for async tasks
6. CDN for frontend assets

---

## 11. Monitoring

### Health Check (`GET /api/health`)
```json
{"status": "healthy", "services": {"database": "healthy", "external_apis": {...}}}
```

### Key Metrics
- System: CPU, memory, disk, network
- App: Request rate, response time (p50/p95/p99), error rate, cache hit rate
- Business: DAU/MAU, analyses per user, API costs

---

## 12. Backups

**Strategy:** Daily at 2 AM UTC, retain 7 daily + 4 weekly + 3 monthly

```bash
# Backup
docker-compose exec -T db pg_dump -U user stockanalytics | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip < backup.sql.gz | docker-compose exec -T db psql -U user stockanalytics
```

---

## 13. Security Checklist

- [ ] HTTPS/TLS, JWT auth, bcrypt hashing
- [ ] Rate limiting, input validation
- [ ] SQL injection/XSS prevention
- [ ] CORS, security headers (HSTS, X-Frame-Options)
- [ ] Firewall, SSH key-only, secrets in env vars
- [ ] Database localhost-only access

---

## 14. Cost Estimation

| Item | Monthly (USD) |
|------|---------------|
| VPS (4 vCPU, 8GB) | $20-40 |
| Domain + SSL | $2 |
| Backups (100GB) | $5 |
| External APIs | $50-200 |
| **Total** | **$80-250** |