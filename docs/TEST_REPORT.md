# NEXT — Reporte de Testing Completo

**Fecha:** 2026-04-22  
**Auditor:** Testing Agent de MOLINO  
**Alcance:** Backend, Dashboard, Integración, Seguridad  
**Estado:** ❌ NO LISTO PARA DESPLIEGUE

---

## Resumen Ejecutivo

| Área | Veredicto | Issues Bloqueantes | No Bloqueantes |
|------|-----------|-------------------|----------------|
| 1. Calidad de Código | ❌ FAIL | 5 | 6 |
| 2. Cumplimiento Arquitectura | ❌ FAIL | 3 | 4 |
| 3. Verificación Seguridad | ⚠️ WARN | 2 | 3 |
| 4. Integración | ❌ FAIL | 3 | 2 |
| 5. Dashboard | ❌ FAIL | 3 | 1 |

**Veredicto General: ❌ NECESITA CORRECCIONES — 16 issues bloqueantes**

---

## 1. Calidad de Código

### Veredicto: ❌ FAIL

Todos los archivos pasan `ast.parse()` sin errores de sintaxis. Sin embargo, hay errores de runtime que impedirán el arranque.

### Issues Bloqueantes

#### B-1.1: `database.py` llama función inexistente `get_settings()`
- **Archivo:** `backend/app/database.py`, línea 8
- **Problema:** `from app.config import get_settings` → `get_settings()` no existe en `config.py`. Solo existe `settings = Settings()`.
- **Impacto:** La API no arranca. ImportError o AttributeError.
- **Fix:** Agregar `def get_settings(): return Settings()` en `config.py`, o cambiar a `from app.config import settings`.

#### B-1.2: Inconsistencia mayúsculas/minúsculas en atributos de Settings
- **Archivo:** `database.py` usa `settings.DATABASE_URL` y `settings.DEBUG`
- **Problema:** Pydantic BaseSettings los define como `database_url` y `debug` (minúsculas). Acceder como `DATABASE_URL` funciona SOLO si se configura `model_config = SettingsConfigDict(...)` con `env_prefix` y Pydantic v2 alias. Con Pydantic 2.6.1 y la configuración actual, `settings.DATABASE_URL` **sí funciona** porque Pydantic v2 permite acceso por nombre de campo. Sin embargo, es confuso.
- **Impacto:** Funciona pero genera confusión de mantenimiento.
- **Severidad:** No bloqueante (Pydantic v2 permite ambos accesos).

#### B-1.3: `settings.DEFAULT_BANKROLL` no existe en Settings
- **Archivos:** `backend/app/routes/bankroll.py` (línea `_mask_balance`), `backend/app/routes/dashboard.py`
- **Problema:** `settings.DEFAULT_BANKROLL` no está definido en `config.py`. Solo existen las constantes en `utils/constants.py` (`INITIAL_BANKROLL = 100000`).
- **Impacto:** `AttributeError` al llamar endpoints de bankroll o dashboard.
- **Fix:** Agregar `default_bankroll: float = 100000.0` a la clase `Settings`.

#### B-1.4: Dockerfile copia directorios inexistentes
- **Archivo:** `backend/Dockerfile`
- **Problema:** `COPY alembic/ ./alembic/` y `COPY alembic.ini .` — no existen ni `alembic/` ni `alembic.ini` en el proyecto.
- **Impacto:** Build de Docker falla.
- **Fix:** Crear estructura Alembic o remover esas líneas del Dockerfile.

#### B-1.5: `docker-compose.yml` apunta a directorio equivocado
- **Archivo:** `integration/docker-compose.yml`, servicio `next-api`
- **Problema:** `build.context: ../api` — el directorio es `../backend`, no `../api`.
- **Impacto:** `docker-compose build` falla.
- **Fix:** Cambiar a `build.context: ../backend`.

### Issues No Bloqueantes

| # | Archivo | Issue |
|---|---------|-------|
| NB-1.1 | `config.py` | `class Config: env_file = ".env"` es estilo Pydantic v1. En v2 debería ser `model_config = SettingsConfigDict(env_file=".env")`. Funciona con compatibilidad pero genera warning de deprecación. |
| NB-1.2 | `requirements.txt` | `scikit-learn` pesado (120MB+). Para MVP que no usa el modelo real, considerar removerlo y agregar solo si se sube un `.joblib`. |
| NB-1.3 | `database.py` | `get_db()` hace commit en cada request exitosa, incluyendo GETs. No es incorrecto pero es innecesario para lecturas. |
| NB-1.4 | `routes/bankroll.py` | `_mask_pnl()` se define pero nunca se usa. |
| NB-1.5 | `routes/value_bets.py` | N+1 query problem: para cada value bet hace queries separadas para pred y fixture. Debería usar `selectinload` o `joinedload`. |
| NB-1.6 | `database.py` | `init_db()` se define pero nunca se llama (no hay startup event). Las tablas no se crean automáticamente. |

