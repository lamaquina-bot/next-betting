# MOLINO NEXT — Arquitectura del Sistema

**Versión:** 1.0  
**Fecha:** 2026-04-22  
**Estado:** BORRADOR

---

## 1. System Overview

```
                    ┌─────────────────────────────────────────┐
                    │           COOLIFY VPS 89.117.33.22      │
                    │                                          │
  ┌──────────┐      │  ┌──────────────┐   ┌───────────────┐   │
  │ Gabriel  │◄─────┼──│ Telegram Bot │   │   Streamlit   │   │
  │ (mobile) │      │  │  (alerts)    │   │   Dashboard   │   │
  └──────────┘      │  └──────┬───────┘   └───────┬───────┘   │
                    │         │                   │           │
                    │         └───────┬───────────┘           │
                    │                 │                        │
                    │         ┌───────▼───────┐               │
                    │         │  FastAPI API  │               │
                    │         │  :8000        │               │
                    │         └───┬───────┬───┘               │
                    │             │       │                    │
                    │    ┌────────▼┐  ┌───▼──────────┐        │
                    │    │ML Engine│  │Scheduler     │        │
                    │    │(xgboost)│  │(APScheduler) │        │
                    │    └────────┘  └───┬──────────┘        │
                    │                    │                     │
                    │            ┌───────▼────────┐           │
                    │            │ PostgreSQL 16   │           │
                    │            │ :5432           │           │
                    │            └────────────────┘           │
                    └──────────────────┬──────────────────────┘
                                       │
                          ┌────────────┼────────────┐
                          ▼                         ▼
                    API-Football              The Odds API
                   (€9.99/mes)              (free tier)
```

**Flujo principal:**
1. **Scheduler** ejecuta jobs programados (fixtures/6h, odds/15min)
2. **APIs externas** → datos crudos → **PostgreSQL**
3. **ML Engine** genera predicciones desde features + odds
4. **Value detector** compara modelo vs mercado → picks
5. **FastAPI** expone endpoints REST para dashboard y bot
6. **Telegram Bot** envía alertas de picks y drawdown
7. **Streamlit** muestra dashboard interactivo

---

## 2. Tech Stack

| Componente    | Tecnología             | Versión | Justificación                          |
|---------------|------------------------|---------|----------------------------------------|
| Backend       | Python + FastAPI       | 3.11    | Async, nativo ML, OpenAPI automático   |
| Base de datos | PostgreSQL             | 16      | JOINs, agregaciones, 47K+ registros    |
| ML            | xgboost / scikit-learn | —       | Modelo existente 136 features          |
| Dashboard     | Streamlit              | 1.37+   | Python-native, rápido para MVP         |
| Scheduler     | APScheduler            | 3.10+   | In-process, sin infra extra            |
| Bot           | python-telegram-bot    | 21+     | Gabriel ya usa Telegram                |
| Contenedores  | Docker + docker-compose| —       | Consistente con Coolify existente      |
| Proxy         | Traefik (existente)    | 3.6     | SSL automático, routing por dominio    |
| CI/CD         | GitHub Actions         | —       | Build → push → Coolify webhook         |
| Monitoreo     | Uptime Kuma            | —       | Ya disponible en VPS                   |

---

## 3. Data Model

### Tabla: `leagues`

| Campo       | Tipo         | Restricciones           |
|-------------|--------------|-------------------------|
| id          | SERIAL        | PRIMARY KEY             |
| api_id      | INTEGER       | UNIQUE NOT NULL         |
| name        | VARCHAR(100)  | NOT NULL                |
| country     | VARCHAR(50)   | NOT NULL                |
| season      | INTEGER       | NOT NULL                |

### Tabla: `fixtures`

| Campo          | Tipo           | Restricciones                    |
|----------------|----------------|----------------------------------|
| id             | SERIAL          | PRIMARY KEY                      |
| api_id         | INTEGER         | UNIQUE NOT NULL                  |
| league_id      | INTEGER         | REFERENCES leagues(id)           |
| home_team      | VARCHAR(100)    | NOT NULL                         |
| away_team      | VARCHAR(100)    | NOT NULL                         |
| kickoff_utc    | TIMESTAMPTZ     | NOT NULL                         |
| status         | VARCHAR(20)     | DEFAULT 'scheduled'              |
| home_goals     | SMALLINT        | NULL                             |
| away_goals     | SMALLINT        | NULL                             |
| created_at     | TIMESTAMPTZ     | DEFAULT NOW()                    |
| updated_at     | TIMESTAMPTZ     | DEFAULT NOW()                    |

