# Architecture Documentation
## Stock Market Analytics Platform

**Version:** 1.0  
**Last Updated:** January 2026  
**Document Owner:** Engineering Team

---

## 1. Architecture Overview

### 1.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Next.js Frontend (React)                     │   │
│  │  - UI Components  - State Management  - API Client       │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS/REST API
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                         VPS SERVER                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Nginx Reverse Proxy                     │   │
│  │               (SSL Termination, Load Balancing)           │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │                                          │
│  ┌────────────────────▼─────────────────────────────────────┐   │
│  │              FastAPI Backend (Python)                     │   │
│  │  ┌──────────────┬──────────────┬──────────────────────┐  │   │
│  │  │   Auth       │   Analysis   │   Cache              │  │   │
│  │  │   Service    │   Orchestrator│  Manager             │  │   │
│  │  └──────────────┴──────────────┴──────────────────────┘  │   │
│  │  ┌──────────────┬──────────────┬──────────────────────┐  │   │
│  │  │ Sentimental  │ Fundamental  │   Technical          │  │   │
│  │  │ Engine       │ Engine       │   Engine             │  │   │
│  │  └──────────────┴──────────────┴──────────────────────┘  │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │            External API Client Layer                 │  │   │
│  │  │  (News API, Twitter API, Financial Data APIs)       │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│  ┌───────────────────────▼──────────────────────────────────┐   │
│  │              PostgreSQL Database                          │   │
│  │  - Users  - Analysis History  - Cache  - API Logs       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             │ External HTTP/REST
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
│  - News APIs  - Twitter/X API  - Stock Data APIs                │
│  - Financial Reports APIs                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Architecture Principles

1. **Separation of Concerns:** Frontend, backend, analysis engines, and data storage are isolated
2. **Stateless Services:** Backend APIs are stateless to enable horizontal scaling
3. **Caching First:** Aggressive caching to minimize external API costs
4. **Microservice-Ready:** Modular design allows future extraction of engines into microservices
5. **Containerization:** Docker for consistency across development, testing, and production
6. **Security First:** Authentication, authorization, input validation at every layer

---

## 2. Technology Stack

### 2.1 Frontend Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Next.js | 14.x | React framework with SSR, routing, API routes |
| UI Library | React | 18.x | Component-based UI |
| Styling | Tailwind CSS | 3.x | Utility-first CSS framework |
| State Management | React Context + Hooks | - | Global state management |
| Charts/Viz | Recharts / Chart.js | Latest | Data visualization |
| HTTP Client | Axios | Latest | API communication |
| Auth | NextAuth.js / Custom JWT | Latest | Authentication handling |

### 2.2 Backend Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | FastAPI | 0.115.x | High-performance async Python API framework |
| ORM | SQLAlchemy | 2.x | Database ORM |
| Database | PostgreSQL | 16.x | Relational database |
| Authentication | JWT (PyJWT) | Latest | Token-based auth |
| Password Hashing | bcrypt / passlib | Latest | Secure password storage |
| Validation | Pydantic | 2.x | Data validation (built into FastAPI) |
| Task Queue | Optional: Celery + Redis | Latest | For heavy async tasks (if needed) |
| HTTP Client | httpx / aiohttp | Latest | Async external API calls |

### 2.3 Analysis Engines (Python Libraries)

| Engine | Libraries | Purpose |
|--------|-----------|---------|
| Sentimental | transformers, vaderSentiment, nltk | NLP and sentiment analysis |
| Fundamental | pandas, numpy, yfinance (or custom) | Financial metrics calculation |
| Technical | pandas, ta-lib, numpy | Technical indicators and pattern recognition |

### 2.4 Infrastructure & DevOps

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Containerization | Docker | Application containerization |
| Orchestration | Docker Compose | Multi-container management |
| Web Server | Nginx | Reverse proxy, SSL termination, static files |
| VPS | Ubuntu 22.04 LTS | Server OS |
| SSL/TLS | Let's Encrypt (Certbot) | Free SSL certificates |
| Monitoring | Prometheus + Grafana (Optional) | System monitoring |
| Logging | Python logging + File rotation | Application logs |

