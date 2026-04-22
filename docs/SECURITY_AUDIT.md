# NEXT — Auditoría de Seguridad

**Fecha:** 2026-04-22  
**Auditor:** Security Agent de MOLINO  
**Alcance:** Backend API, infraestructura Docker, integraciones externas  
**Estado:** PRE-PRODUCCIÓN (MVP)

---

## Resumen Ejecutivo

| Crítico | Alto | Medio | Bajo |
|---------|------|-------|------|
| 3       | 3    | 3     | 1    |

**Veredicto general: ❌ NO LISTO PARA PRODUCCIÓN**

El sistema tiene 3 hallazgos críticos que deben resolverse antes de cualquier despliegue público: API sin autenticación, credenciales débiles en `.env.example`, y ausencia total de rate limiting. Para uso personal/single-user está aceptable con mitigaciones básicas.

---

## 1. API Keys Exposure

### Estado: ⚠️ WARN

**Hallazgos:**
- `config.py` define defaults vacíos (`api_football_key: str = ""`) — ✅ Correcto, no hay keys hardcoded
- `.env.example` usa placeholders (`tu_api_key_aqui`) — ✅ Correcto
- `data_ingestion.py` pasa `apiKey` como query param a The Odds API — aparece en logs del servidor
- `data_ingestion.py` pasa API key como header (`x-apisports-key`) — ✅ Mejor práctica
- No hay `.gitignore` en el proyecto — **Riesgo de commit accidental de `.env`**

**Recomendaciones:**
1. Crear `.gitignore` inmediatamente: excluir `.env`, `*.joblib`, `data/historical/`
2. Mover `apiKey` de query params a header en The Odds API (si el API lo soporta)
3. Usar Docker secrets o variables de Coolify en lugar de `.env` file

---

## 2. SQL Injection

### Estado: ✅ PASS

**Hallazgos:**
- Todas las consultas usan **SQLAlchemy ORM** con `select()`, `.where()`, `.filter()` — queries parametrizadas
- **Cero SQL crudo** (`text()`, `execute(raw_sql)`) encontrado en todo el código
- Los filtros de rutas usan parámetros tipados (int, float, str) con Pydantic validation
- `regex` en Query params (`^(home|draw|away)$`, `^(pending|won|lost|void)$`) restringe valores

**Recomendaciones:**
- Mantener la disciplina de ORM. Si se necesita SQL crudo futuro, obligar `text()` con bind parameters

---

## 3. Authentication

### Estado: ❌ FAIL — CRÍTICO

**Hallazgos:**
- **Cero autenticación** en toda la API — todos los endpoints son públicamente accesibles
- `docker-compose.yml` define `API_KEY: ${API_KEY:-changeme}` pero **nunca se valida en ningún endpoint**
- `POST /bankroll/bet-result` permite modificar datos financieros sin auth
- El endpoint de health expone versión del sistema
- Para SaaS: necesario JWT/API key middleware obligatorio

**Recomendaciones:**
1. **Inmediato (MVP):** Implementar middleware de API key estática:
   ```python
   @app.middleware("http")
   async def verify_api_key(request, call_next):
       if request.url.path == "/health":
           return await call_next(request)
       key = request.headers.get("X-API-Key")
       if key != settings.api_key:
           raise HTTPException(401)
       return await call_next(request)
   ```
2. **SaaS futuro:** JWT con roles (admin/viewer), OAuth2 opcional
3. Proteger `POST /bankroll/bet-result` con role admin

---

## 4. Rate Limiting

### Estado: ❌ FAIL — CRÍTICO

**Hallazgos:**
- **Sin rate limiting** en ningún endpoint
- No hay dependencia de `slowapi` o similar en `requirements.txt`
- Los endpoints de predicciones y value bets podrían ser abusados para escalar llamadas a APIs externas vía `sync`
- `POST /bankroll/bet-result` sin protección contra spam

**Recomendaciones:**
1. Agregar `slowapi` a requirements.txt
2. Configurar límites por endpoint:
   - GET (lectura): 60/min por IP
   - POST (escritura): 10/min por IP
   - `/fixtures/sync`: 5/hora (dispara llamadas externas)
3. En SaaS: rate limiting por usuario/API key

---

## 5. Input Validation

### Estado: ✅ PASS (con notas)

**Hallazgos:**
- Schemas Pydantic correctamente definidos para requests y responses
- Validaciones apropiadas: `Field(..., gt=0)` para odds, `ge=0.0, le=1.0` para edge
- `Query()` con `ge/le` limita rangos de parámetros
- Regex constraints en status y outcome: `^(home|draw|away)$`

**Gaps menores:**
- `BetResultRequest.stake` no tiene máximo — un stake absurdamente alto podría enviarse
- `status` en value_bets no tiene constraint de longitud máxima
- No hay validación de `fixture_id` como entero positivo en algunos schemas

**Recomendaciones:**
1. Agregar `stake: float = Field(..., gt=0, le=100000)` (max razonable)
2. Agregar `max_length` a campos String en schemas
3. Considerar `str = Field(..., pattern=...)` para todos los campos enum-like

---

## 6. CORS

### Estado: ❌ FAIL — ALTO

**Hallazgos:**
- Configuración wildcard: `allow_origins=["*"]`
- Con `allow_credentials=True` — **combinación peligrosa**
- Cualquier sitio web puede hacer requests a la API con cookies/credenciales