**Índices:** `(kickoff_utc, league_id)`, `(status)`

### Tabla: `odds`

| Campo         | Tipo           | Restricciones                    |
|---------------|----------------|----------------------------------|
| id            | BIGSERIAL       | PRIMARY KEY                      |
| fixture_id    | INTEGER         | REFERENCES fixtures(id)          |
| bookmaker     | VARCHAR(50)     | NOT NULL                         |
| market        | VARCHAR(20)     | NOT NULL -- h2h, totals, ou      |
| home_win      | DECIMAL(6,3)    | NULL                             |
| draw          | DECIMAL(6,3)    | NULL                             |
| away_win      | DECIMAL(6,3)    | NULL                             |
| over_line     | DECIMAL(4,2)    | NULL                             |
| under_line    | DECIMAL(4,2)    | NULL                             |
| timestamp     | TIMESTAMPTZ     | NOT NULL                         |

**Índices:** `(fixture_id, timestamp)`, `(bookmaker, fixture_id)`

### Tabla: `predictions`

| Campo           | Tipo           | Restricciones                    |
|-----------------|----------------|----------------------------------|
| id              | SERIAL          | PRIMARY KEY                      |
| fixture_id      | INTEGER         | UNIQUE REFERENCES fixtures(id)   |
| model_version   | VARCHAR(20)     | NOT NULL                         |
| home_win_prob   | DECIMAL(5,4)    | NOT NULL                         |
| draw_prob       | DECIMAL(5,4)    | NOT NULL                         |
| away_win_prob   | DECIMAL(5,4)    | NOT NULL                         |
| confidence_tier | VARCHAR(10)     | NOT NULL -- high/medium/low      |
| features_hash   | VARCHAR(64)     | -- detectar cambios de features  |
| created_at      | TIMESTAMPTZ     | DEFAULT NOW()                    |

### Tabla: `value_bets`

| Campo          | Tipo           | Restricciones                        |
|----------------|----------------|--------------------------------------|
| id             | SERIAL          | PRIMARY KEY                          |
| fixture_id     | INTEGER         | REFERENCES fixtures(id)              |
| prediction_id  | INTEGER         | REFERENCES predictions(id)           |
| selection      | VARCHAR(10)     | NOT NULL -- home/draw/away           |
| model_prob     | DECIMAL(5,4)    | NOT NULL                             |
| best_odds      | DECIMAL(6,3)    | NOT NULL                             |
| bookmaker      | VARCHAR(50)     | NOT NULL                             |
| edge           | DECIMAL(5,4)    | NOT NULL                             |
| stake_pct      | DECIMAL(5,4)    | -- % del bankroll (Kelly)            |
| stake_amount   | DECIMAL(10,2)   | -- monto absoluto                    |
| confidence     | SMALLINT        | NOT NULL -- 1-5 estrellas           |
| result         | VARCHAR(10)     | NULL -- win/loss/pending             |
| settled_at     | TIMESTAMPTZ     | NULL                                 |
| created_at     | TIMESTAMPTZ     | DEFAULT NOW()                        |

**Índices:** `(edge DESC)`, `(created_at)`, `(result)`

### Tabla: `bankroll_history`

| Campo          | Tipo           | Restricciones                    |
|----------------|----------------|----------------------------------|
| id             | SERIAL          | PRIMARY KEY                      |
| date           | DATE            | NOT NULL                         |
| balance        | DECIMAL(12,2)   | NOT NULL                         |
| peak           | DECIMAL(12,2)   | NOT NULL                         |
| drawdown_pct   | DECIMAL(5,4)    | NOT NULL                         |
| daily_pnl      | DECIMAL(10,2)   | NOT NULL DEFAULT 0               |
| total_bets     | INTEGER         | DEFAULT 0                        |
| is_paused      | BOOLEAN         | DEFAULT FALSE                    |

**Índices:** `(date)`