---

## 3. System Components

### 3.1 Frontend Application (Next.js)

**Directory Structure:**
```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   └── register/
│   ├── dashboard/
│   ├── analyze/
│   ├── history/
│   └── profile/
├── components/
│   ├── ui/              # Reusable UI components
│   ├── charts/          # Chart components
│   ├── analysis/        # Analysis-specific components
│   └── layout/          # Layout components
├── lib/
│   ├── api.js           # API client
│   ├── auth.js          # Auth helpers
│   └── utils.js         # Utility functions
├── public/
├── styles/
└── middleware.js        # Auth middleware
```

**Key Responsibilities:**
- User authentication UI
- Ticker search and input
- Analysis engine selection
- Real-time progress indicators
- Results visualization (charts, tables, cards)
- Analysis history display
- Responsive design

**State Management:**
- User authentication state (Context API)
- Analysis results state (React hooks)
- Loading states and error handling

### 3.2 Backend API (FastAPI)

**Directory Structure:**
```
backend/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Configuration management
│   ├── database.py              # Database connection
│   ├── models/                  # SQLAlchemy models
│   │   ├── user.py
│   │   ├── analysis.py
│   │   └── cache.py
│   ├── schemas/                 # Pydantic schemas
│   │   ├── user.py
│   │   ├── analysis.py
│   │   └── auth.py
│   ├── routers/                 # API endpoints
│   │   ├── auth.py
│   │   ├── analysis.py
│   │   ├── user.py
│   │   └── health.py
│   ├── services/                # Business logic
│   │   ├── auth_service.py
│   │   ├── analysis_orchestrator.py
│   │   └── cache_manager.py
│   ├── engines/                 # Analysis engines
│   │   ├── sentimental/
│   │   │   ├── engine.py
│   │   │   ├── news_fetcher.py
│   │   │   └── twitter_fetcher.py
│   │   ├── fundamental/
│   │   │   ├── engine.py
│   │   │   └── metrics_calculator.py
│   │   └── technical/
│   │       ├── engine.py
│   │       └── indicators.py
│   ├── integrations/            # External API clients
│   │   ├── news_api.py
│   │   ├── twitter_api.py
│   │   └── stock_data_api.py
│   ├── utils/
│   │   ├── security.py
│   │   ├── validators.py
│   │   └── logger.py
│   └── middleware/
│       ├── auth_middleware.py
│       └── error_handler.py
├── tests/
├── alembic/                     # Database migrations
├── requirements.txt
└── Dockerfile
```

**API Endpoints:**

```python
# Authentication
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/logout
POST   /api/auth/refresh

# Analysis
POST   /api/analyze/sentimental
POST   /api/analyze/fundamental
POST   /api/analyze/technical
POST   /api/analyze/combined

# User
GET    /api/user/profile
PUT    /api/user/profile
GET    /api/user/history
DELETE /api/user/history/{id}

# Utility
GET    /api/health
GET    /api/tickers/search?q={query}
```

### 3.3 Analysis Engines

#### 3.3.1 Sentimental Analysis Engine

**Input:**
```python
{
  "ticker": "AAPL",
  "market": "US"
}
```

**Process:**
1. Check cache for recent news/tweets (within TTL)
2. If cache miss:
   - Fetch news articles from News API
   - Fetch tweets from Twitter API
   - Store in cache with timestamp
3. Run sentiment analysis on each article/tweet
4. Aggregate sentiment scores
5. Calculate overall sentiment rating
6. Identify most influential content

**Output:**
```python
{
  "overall_sentiment": "POSITIVE",
  "sentiment_score": 0.72,  # -1 to 1
  "news_sentiment": {
    "positive": 15,
    "neutral": 8,
    "negative": 3,
    "top_articles": [...]
  },
  "social_sentiment": {
    "positive": 245,
    "neutral": 120,
    "negative": 56,
    "top_tweets": [...]
  },
  "trend": "IMPROVING",
  "confidence": 0.85,
  "last_updated": "2026-01-17T10:30:00Z"
}
```