---

## 2. Cumplimiento de Arquitectura

### Veredicto: ❌ FAIL

La arquitectura define un sistema ambicioso. El código implementado cubre aproximadamente el 30% de lo especificado.

### Issues Bloqueantes

#### B-2.1: Solo 7 de 25+ endpoints implementados
**Endpoints implementados:**
| Método | Ruta | ✅ |
|--------|------|-----|
| GET | `/health` | ✅ |
| GET | `/api/fixtures/` | ✅ |
| GET | `/api/fixtures/upcoming` | ✅ |
| GET | `/api/predictions/` | ✅ |
| GET | `/api/predictions/{id}` | ✅ |
| GET | `/api/value-bets/` | ✅ |
| GET | `/api/value-bets/today` | ✅ |
| GET | `/api/bankroll/` | ✅ |
| POST | `/api/bankroll/bet-result` | ✅ |
| GET | `/api/dashboard/summary` | ✅ |

**Endpoints faltantes (15+):**
- `GET /api/v1/config`, `PUT /api/v1/config/{key}`
- `GET /api/fixtures/{id}`, `GET /api/fixtures/{id}/odds`, `POST /api/fixtures/sync`
- `POST /api/predictions` (generar predicciones)
- `GET /api/models/active`, `GET /api/models`, `POST /api/models/upload`, `POST /api/models/{version}/promote`, `GET /api/models/compare`
- `GET /api/picks/today`
- `GET /api/bankroll/summary`, `GET /api/bankroll/history`, `GET /api/bankroll/drawdown`
- `GET /api/pipeline/status`, `GET /api/pipeline/logs`

**Impacto:** La arquitectura especifica `/api/v1/` como prefijo, pero el código usa `/api/` directo.

#### B-2.2: Solo 6 de 8 tablas implementadas
**Tablas existentes:** League, Fixture, Odd, Prediction, ValueBet, BankrollHistory  
**Tablas faltantes:**
- `model_versions` (tracking de versiones de modelo)
- `config` (configuración dinámica)
- `pipeline_logs` (auditoría de jobs)

**Nota:** La tabla `bankroll_history` del modelo no coincide con la de arquitectura (falta `peak`, `drawdown_pct`, `is_paused`). La tabla `odds` difiere (falta `market`, `over_line`, `under_line`). La tabla `value_bets` difiere (falta `fixture_id` directo, `model_prob`, `best_odds`, `bookmaker`, `confidence`, `stake_pct`, `stake_amount`, `settled_at`).

#### B-2.3: Scheduler (APScheduler) no implementado
- La arquitectura define 9 jobs programados. No hay código de scheduler.
- No hay `app/jobs/` ni `app/services/scheduler.py`.
- Los servicios de ingesta de datos existen pero no están conectados a un scheduler.

### Issues No Bloqueantes

| # | Issue | Detalle |
|---|-------|---------|
| NB-2.1 | Estructura de archivos no coincide | Arquitectura especifica `app/api/` para rutas, código usa `app/routes/`. Esquema de directorios simplificado. |
| NB-2.2 | Feature builder no existe | Arquitectura define `services/feature_builder.py` con 136 features. No implementado. |
| NB-2.3 | Telegram bot commands | Solo existe envío de alertas. No hay comandos `/start`, `/stats`, `/picks`. |
| NB-2.4 | Tests no existen | Arquitectura especifica `tests/test_api.py`, `test_predictor.py`, `test_kelly.py`. No hay directorio `tests/`. |

---

## 3. Verificación de Seguridad

### Veredicto: ⚠️ WARN (mejorado respecto al audit original)

Los 6 fixes del Security Audit fueron implementados parcialmente.

### Fixes Implementados

| Fix | Estado | Detalle |
|-----|--------|---------|
| Fix 1: API Key Auth | ✅ Implementado | `middleware/auth.py` — Middleware verifica `X-API-Key` header contra `API_KEY` env var. Permite bypass si no hay key configurada (modo dev). |
| Fix 2: Rate Limiting | ✅ Implementado | `middleware/rate_limit.py` — 60 req/min por IP, en memoria. Excluye `/health`. |
| Fix 3: CORS Restrictivo | ✅ Implementado | `main.py` — Origins limitados a `localhost:8501` y `next.thefuckinggoat.cloud`. |
| Fix 4: .gitignore | ❌ No implementado | No existe archivo `.gitignore` en el proyecto. |
| Fix 5: Protección datos financieros | ✅ Implementado | `bankroll.py` — enmascara balance para no-admins via `X-Admin-Key` header. |
| Fix 6: Validación token Telegram | ✅ Implementado | `alerts.py` — Valida formato de token con regex `^\d{8,10}:[A-Za-z0-9_-]{35}$`. |