### Tabla: `model_versions`

| Campo          | Tipo           | Restricciones                    |
|----------------|----------------|----------------------------------|
| id             | SERIAL          | PRIMARY KEY                      |
| version        | VARCHAR(20)     | UNIQUE NOT NULL                  |
| trained_at     | TIMESTAMPTZ     | NOT NULL                         |
| features_count | INTEGER         | NOT NULL                         |
| accuracy       | DECIMAL(5,4)    | NULL                             |
| log_loss       | DECIMAL(6,4)    | NULL                             |
| brier_score    | DECIMAL(6,4)    | NULL                             |
| is_active      | BOOLEAN         | DEFAULT FALSE                    |
| file_path      | VARCHAR(255)    | NOT NULL                         |

### Tabla: `config`

| Campo     | Tipo          | Restricciones               |
|-----------|---------------|-----------------------------|
| key       | VARCHAR(50)   | PRIMARY KEY                 |
| value     | JSONB         | NOT NULL                    |
| updated_at| TIMESTAMPTZ   | DEFAULT NOW()               |

**Config keys:** `min_edge`, `kelly_fraction`, `max_daily_picks`, `bankroll_initial`, `drawdown_warning`, `drawdown_critical`

### Tabla: `pipeline_logs`

| Campo       | Tipo          | Restricciones                |
|-------------|---------------|------------------------------|
| id          | SERIAL         | PRIMARY KEY                  |
| job_name    | VARCHAR(50)    | NOT NULL                     |
| status      | VARCHAR(10)    | NOT NULL -- success/failed   |
| records_ins | INTEGER        | DEFAULT 0                    |
| records_upd | INTEGER        | DEFAULT 0                    |
| error_msg   | TEXT           | NULL                         |
| started_at  | TIMESTAMPTZ    | NOT NULL                     |
| finished_at | TIMESTAMPTZ    | NULL                         |

---

## 4. API Endpoints

### Prefijo: `/api/v1`

#### Health & Config

| Método | Ruta                    | Descripción                          |
|--------|-------------------------|--------------------------------------|
| GET    | `/health`               | Status: API, DB, modelo              |
| GET    | `/config`               | Configuración actual                 |
| PUT    | `/config/{key}`         | Actualizar config (hot reload)       |

#### Fixtures & Odds

| Método | Ruta                            | Descripción                     |
|--------|---------------------------------|---------------------------------|
| GET    | `/fixtures?date=&league=`       | Fixtures con filtros            |
| GET    | `/fixtures/{id}`                | Detalle de fixture              |
| GET    | `/fixtures/{id}/odds`           | Odds históricas de un fixture   |
| POST   | `/fixtures/sync`                | Forzar sincronización manual    |

#### Predicciones & Modelo

| Método | Ruta                            | Descripción                     |
|--------|---------------------------------|---------------------------------|
| POST   | `/predictions`                  | Generar predicciones por IDs    |
| GET    | `/predictions/{fixture_id}`     | Predicción de un fixture        |
| GET    | `/models/active`                | Modelo activo + métricas        |
| GET    | `/models`                       | Listar versiones                |
| POST   | `/models/upload`                | Subir nueva versión (.joblib)   |
| POST   | `/models/{version}/promote`     | Activar versión                 |
| GET    | `/models/compare?v1=&v2=`       | Comparar versiones             |

#### Value Bets & Picks

| Método | Ruta                            | Descripción                     |
|--------|---------------------------------|---------------------------------|
| GET    | `/value-bets?date=&min_edge=`   | Value bets con filtros          |
| GET    | `/picks/today`                  | Picks consolidados del día      |

#### Bankroll

| Método | Ruta                            | Descripción                     |
|--------|---------------------------------|---------------------------------|
| GET    | `/bankroll/summary?period=`     | ROI, yield, hit rate, profit    |
| GET    | `/bankroll/history?from=&to=`   | Serie temporal bankroll         |
| GET    | `/bankroll/drawdown`            | Historial de drawdown           |

#### Pipeline

| Método | Ruta                            | Descripción                     |
|--------|---------------------------------|---------------------------------|
| GET    | `/pipeline/status`              | Último run, próximo, estado     |
| GET    | `/pipeline/logs?job=&limit=`    | Logs de ejecuciones             |