#### 3.3.2 Fundamental Analysis Engine

**Input:**
```python
{
  "ticker": "RELIANCE.NS",
  "market": "IN"
}
```

**Process:**
1. Check cache for latest financial reports
2. If cache miss or outdated:
   - Fetch quarterly/annual reports
   - Store in cache
3. Calculate key ratios:
   - Profitability: ROE, ROA, Profit Margin
   - Valuation: P/E, P/B, P/S, PEG
   - Liquidity: Current Ratio, Quick Ratio
   - Leverage: Debt-to-Equity, Interest Coverage
   - Efficiency: Asset Turnover, Inventory Turnover
4. Compare with industry peers
5. Analyze trends (YoY, QoQ growth)
6. Generate fundamental score

**Output:**
```python
{
  "fundamental_rating": "STRONG BUY",
  "score": 8.2,  # 0-10
  "key_metrics": {
    "pe_ratio": 28.5,
    "roe": 0.18,
    "debt_to_equity": 0.45,
    "current_ratio": 1.8,
    "revenue_growth_yoy": 0.12
  },
  "trends": {
    "revenue": "GROWING",
    "profit": "IMPROVING",
    "debt": "STABLE"
  },
  "peer_comparison": {
    "rank": 3,
    "total_peers": 10
  },
  "strengths": ["Strong ROE", "Low debt"],
  "concerns": ["High P/E ratio"],
  "last_updated": "2026-01-15T00:00:00Z"
}
```

#### 3.3.3 Technical Analysis Engine

**Input:**
```python
{
  "ticker": "TSLA",
  "market": "US",
  "timeframe": "1D"  # Optional
}
```

**Process:**
1. Check cache for recent price data
2. If cache miss (>15 min old during market hours):
   - Fetch historical OHLCV data
   - Store in cache
3. Calculate technical indicators:
   - Moving Averages (SMA, EMA)
   - RSI (Relative Strength Index)
   - MACD (Moving Average Convergence Divergence)
   - Bollinger Bands
   - Volume analysis
4. Identify chart patterns
5. Detect support/resistance levels
6. Generate buy/sell signals

**Output:**
```python
{
  "technical_rating": "BUY",
  "signal_strength": 0.75,  # 0-1
  "indicators": {
    "rsi": 62.5,
    "macd": {"value": 2.5, "signal": "BULLISH"},
    "moving_averages": {
      "sma_50": 145.20,
      "sma_200": 138.50,
      "ema_20": 147.30
    },
    "bollinger_bands": {
      "upper": 152.00,
      "middle": 145.00,
      "lower": 138.00,
      "position": "MIDDLE"
    }
  },
  "support_resistance": {
    "support": [140.00, 135.50],
    "resistance": [150.00, 155.25]
  },
  "patterns_detected": ["ASCENDING_TRIANGLE"],
  "signals": {
    "short_term": "BUY",
    "medium_term": "HOLD",
    "long_term": "BUY"
  },
  "momentum": "BULLISH",
  "last_updated": "2026-01-17T10:45:00Z"
}
```

### 3.4 Database Schema

**PostgreSQL Tables:**

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Analysis history table
CREATE TABLE analysis_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,  -- 'US' or 'IN'
    analysis_types JSON NOT NULL,  -- ['sentimental', 'fundamental', 'technical']
    results JSON NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_ticker (ticker)
);

-- Cache table for news
CREATE TABLE cache_news (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    content JSON NOT NULL,
    source VARCHAR(100),
    published_at TIMESTAMP,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    INDEX idx_ticker_expires (ticker, expires_at)
);

-- Cache table for tweets
CREATE TABLE cache_tweets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    content JSON NOT NULL,
    tweet_id VARCHAR(100) UNIQUE,
    posted_at TIMESTAMP,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    INDEX idx_ticker_expires (ticker, expires_at)
);