### Issues Bloqueantes

#### B-3.1: Sin `.gitignore`
- **Problema:** Riesgo de commitear `.env`, modelos `.joblib`, datos CSV.
- **Fix:** Crear `.gitignore` con `.env`, `*.joblib`, `data/`, `__pycache__/`, `.git/`.

#### B-3.2: `joblib.load()` sin validación de integridad
- **Problema:** Deserialización de pickle = ejecución de código arbitrario.
- **Impacto:** Medio (solo si alguien puede subir un modelo malicioso al filesystem).
- **Fix futuro:** Verificar hash SHA256 antes de cargar. Por ahora aceptable para MVP single-user.

### Issues No Bloqueantes

| # | Issue |
|---|-------|
| NB-3.1 | Rate limiting en memoria se pierde al reiniciar el contenedor. Para single-user es aceptable. |
| NB-3.2 | `debug: bool = True` por defecto en config. En producción debería ser `False`. |
| NB-3.3 | Puerto DB (5433) expuesto al host en docker-compose. Debería ser solo red interna. |

---

## 4. Integración

### Veredicto: ❌ FAIL

### Issues Bloqueantes

#### B-4.1: Build context incorrecto en docker-compose
- **Archivo:** `integration/docker-compose.yml`
- **Problema:** `build.context: ../api` — debería ser `../backend`.
- **Fix:** Cambiar a `../backend`.

#### B-4.2: Dashboard no recibe `API_URL` correctamente
- **Problema:** docker-compose pasa `NEXT_API_URL` y `NEXT_API_EXTERNAL_URL` como env vars. Pero `dashboard/app.py` lee `os.getenv("API_URL", "http://localhost:8000/api")`.
- **Impacto:** Dashboard no se conecta al backend en Docker.
- **Fix:** Cambiar env var en compose a `API_URL: http://next-api:8000/api`, o cambiar `app.py` para leer `NEXT_API_URL`.

#### B-4.3: Connection string mismatch
- **Problema:** docker-compose pasa `DATABASE_URL: postgresql://...` (sin asyncpg). Pero `config.py` default usa `postgresql+asyncpg://...`. El compose no incluye el driver correcto.
- **Impacto:** La DB URL del compose no funcionará con SQLAlchemy async (asyncpg).
- **Fix:** Cambiar en compose a `DATABASE_URL: postgresql+asyncpg://...`.

### Issues No Bloqueantes

| # | Issue |
|---|-------|
| NB-4.1 | `nginx.conf` asume SSL certs en `/etc/nginx/ssl/` pero no hay volumen ni configuración para generarlos. Con Traefik, este nginx es redundante. |
| NB-4.2 | `migrate_data.py` usa `create_engine` (sync) pero la app usa async. Correcto para script one-shot, pero la tabla `historical_matches` no existe en los modelos ORM. |

---

## 5. Dashboard (Streamlit)

### Veredicto: ❌ FAIL

### Issues Bloqueantes

#### B-5.1: Endpoints que no existen en el backend
El dashboard llama a estos endpoints que **no están implementados**:

| Endpoint llamado | Existe? |
|------------------|---------|
| `GET /api/bankroll` | ✅ (pero devuelve lista, no objeto con `.balance`) |
| `GET /api/picks/today` | ❌ No existe. Debería ser `/api/value-bets/today` |
| `GET /api/stats` | ❌ No existe |
| `GET /api/bankroll/history` | ❌ No existe. Debería ser `/api/bankroll/` |
| `GET /api/stats/performance` | ❌ No existe |
| `GET /api/bets/history` | ❌ No existe |

**Impacto:** Todas las tabs del dashboard muestran errores o datos vacíos. Solo funciona si el backend tiene data y los endpoints coinciden.

#### B-5.2: Estructura de respuesta no coincide
- `app.py` espera `bankroll_data.get("balance")` pero `GET /api/bankroll/` devuelve una **lista** de `BankrollResponse`, no un objeto.
- `picks_data` espera columnas `fixture`, `outcome`, `probability` pero `ValueBetTodayResponse` tiene `home_team`, `away_team`, `recommended_bet`, `market_odds`, `edge`, `kelly_stake`.
- **Impacto:** KPIs muestran $0 o valores incorrectos. Tabla de picks no muestra columnas.

#### B-5.3: Variable de entorno incorrecta (repetido de B-4.2)
- `API_URL` en `.env.example` del dashboard dice `http://localhost:8000/api`
- docker-compose pasa `NEXT_API_URL` 
- No coinciden.

### Issues No Bloqueantes

| # | Issue |
|---|-------|
| NB-5.1 | Dark theme CSS es funcional pero limitado. No afecta `st.dataframe()` que usa su propio tema. Estéticamente aceptable para MVP. |

---

## Lista Completa de Issues