---

## 5. ML Pipeline

```
  ┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
  │ API-Football │────►│ Feature Builder  │────►│ Model v2.0   │
  │ The Odds API │     │ (136 features)   │     │ (xgboost)    │
  └─────────────┘     └──────────────────┘     └──────┬───────┘
                                                       │
                                              P(H), P(D), P(A)
                                                       │
                       ┌───────────────────────────────▼───────┐
                       │           Value Bet Detector          │
                       │  edge = (model_prob × decimal_odds)-1 │
                       │  filter: edge > min_edge (5%)         │
                       │  rank: edge DESC, confidence DESC     │
                       └───────────────────┬───────────────────┘
                                           │
                               ┌───────────▼────────────┐
                               │    Kelly Criterion     │
                               │ f* = (bp - q) / b      │
                               │ stake = 25% Kelly      │
                               │ cap: 5% bankroll       │
                               └───────────┬────────────┘
                                           │
                                   value_bets + stakes
                                           │
                               ┌───────────▼────────────┐
                               │   Telegram + Dashboard │
                               └────────────────────────┘
```

**Feature Engineering (136 features):**
- Estadísticas de equipos: xG, goles, tiros, posesión (últimos 5/10/20 partidos)
- Head-to-head: histórico directo entre equipos
- Forma reciente: racha, puntos últimos N partidos
- Contexto: localía, descanso, hora del partido
- Cuotas de mercado: implied probabilities, movimientos de línea
- Dixon-Coles: ajuste por dependencia de goles

**Pipeline steps (cada predicción):**
1. Cargar fixture + stats de equipos desde PostgreSQL
2. Calcular/actualizar 136 features
3. Hashear features → skip si no cambiaron (cache)
4. Inferir con modelo activo → probabilidades H/D/A
5. Cruza con mejores cuotas disponibles → edge calculation
6. Si edge > threshold → value bet + Kelly stake
7. Persistir todo en PostgreSQL

---

## 6. Scheduled Jobs

APScheduler (in-process en FastAPI):

| Job                    | Cron              | Descripción                              |
|------------------------|-------------------|------------------------------------------|
| `sync_fixtures`        | `0 */6 * * *`     | Sincronizar fixtures de 6 ligas          |
| `sync_odds_upcoming`   | `*/15 * * * *`    | Odds para fixtures próximas 24h          |
| `sync_odds_distant`    | `0 * * * *`       | Odds para fixtures > 24h                 |
| `generate_predictions` | `0 7,16 * * *`    | Predecir fixtures sin predicción         |
| `generate_picks`       | `0 8 * * *`       | Picks diarios (08:00 UTC)                |
| `settle_bets`          | `*/30 * * * *`    | Resolver apuestas con resultados         |
| `update_bankroll`      | `0 22 * * *`      | Recalcular bankroll + P&L diario         |
| `daily_report`         | `0 22 * * *`      | Enviar reporte Telegram                  |
| `cleanup_old_odds`     | `0 3 * * *`       | Purgar odds > 30 días                    |

**Resiliencia:** retry 3x con backoff exponencial (5s, 30s, 120s). Si falla 3x → alerta Telegram a Gabriel.

---

## 7. Deployment

### Docker Compose (`docker-compose.yml`)

```yaml
version: "3.8"

services:
  api:
    build: .
    container_name: molino-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://molino:${DB_PASS}@postgres:5432/molino
      - API_FOOTBALL_KEY=${API_FOOTBALL_KEY}
      - THE_ODDS_API_KEY=${THE_ODDS_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
    depends_on:
      postgres:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.molino-api.rule=Host(`molino-api.thefuckinggoat.cloud`)"
      - "traefik.http.routers.molino-api.tls=true"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.streamlit
    container_name: molino-dashboard
    ports:
      - "8501:8501"
    environment:
      - API_URL=http://api:8000
    depends_on:
      - api
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.molino-dash.rule=Host(`molino.thefuckinggoat.cloud`)"
      - "traefik.http.routers.molino-dash.tls=true"
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    container_name: molino-postgres
    volumes:
      - molino-pgdata:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=molino
      - POSTGRES_USER=molino
      - POSTGRES_PASSWORD=${DB_PASS}
    ports:
      - "5433:5432"          # No exponer 5432 (ya usado por Coolify)
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U molino"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  molino-pgdata:
```