-- Cache table for financial reports
CREATE TABLE cache_financial_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    report_type VARCHAR(50),  -- 'quarterly', 'annual'
    report_period VARCHAR(20),  -- 'Q1-2024', '2024'
    content JSON NOT NULL,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    INDEX idx_ticker_period (ticker, report_period),
    UNIQUE(ticker, market, report_type, report_period)
);

-- Cache table for price data
CREATE TABLE cache_price_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10),  -- '1D', '1H', '15M'
    ohlcv_data JSON NOT NULL,  -- Array of OHLCV bars
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    INDEX idx_ticker_timeframe_expires (ticker, timeframe, expires_at),
    UNIQUE(ticker, market, timeframe)
);

-- API usage logs
CREATE TABLE api_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(100) NOT NULL,  -- 'news_api', 'twitter_api', etc.
    endpoint VARCHAR(255),
    ticker VARCHAR(20),
    response_status INT,
    credits_used INT DEFAULT 1,
    cached BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_service_created (service, created_at)
);
```

---

## 4. Data Flow

### 4.1 User Authentication Flow

```
User → Frontend → POST /api/auth/login
                   ↓
              FastAPI Auth Router
                   ↓
              Auth Service
                   ↓
         1. Validate credentials
         2. Hash password check
         3. Generate JWT token
                   ↓
              ← Return JWT + User Info
                   ↓
       Frontend stores token
       Includes in Authorization header
```

### 4.2 Analysis Request Flow

```
User inputs ticker + selects engines
         ↓
Frontend → POST /api/analyze/combined
          {ticker: "AAPL", market: "US", engines: ["sentimental", "fundamental"]}
         ↓
    Auth Middleware (verify JWT)
         ↓
    Analysis Orchestrator
         ↓
    Parallel execution:
    ┌─────────────────┬─────────────────┐
    ↓                 ↓                 ↓
Sentimental      Fundamental      Technical
Engine           Engine           Engine
    ↓                 ↓                 ↓
Cache Manager     Cache Manager    Cache Manager
(check cache)     (check cache)    (check cache)
    ↓                 ↓                 ↓
If MISS:          If MISS:         If MISS:
External APIs     External APIs    External APIs
    ↓                 ↓                 ↓
Process data      Process data     Process data
    ↓                 ↓                 ↓
Store in cache    Store in cache   Store in cache
    ↓                 ↓                 ↓
    └─────────────────┴─────────────────┘
                  ↓
         Aggregate results
                  ↓
         Save to analysis_history
                  ↓
         Return combined response
                  ↓
         Frontend displays results
```

### 4.3 Cache Hit Flow

```
Analysis Engine requests data
         ↓
Cache Manager checks database
         ↓
    Is data cached AND not expired?
         ↓
    YES → Return cached data (FAST)
         ↓
    NO → Fetch from external API
       → Store in cache
       → Return fresh data