**Recomendaciones:**
1. Restringir origins a dominios conocidos:
   ```python
   allow_origins=[
       "https://next.thefuckinggoat.cloud",
       "https://molino.thefuckinggoat.cloud",
   ]
   ```
2. Para desarrollo: usar lista desde env var
3. Si `allow_origins=["*"]`, entonces `allow_credentials` debe ser `False`

---

## 7. Database Security

### Estado: ⚠️ WARN — ALTO

**Hallazgos:**
- `.env.example` muestra credenciales débiles: `molino:molino123` y `next:cambiar_esta_password_segura_123`
- Puerto 5433 expuesto al host — accesible desde VPS
- Connection string en `config.py` tiene default: `postgresql+asyncpg://next:next@localhost:5433/next_betting` (usuario=password=db name)
- `echo=settings.DEBUG` en engine — en debug=True, **todas las queries se loguean** incluyendo datos
- No hay SSL en conexión PostgreSQL interna

**Recomendaciones:**
1. Generar passwords fuertes aleatorios para producción
2. **Remover** `ports: "5433:5432"` de docker-compose en producción (usar solo red interna Docker)
3. Cambiar default de `debug` a `False`
4. Agregar `sslmode=require` al connection string si PostgreSQL lo soporta en la red interna
5. Considerar `pgcrypto` para datos financieros sensibles

---

## 8. Telegram Bot Security

### Estado: ⚠️ WARN — MEDIO

**Hallazgos:**
- Token y chat_id se leen de env vars — ✅ Correcto
- `alerts.py` imprime warning si no configurado, no crashea
- **Riesgo:** Si el bot token se filtra, cualquiera puede enviar mensajes en nombre del bot
- Chat ID hardcodeado = un solo destinatario (Gabriel) — correcto para MVP
- No hay verificación de que los mensajes lleguen solo al chat autorizado

**Recomendaciones:**
1. En SaaS: permitir MÚLTIPLES chat_ids por usuario
2. Implementar comando `/start` que vincule chat_id con usuario
3. Mensajes de Telegram NO deben contener API keys ni datos sensibles (actualmente solo contienen picks — aceptable)
4. Rotar bot token si se sospecha filtración

---

## 9. Model Protection

### Estado: ⚠️ WARN — MEDIO

**Hallazgos:**
- Modelo se carga con `joblib.load()` — **pickle deserialization = ejecución de código arbitrario**
- Path por defecto: `models/latest_model.joblib` (relativo, predecible)
- Si un atacante sube un modelo malicioso vía filesystem o endpoint futuro `/models/upload`, ejecuta código arbitrario
- No hay verificación de integridad (hash, firma) del modelo

**Recomendaciones:**
1. **Crítico:** Si se implementa `/models/upload`, validar firma/hash SHA256 del archivo
2. Usar `safetensors` o formato seguro en lugar de joblib/pickle (futuro)
3. Directorio `models/` debe tener permisos de solo lectura para el proceso API
4. Logear carga de modelos con hash para auditoría

---

## 10. Financial Data

### Estado: ⚠️ WARN — ALTO

**Hallazgos:**
- Datos financieros (bankroll, P&L, stakes, ROI) **expuestos sin autenticación**
- `GET /bankroll/history` muestra balances históricos completos
- `GET /dashboard/summary` muestra balance actual, ROI, profit
- `POST /bankroll/bet-result` permite modificar datos financieros — sin auth, sin validación de ownership
- No hay cifrado en reposo para datos financieros
- No hay auditoría/log de quién modifica qué

**Recomendaciones:**
1. **Autenticación obligatoria** en todos los endpoints financieros (vincula con finding #3)
2. Audit log: registrar cada `POST /bankroll/bet-result` con IP, timestamp, usuario
3. Validación de consistencia: no permitir stakes > balance actual
4. En SaaS: cifrado por usuario, aislamiento de datos entre tenants
5. Considerar que `GET /bankroll/*` devuelva datos anonimizados o con confirmación de identidad

---

## Issues Bloqueantes (para producción)

| # | Severidad | Issue | Esfuerzo |
|---|-----------|-------|----------|
| 1 | **CRÍTICO** | API sin autenticación | 2h |
| 2 | **CRÍTICO** | Sin rate limiting | 1h |
| 3 | **CRÍTICO** | CORS wildcard con credentials | 15min |
| 4 | **ALTO** | Puerto DB expuesto al host | 5min |
| 5 | **ALTO** | Credenciales débiles por defecto | 15min |
| 6 | **ALTO** | Sin `.gitignore` — riesgo de leak | 10min |

---

## Issues No Bloqueantes (mejoras post-MVP)

| # | Severidad | Issue |
|---|-----------|-------|
| 7 | MEDIO | Validación de integridad del modelo ML |
| 8 | MEDIO | Telegram bot token rotation plan |
| 9 | MEDIO | API key en query params (The Odds API) |
| 10 | BAJO | Debug mode por defecto en config |

---

## Roadmap de Seguridad Sugerido

### Pre-deploy (2-3h total)
1. ✅ Crear `.gitignore`
2. ✅ Agregar API key middleware
3. ✅ Agregar `slowapi` rate limiting
4. ✅ Restringir CORS
5. ✅ Quitar puerto DB del host
6. ✅ Generar passwords fuertes

### Post-MVP
7. Audit logging en endpoints financieros
8. JWT con roles para SaaS
9. Verificación de integridad del modelo
10. Cifrado en reposo para datos financieros

---

*Auditoría realizada por Security Agent de MOLINO.*  
*Basada en revisión de código estático. No se realizó pentesting dinámico.*