### Flujo de Deploy

```
git push → GitHub Actions → docker build → push to registry → Coolify webhook → pull + restart
```

### Recursos estimados por contenedor

| Servicio   | RAM   | CPU  |
|------------|-------|------|
| api        | ~256MB| ~10% |
| dashboard  | ~128MB| ~5%  |
| postgres   | ~128MB| ~5%  |
| **Total**  | ~512MB| ~20% |

VPS tiene 4GB RAM → sobra espacio.

---

## 8. File Structure

```
molino-next/
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.streamlit
├── .env.example
├── .github/
│   └── workflows/
│       └── deploy.yml
├── alembic/
│   ├── alembic.ini
│   └── versions/              # Migraciones DB
├── app/
│   ├── main.py                # FastAPI app + scheduler startup
│   ├── config.py              # Settings (pydantic-settings)
│   ├── database.py            # SQLAlchemy engine + session
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── fixture.py
│   │   ├── odds.py
│   │   ├── prediction.py
│   │   ├── value_bet.py
│   │   ├── bankroll.py
│   │   └── config.py
│   ├── schemas/               # Pydantic request/response schemas
│   │   └── ...
│   ├── api/
│   │   ├── __init__.py
│   │   ├── fixtures.py
│   │   ├── predictions.py
│   │   ├── value_bets.py
│   │   ├── bankroll.py
│   │   ├── models.py
│   │   └── pipeline.py
│   ├── services/
│   │   ├── data_ingestion.py  # API-Football + The Odds API clients
│   │   ├── feature_builder.py # 136 features computation
│   │   ├── predictor.py       # Model loading + inference
│   │   ├── value_detector.py  # Edge calculation + filtering
│   │   ├── kelly.py           # Kelly Criterion stake sizing
│   │   ├── bankroll.py        # P&L tracking + drawdown
│   │   └── notifier.py        # Telegram notifications
│   └── jobs/
│       ├── __init__.py
│       └── scheduler.py       # APScheduler job definitions
├── dashboard/
│   ├── app.py                 # Streamlit main
│   ├── pages/
│   │   ├── 1_Picks.py
│   │   ├── 2_Performance.py
│   │   ├── 3_Bankroll.py
│   │   ├── 4_Leagues.py
│   │   └── 5_Model.py
│   └── components/
│       ├── charts.py
│       └── utils.py
├── ml/
│   ├── models/                # .joblib model files
│   ├── dixon_coles.py         # Implementación existente
│   └── kelly.py               # Implementación existente
├── scripts/
│   ├── migrate_csvs.py        # Importar 184 CSVs → PostgreSQL
│   ├── seed_config.py         # Valores default en tabla config
│   └── backtest.py            # Backtesting histórico
├── data/
│   └── historical/            # 184 CSVs (git-ignored)
├── tests/
│   ├── test_api.py
│   ├── test_predictor.py
│   └── test_kelly.py
├── requirements.txt
└── README.md
```

---

## 9. Cost Estimate

| Recurso                     | Costo/mes | Notas                              |
|-----------------------------|-----------|------------------------------------|
| VPS Coolify (existente)     | $0        | Ya pagado, 4GB RAM, sobra         |
| API-Football (plan Basic)   | $11       | €9.99, 100 req/día                |
| The Odds API (free tier)    | $0        | 500 req/mes, suficiente MVP       |
| Dominio (existente)         | $0        | thefuckinggoat.cloud              |
| **Total MVP**               | **$11/mes** | ✅ <$15 target                    |

### Upgrade path (si se necesita)

| Recurso                       | Costo/mes | Cuándo activar             |
|-------------------------------|-----------|----------------------------|
| The Odds API (5K requests)    | $4.99     | Si odds/15min no alcanzan  |
| VPS upgrade (8GB RAM)         | ~$10      | Si se añade Redis + más servicios |
| **Total con upgrades**        | ~$26/mes  | Todavía <$50               |

---

*Arquitectura diseñada por Architect Agent de MOLINO.*  
*Basada en REQUIREMENTS.md v1.0 y decisiones confirmadas por Gabriel.*