```

---

## 5. Security Architecture

### 5.1 Authentication & Authorization

**JWT-based Authentication:**
```python
# Token structure
{
  "sub": "user_id",
  "email": "user@example.com",
  "exp": 1234567890,  # Expiration timestamp
  "iat": 1234567890   # Issued at timestamp
}
```

**Token Flow:**
1. User logs in with email/password
2. Backend validates credentials
3. Backend generates access token (15 min expiry) + refresh token (7 days)
4. Frontend stores tokens (memory/httpOnly cookies)
5. Frontend includes access token in Authorization header
6. Backend validates token on each request
7. If access token expires, use refresh token to get new access token

**Password Security:**
- Bcrypt hashing with cost factor 12
- No plaintext password storage
- Password strength requirements enforced

### 5.2 API Security

**Rate Limiting:**
- Per-user: 100 requests per hour
- Per-IP: 200 requests per hour (unauthenticated)
- Analysis endpoints: 20 requests per hour per user

**Input Validation:**
- Pydantic schemas validate all inputs
- SQL injection prevention via ORM
- XSS prevention via output encoding

**CORS Configuration:**
```python
CORS_ORIGINS = [
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]
```

### 5.3 Network Security

**HTTPS/TLS:**
- Let's Encrypt SSL certificate
- TLS 1.2+ only
- HSTS header enabled
- Redirect HTTP → HTTPS

**Firewall Rules:**
- Allow: 80 (HTTP), 443 (HTTPS), 22 (SSH - restricted IPs only)
- Deny: All other inbound traffic
- PostgreSQL: localhost only (no external access)

---

## 6. Deployment Architecture

### 6.1 Docker Containerization

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/stockanalytics
      - JWT_SECRET=${JWT_SECRET}
      - NEWS_API_KEY=${NEWS_API_KEY}
      - TWITTER_API_KEY=${TWITTER_API_KEY}
    depends_on:
      - db
    volumes:
      - ./backend:/app
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=stockanalytics
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - /var/log/nginx:/var/log/nginx
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
```

**Dockerfile (Backend):**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ./app ./app

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Dockerfile (Frontend):**
```dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy application
COPY . .

# Build Next.js app
RUN npm run build

# Expose port
EXPOSE 3000

# Run application
CMD ["npm", "start"]
```

### 6.2 Nginx Configuration

```nginx
# /etc/nginx/nginx.conf

http {
    upstream frontend {
        server frontend:3000;
    }

    upstream backend {
        server backend:8000;
    }

    # HTTP to HTTPS redirect
    server {
        listen 80;
        server_name yourdomain.com www.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;

        # API routes
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Frontend routes
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### 6.3 VPS Setup Steps

1. **Initial Server Setup:**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Install Docker Compose
   sudo apt install docker-compose -y
   
   # Configure firewall
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

2. **Clone Repository & Deploy:**
   ```bash
   git clone https://github.com/yourusername/stock-analytics.git
   cd stock-analytics
   
   # Set environment variables
   cp .env.example .env
   nano .env  # Edit with your API keys
   
   # Start services
   docker-compose up -d
   ```

3. **SSL Certificate Setup:**
   ```bash
   # Install Certbot
   sudo apt install certbot python3-certbot-nginx -y
   
   # Obtain certificate
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   
   # Auto-renewal (already set up by Certbot)
   sudo certbot renew --dry-run
   ```

4. **Database Initialization:**
   ```bash
   # Run migrations
   docker-compose exec backend alembic upgrade head
   ```

---

## 7. Scalability Considerations

### 7.1 Current Architecture (Phase 1)

**Single VPS Setup:**
- All services on one server
- Good for: 10-50 concurrent users
- Cost-effective for MVP

**Bottlenecks:**
- CPU: Analysis engines (especially technical analysis)
- Memory: Caching large datasets
- I/O: Database queries

### 7.2 Future Scaling (Phase 2+)

**Horizontal Scaling Options:**

1. **Separate Database Server:**
   - Move PostgreSQL to dedicated server/managed service
   - Better performance and backups

2. **Load Balancer + Multiple Backend Instances:**
   ```
   Load Balancer
       ↓
   Backend 1  Backend 2  Backend 3
       ↓         ↓         ↓
   Shared PostgreSQL
   ```

3. **Microservices Architecture:**
   - Extract each engine into separate service
   - Independent scaling based on load

4. **Caching Layer:**
   - Add Redis for frequently accessed data
   - Reduce database load

5. **Queue System (Celery + Redis):**
   - Offload heavy analysis tasks
   - Better user experience with async processing

6. **CDN for Frontend:**
   - Serve static assets from CDN
   - Reduce server load

---

## 8. Monitoring & Observability

### 8.1 Application Logging

**Log Levels:**
- ERROR: Critical issues requiring immediate attention
- WARNING: Important events that might need attention
- INFO: General informational messages
- DEBUG: Detailed debugging information

**Log Structure:**
```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "level": "INFO",
  "service": "sentimental_engine",
  "message": "Analysis completed for AAPL",
  "ticker": "AAPL",
  "user_id": "uuid",
  "duration_ms": 1250
}
```

### 8.2 Health Checks

**Endpoint:** `GET /api/health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-17T10:30:00Z",
  "services": {
    "database": "healthy",
    "cache": "healthy",
    "external_apis": {
      "news_api": "healthy",
      "twitter_api": "degraded",
      "stock_api": "healthy"
    }
  }
}
```

### 8.3 Metrics to Monitor

**System Metrics:**
- CPU usage
- Memory usage
- Disk I/O
- Network bandwidth

**Application Metrics:**
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate
- Analysis completion time per engine
- Cache hit rate
- External API success rate
- Active users

**Business Metrics:**
- Daily/Monthly active users
- Analyses per user
- Most analyzed tickers
- API costs per analysis

---

## 9. Disaster Recovery & Backups

### 9.1 Database Backups

**Strategy:**
- Daily automated backups at 2 AM UTC
- Retain: 7 daily, 4 weekly, 3 monthly
- Store offsite (S3, Backblaze, etc.)

**Backup Script:**
```bash
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T db pg_dump -U user stockanalytics | gzip > $BACKUP_DIR/backup_$DATE.sql.gz
```

### 9.2 Recovery Procedures

**Database Restore:**
```bash
gunzip < backup_20260117.sql.gz | docker-compose exec -T db psql -U user stockanalytics
```

**Full System Recovery:**
1. Provision new VPS
2. Install Docker and Docker Compose
3. Clone repository
4. Restore database from backup
5. Configure environment variables
6. Start services with docker-compose

---

## 10. Development Workflow

### 10.1 Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Database (local)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:16
```