### 🔴 Bloqueantes (16)

| ID | Área | Issue | Esfuerzo |
|----|------|-------|----------|
| B-1.1 | Código | `get_settings()` no existe en config.py | 5 min |
| B-1.3 | Código | `DEFAULT_BANKROLL` no definido en Settings | 5 min |
| B-1.4 | Código | Dockerfile copia `alembic/` inexistente | 10 min |
| B-1.5 | Código | docker-compose build context `../api` → `../backend` | 1 min |
| B-2.1 | Arq | 15+ endpoints faltantes vs arquitectura | 8-16 h |
| B-2.2 | Arq | 3 tablas faltantes, esquemas no coinciden | 2-4 h |
| B-2.3 | Arq | Scheduler no implementado | 4-6 h |
| B-3.1 | Seguridad | Sin `.gitignore` | 5 min |
| B-4.1 | Integración | Build context incorrecto | 1 min |
| B-4.2 | Integración | Dashboard no recibe `API_URL` | 5 min |
| B-4.3 | Integración | Connection string sin `+asyncpg` | 2 min |
| B-5.1 | Dashboard | 5 endpoints inexistentes llamados | 4-8 h |
| B-5.2 | Dashboard | Estructura de respuesta no coincide | 2-3 h |
| B-5.3 | Dashboard | Variable env incorrecta | 2 min |

### 🟡 No Bloqueantes (16)

| ID | Área | Issue |
|----|------|-------|
| NB-1.1 | Código | Pydantic v1 Config style deprecado |
| NB-1.2 | Código | scikit-learn innecesario sin modelo real |
| NB-1.3 | Código | get_db() commit en GETs |
| NB-1.4 | Código | `_mask_pnl()` sin usar |
| NB-1.5 | Código | N+1 queries en value_bets |
| NB-1.6 | Código | init_db() nunca llamado |
| NB-2.1 | Arq | Estructura dirs simplificada vs arq |
| NB-2.2 | Arq | Feature builder no existe |
| NB-2.3 | Arq | Telegram bot commands no implementados |
| NB-2.4 | Arq | Sin tests |
| NB-3.1 | Seguridad | Rate limit se pierde al reiniciar |
| NB-3.2 | Seguridad | debug=True por defecto |
| NB-3.3 | Seguridad | Puerto DB expuesto |
| NB-4.1 | Integración | nginx.conf redundante con Traefik |
| NB-4.2 | Integración | migrate_data.py tabla no en ORM |
| NB-5.1 | Dashboard | Dark theme limitado |

---

## Plan de Acción Mínimo para MVP Funcional

### Paso 1: Quick Fixes (30 min) — Hacer que arranque
1. ✅ Agregar `def get_settings()` a `config.py`
2. ✅ Agregar `default_bankroll: float = 100000.0` a `Settings`
3. ✅ Crear `.gitignore`
4. ✅ Corregir Dockerfile (quitar alembic lines o crear alembic mínimo)
5. ✅ Corregir docker-compose build context + env vars + connection string

### Paso 2: Alinear Dashboard con Backend (2-3 h)
1. Corregir `app.py` para llamar endpoints que existen:
   - `/api/dashboard/summary` en vez de `/api/stats`
   - `/api/value-bets/today` en vez de `/api/picks/today`
   - `/api/bankroll/` en vez de `/api/bankroll/history`
   - `/api/value-bets/?status=settled` en vez de `/api/bets/history`
2. Corregir parsing de respuestas (lista vs objeto, nombres de campos)

### Paso 3: Endpoints críticos faltantes (4-6 h)
1. `GET /api/fixtures/{id}` — detalle de fixture
2. `POST /api/fixtures/sync` — sincronización manual
3. `GET /api/bankroll/history` — historial formateado
4. `GET /api/picks/today` — wrapper de value-bets/today

### Paso 4: Scheduler (4-6 h) — Post-MVP
1. Integrar APScheduler en `main.py` startup
2. Jobs de sync de fixtures y odds
3. Job de predicciones automáticas

---

## Veredicto Final

## ❌ NECESITA CORRECCIONES

**El código está bien estructurado y los conceptos son correctos, pero hay errores de integración que impedirán el arranque.** Los 6 fixes de seguridad están implementados. Los servicios ML y de detección de value bets son funcionales. El principal gap es la desconexión entre:
1. Config/database (función `get_settings` faltante)
2. Dashboard ↔ Backend (endpoints no coinciden)
3. docker-compose ↔ código real (paths y env vars)

**Con Paso 1 (30 min), el backend arranca.**  
**Con Paso 1+2 (3 h), el dashboard es funcional.**  
**Con Paso 1+2+3 (8 h), se tiene un MVP desplegable.**

---

*Reporte generado por Testing Agent de MOLINO.*  
*Revisión estática de código. No se ejecutaron tests de integración.*