### 10.2 Git Workflow

```
main (production)
  ↑
develop (staging)
  ↑
feature/xyz (feature branches)
```

### 10.3 CI/CD Pipeline (Future)

```
Git Push → GitHub Actions
    ↓
1. Run tests
2. Build Docker images
3. Push to registry
4. Deploy to VPS
5. Run health checks
```

---

## 11. Cost Estimation

### 11.1 Infrastructure Costs (Monthly)

| Item | Cost (USD) |
|------|------------|
| VPS (4 vCPU, 8GB RAM) | $20-40 |
| Domain + SSL | $2 |
| Backups Storage (100GB) | $5 |
| **Total Infrastructure** | **~$30-50/mo** |

### 11.2 External API Costs (Variable)

Depends on usage and API providers. Budget $50-200/month initially.

### 11.3 Total Estimated Costs

**MVP Phase:** $80-250/month

---

## 12. Security Checklist

- [ ] HTTPS/TLS enabled
- [ ] JWT authentication implemented
- [ ] Password hashing (bcrypt)
- [ ] Rate limiting configured
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (ORM)
- [ ] XSS prevention
- [ ] CORS properly configured
- [ ] Security headers set (HSTS, X-Frame-Options, etc.)
- [ ] Firewall configured
- [ ] SSH key-based authentication (no password)
- [ ] Regular security updates
- [ ] Secrets in environment variables (not in code)
- [ ] Database access restricted to localhost
- [ ] API keys encrypted at rest

---

## 13. API Documentation

**OpenAPI/Swagger:**
- FastAPI auto-generates interactive documentation
- Available at: `https://yourdomain.com/api/docs`
- Includes all endpoints, schemas, and examples

---

## 14. Appendix

### 14.1 Glossary

- **VPS:** Virtual Private Server
- **JWT:** JSON Web Token
- **ORM:** Object-Relational Mapping
- **CORS:** Cross-Origin Resource Sharing
- **SSL/TLS:** Secure Sockets Layer / Transport Layer Security
- **OHLCV:** Open, High, Low, Close, Volume (price data)

### 14.2 References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Nginx Documentation](https://nginx.org/en/docs/)

---

**Document Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Engineering Team | Initial architecture documentation |