# MOLINO NEXT — Documento de Requisitos

**Versión:** 1.0  
**Fecha:** 2026-04-22  
**Estado:** BORRADOR — Pendiente aprobación de Gabriel

---

## 1. Decisión de Stack

### Decisión: **Python (FastAPI) + PostgreSQL + Coolify**

**Justificación:**

| Factor | Python/FastAPI | Node.js/Express |
|--------|---------------|-----------------|
| ML existente | ✅ 136-feature model, scripts, Dixon-Coles — todo en Python | ❌ Requeriría reescribir o wrappear |
| Ecosistema datos | ✅ pandas, scikit-learn, xgboost nativos | ❌ Limitado para ML |
| Equipo | ⚠️ Curva de aprendizaje mínima (ML ya está en Python) | ✅ Infraestructura existente |
| Performance | ✅ FastAPI comparable a Express | ✅ Nativo |
| Integración modelo | ✅ Carga directa `.pkl`/`.joblib` | ❌ Subproceso o microservicio |

**Racional:** El 80% del valor del proyecto es el modelo ML y la lógica cuantitativa. Todo está en Python. Reescribir en Node.js sería multiplicar el esfuerzo por 3 sin beneficio claro. FastAPI da performance equivalente con acceso directo al ecosistema ML.

### Base de datos: **PostgreSQL**

- Firebase (Firestore) no soporta queries analíticas complejas (JOINs, aggregations sobre 47K+ partidos)
- PostgreSQL + `pgvector` permite futuras extensiones ML
- Los CSVs históricos se importan limpiamente con `\copy`
- Coolify soporta PostgreSQL como servicio managed

### Hosting: **Coolify (existente)**

- Ya pagado y funcionando (`taller-de-ines.thefuckinggoat.cloud`)
- Domains configurados con Traefik
- Costo: $0 adicional vs $50+/mes en AWS
- Permite migrar a AWS en fase SaaS si se necesita

### Resumen de Stack MVP

```
Backend:   Python 3.11 + FastAPI
DB:        PostgreSQL 16
Cache:     Redis (opcional, fase 2)
ML:        scikit-learn / xgboost (modelo existente)
Hosting:   Coolify (VPS existente)
CI/CD:     GitHub Actions → Coolify webhook
Monitoreo: Uptime Kuma (self-hosted)
```

---

## 2. Requisitos Funcionales

### F1: Data Pipeline

**F1.1 — Ingesta de fixtures desde API-Football**

- **Descripción:** Obtener partidos programados de 6 ligas (Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie) vía API-Football.
- **Endpoint:** `GET /fixtures?league={id}&season={year}&next=30`
- **Frecuencia:** Cada 6 horas, con refresh forzado 1 hora antes del primer partido del día.
- **Criterio de aceptación:**
  - [ ] Endpoint expone `GET /api/v1/fixtures?date=YYYY-MM-DD` con fixtures del día
  - [ ] Cada fixture contiene: id, liga, equipos, fecha/hora UTC, estado, cuotas (si disponibles)
  - [ ] Respuesta en <2s para hasta 100 fixtures
  - [ ] Datos almacenados en tabla `fixtures` con upsert (idempotente)
  - [ ] Logging de cada sincronización con count de registros insertados/actualizados

**F1.2 — Ingesta de cuotas en tiempo real**

- **Descripción:** Obtener cuotas de mercado desde The Odds API para los fixtures pendientes.
- **Endpoint:** `GET /v4/sports/{sport}/odds/?regions=eu&markets=h2h,totals`
- **Frecuencia:** Cada 15 minutos para fixtures de las próximas 24h; cada 1 hora para fixtures >24h.
- **Criterio de aceptación:**
  - [ ] Almacenar cuotas de múltiples bookmakers en tabla `odds`
  - [ ] Registro de timestamp de cada cuota para tracking de movimiento de línea
  - [ ] Alerta si no se obtienen cuotas en 2 ciclos consecutivos
  - [ ] Máximo 500 calls/día (limite del plan free de The Odds API)

**F1.3 — Migración de datos históricos (184 CSVs → PostgreSQL)**

- **Descripción:** Script one-shot para importar los 184 archivos CSV al schema de base de datos.
- **Criterio de aceptación:**
  - [ ] Script `scripts/migrate_csvs.py` con progreso visual (tqdm)
  - [ ] Validación de esquema: tipos de datos, nulos, duplicados
  - [ ] Reporte post-migración: total registros, warnings, errores
  - [ ] Idempotente: puede ejecutarse múltiples veces sin duplicar datos
  - [ ] Target: >47,000 partidos + estadísticas asociadas importados correctamente

**F1.4 — Refresh programado (cron)**

- **Descripción:** Jobs programados para sincronización automática de datos.
- **Criterio de aceptación:**
  - [ ] Cron jobs configurados: fixtures cada 6h, odds cada 15min, cleanup diario
  - [ ] Health check endpoint `GET /api/v1/pipeline/status` muestra último run y próximo
  - [ ] Si un job falla, reintenta 3 veces con backoff exponencial
  - [ ] Notificación a Gabriel si 3 reintentos fallan consecutivamente

---

### F2: Predictive Engine

**F2.1 — Carga del modelo existente (136 features)**

- **Descripción:** Servir el modelo ML entrenado (47,412 matches, 6 ligas) como API.
- **Criterio de aceptación:**
  - [ ] Modelo cargado al inicio de la aplicación (warm start, <5s)
  - [ ] Endpoint `GET /api/v1/models/active` muestra modelo en uso, versión, fecha de entrenamiento, métricas
  - [ ] Endpoint `POST /api/v1/models/upload` permite subir nueva versión del modelo
  - [ ] Rollback automático si el nuevo modelo falla health check

**F2.2 — Predicción por fixture**

- **Descripción:** Para cada fixture upcoming, generar probabilidades H/D/A.
- **Criterio de aceptación:**
  - [ ] Endpoint `POST /api/v1/predictions` recibe lista de fixture_ids, devuelve probabilidades
  - [ ] Cada predicción incluye: `home_win_prob`, `draw_prob`, `away_win_prob`, `confidence_tier` (high/medium/low)
  - [ ] 50 predicciones en <30 segundos
  - [ ] Predicciones cacheadas por fixture_id (no recalcular si no hay datos nuevos)

**F2.3 — Versionado de modelos**

- **Descripción:** Soportar múltiples versiones del modelo con comparación.
- **Criterio de aceptación:**
  - [ ] Tabla `model_versions` con: versión, fecha, features, métricas (accuracy, log_loss, Brier score)
  - [ ] Endpoint `GET /api/v1/models/compare?v1=X&v2=Y` compara métricas lado a lado
  - [ ] Promote de modelo: `POST /api/v1/models/{version}/promote`
  - [ ] Máximo 5 versiones almacenadas simultáneamente (cleanup automático)

---

### F3: Value Bet Detection

**F3.1 — Cálculo de edge**

- **Descripción:** Comparar probabilidad del modelo vs cuotas de mercado para detectar valor.
- **Fórmula:** `edge = (model_prob × decimal_odds) - 1`
- **Criterio de aceptación:**
  - [ ] Endpoint `GET /api/v1/value-bets?date=YYYY-MM-DD&min_edge=0.05`
  - [ ] Cada value bet incluye: fixture, modelo prob, mejor cuota, edge %, bookmaker, confidence_tier
  - [ ] Edge calculado contra el promedio de cuotas de todos los bookmakers disponibles
  - [ ] Filtrable por: liga, edge mínimo, confidence tier
  - [ ] Ordenado por edge descendente por defecto

**F3.2 — Umbral de edge configurable**

- **Descripción:** Permitir ajustar el umbral mínimo de edge.
- **Criterio de aceptación:**
  - [ ] Configuración persistida: `min_edge` default = 5%
  - [ ] Se puede ajustar por liga (ej: ligas menores → edge mínimo 8%)
  - [ ] Cambios aplicados sin restart de la aplicación
  - [ ] Endpoint `GET/PUT /api/v1/config/edge-threshold`

**F3.3 — Picks diarios con niveles de confianza**

- **Descripción:** Generar lista consolidada de picks del día.
- **Criterio de aceptación:**
  - [ ] Endpoint `GET /api/v1/picks/today` devuelve picks del día
  - [ ] Cada pick tiene: fixture, selección (H/D/A), cuota, edge, stake recomendado, confidence (1-5 estrellas)
  - [ ] Máximo 10 picks/día (configurable) — no sobrecargar
  - [ ] Generado automáticamente a las 08:00 UTC o bajo demanda

---

### F4: Bankroll Management

**F4.1 — Cálculo de stake (Kelly Criterion)**

- **Descripción:** Calcular tamaño de apuesta óptimo usando Kelly Criterion fraccional.
- **Criterio de aceptación:**
  - [ ] Fórmula: `f* = (bp - q) / b` donde b=decimal_odds-1, p=model_prob, q=1-p
  - [ ] Kelly fraccional: default 25% del Kelly completo (mitigar varianza)
  - [ ] Fracción configurable: `kelly_fraction` en settings
  - [ ] Stake redondeado a múltiplos de $100
  - [ ] Stake máximo por apuesta: 5% del bankroll (hard cap)
  - [ ] Si Kelly sugiere >5%, cap a 5% con warning en logs

**F4.2 — Tracking de P&L**

- **Descripción:** Registrar resultados y calcular métricas de performance.
- **Criterio de aceptación:**
  - [ ] Tabla `bets` con: fixture_id, selección, cuota, stake, resultado, P&L, timestamp
  - [ ] Registro automático al resolverse un fixture (cruzando con resultados de API-Football)
  - [ ] Endpoint `GET /api/v1/bankroll/summary?period=daily|weekly|monthly`
  - [ ] Métricas calculadas: ROI, yield, hit rate, profit total, número de apuestas
  - [ ] Bankroll inicial: $100,000 USD (virtual)

**F4.3 — Alertas de drawdown**

- **Descripción:** Monitorear y alertar cuando el drawdown supera umbrales.
- **Criterio de aceptación:**
  - [ ] Drawdown calculado como: `(peak_bankroll - current_bankroll) / peak_bankroll`
  - [ ] Warning al 10% de drawdown (notificación informativa)
  - [ ] Alerta crítica al 20% de drawdown → pausa automática de nuevas apuestas
  - [ ] Endpoint `GET /api/v1/bankroll/drawdown` con historial
  - [ ] Resumen de pausa automática enviado por notificación

**F4.4 — Historial y gráficos de bankroll**

- **Descripción:** Visualizar evolución del bankroll en el dashboard.
- **Criterio de aceptación:**
  - [ ] Endpoint `GET /api/v1/bankroll/history?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - [ ] Datos suficientes para graficar: fecha, bankroll, pico, drawdown
  - [ ] Granularidad: diario por defecto, horario para última semana

---

### F5: Dashboard

**F5.1 — Vista de picks del día**

- **Descripción:** Página principal con los picks activos.
- **Criterio de aceptación:**
  - [ ] Muestra: partido, selección, cuota, edge %, stake recomendado, confianza (estrellas)
  - [ ] Código de color: verde (edge >8%), amarillo (5-8%), rojo (<5% o no califica)
  - [ ] Actualización automática cada 5 minutos (polling o SSE)
  - [ ] Filtros: por liga, por confianza, solo con edge > X%

**F5.2 — Performance histórica**

- **Descripción:** Métricas agregadas del rendimiento del modelo y las apuestas.
- **Criterio de aceptación:**
  - [ ] KPIs principales: ROI total, yield, hit rate, Sharpe ratio, número total de apuestas
  - [ ] Períodos: últimos 7 días, 30 días, 90 días, todo
  - [ ] Gráfico de ROI acumulado en el tiempo
  - [ ] Tabla de resultados recientes (últimas 50 apuestas)

**F5.3 — Evolución del bankroll**

- **Descripción:** Gráfico de línea mostrando el bankroll a lo largo del tiempo.
- **Criterio de aceptación:**
  - [ ] Línea de bankroll + línea de bankroll máximo (peak)
  - [ ] Área sombreada mostrando drawdown
  - [ ] Tooltip al hover: fecha, bankroll, drawdown actual
  - [ ] Períodos seleccionables

**F5.4 — Desglose por liga**

- **Descripción:** Performance segmentada por liga.
- **Criterio de aceptación:**
  - [ ] Tabla con: liga, apuestas, hit rate, ROI, yield, profit
  - [ ] Ordenable por cualquier columna
  - [ ] Identificar ligas más/menos rentables

**F5.5 — Métricas del modelo**

- **Descripción:** Accuracy y calibración del modelo predictivo.
- **Criterio de aceptación:**
  - [ ] Accuracy general y por liga
  - [ ] Brier score (calibración de probabilidades)
  - [ ] Matriz de confusión simplificada (H/D/A)
  - [ ] Comparación vs mercado (¿el modelo bate las cuotas del closing line?)

**Tecnología Dashboard:**  
Opciones evaluadas:
- **Streamlit** → Simple, Python-native, suficiente para MVP. ✅ Recomendado.
- **React + FastAPI** → Más flexible pero más trabajo. Fase 2 (SaaS).
- **Grafana** → Bueno para métricas, malo para UX custom.

**Decisión MVP:** Streamlit embebido en Coolify. Migrar a React en fase SaaS.

---

### F6: Alerting

**F6.1 — Notificaciones push para picks de alto edge**

- **Descripción:** Notificar cuando se detecta un pick con edge >10%.
- **Criterio de aceptación:**
  - [ ] Implementación vía Telegram bot (Gabriel ya usa Telegram)
  - [ ] Mensaje: "🔥 Value bet: [Equipo A vs Equipo B] — Selección: Local @ 2.10 — Edge: 12.3% — Confianza: ⭐⭐⭐⭐"
  - [ ] Máximo 5 notificaciones/día para no spamear
  - [ ] Configurable: umbral de edge, máximo por día, horario silencioso (23:00-08:00)

**F6.2 — Reporte diario**

- **Descripción:** Resumen diario de actividad enviado por Telegram.
- **Criterio de aceptación:**
  - [ ] Enviado a las 22:00 UTC automáticamente
  - [ ] Contenido: picks del día, resultados de partidos finalizados, P&L del día, bankroll actual, drawdown actual
  - [ ] Formato compacto, legible en móvil
  - [ ] Endpoint `GET /api/v1/reports/daily?date=YYYY-MM-DD` para consulta manual

**F6.3 — Alertas de drawdown**

- **Descripción:** Notificación inmediata al superar umbrales de drawdown.
- **Criterio de aceptación:**
  - [ ] ⚠️ Warning 10%: "Drawdown al 10%. Bankroll: $90,000. Revisar estrategia."
  - [ ] 🚫 Crítico 20%: "DRAWDOWN 20%. Nuevas apuestas PAUSADAS automáticamente. Revisar modelo."
  - [ ] Notificación inmediata vía Telegram

**F6.4 — Alertas de degradación del modelo**

- **Descripción:** Detectar si el modelo pierde rendimiento.
- **Criterio de aceptación:**
  - [ ] Comparar hit rate de últimos 100 picks vs hit rate histórico
  - [ ] Si hit rate reciente cae >10% por debajo del histórico → alerta
  - [ ] Si ROI últimos 100 picks es negativo → alerta
  - [ ] Alerta semanal con métricas del modelo vs benchmark

---

## 3. Requisitos No Funcionales

### NFR-1: Performance

| Métrica | Target | Medición |
|---------|--------|----------|
| Predicciones (50 fixtures) | <30s | Benchmark automatizado |
| API response (single endpoint) | <500ms | p95 con timer middleware |
| Dashboard load | <3s | Primera carga |
| Migración CSV (184 archivos) | <10min | Script one-shot |

### NFR-2: Disponibilidad

- 99.5% uptime durante horas de partido (viernes-domingo, 12:00-23:00 UTC)
- Health check endpoint: `GET /health` → `{ status: "ok", db: "connected", model: "loaded" }`
- Auto-restart en Coolify con health check
- Monitoreo con Uptime Kuma (ya disponible en infraestructura)

### NFR-3: Seguridad

- API keys encriptadas en base de datos (Fernet/AES)
- Variables sensibles como secrets en Coolify (no en código)
- Dashboard protegido con autenticación básica (usuario/contraseña)
- No exponer endpoints del modelo al público sin auth
- Rate limiting: 100 req/min por IP en endpoints públicos

### NFR-4: Escalabilidad

- Arquitectura modular: separar data pipeline, ML engine, API, dashboard como servicios independientes
- MVP: mono-repo con módulos (no microservicios aún)
- Base de datos: índices en `fixtures(date, league)`, `odds(fixture_id, timestamp)`, `bets(fixture_id)`
- Preparado para separar en microservicios en fase SaaS

### NFR-5: Costo

| Recurso | Costo estimado/mes |
|---------|--------------------|
| VPS Coolify (existente) | $0 (ya pagado) |
| API-Football (plan básico) | €9.99 (~$11) |
| The Odds API (plan free) | $0 |
| Dominio (existente) | $0 |
| **Total MVP** | **~$11/mes** ✅ |

---

## 4. Restricciones

1. **API-Football:** Plan pagado mínimo €9.99/mes (100 requests/día). Limita a ~3 sincronizaciones/día completas.
2. **The Odds API:** Plan free = 500 requests/mes. Se necesita plan $4.99/mes (5,000 requests) para odds cada 15min.
3. **Legal:** Herramienta de análisis únicamente. No integrar con casas de apuestas ni facilitar colocación directa de apuestas en MVP.
4. **Bankroll:** Inicial $100,000 virtual. Migrr a real solo después de 3 meses de validación con ROI positivo.
5. **Rate limits:** Respetar todos los límites de APIs proveedoras. Implementar backoff exponencial.

---

## 5. Decisiones Pendientes (Gabriel)

| # | Decisión | Opciones | Recomendación | Impacto si no se decide |
|---|----------|----------|---------------|------------------------|
| 1 | Stack | Python vs Node.js | **Python/FastAPI** | Bloquea inicio de desarrollo |
| 2 | Base de datos | PostgreSQL vs Firebase | **PostgreSQL** | Bloquea diseño de schema |
| 3 | Hosting | AWS vs Coolify | **Coolify** | Bloquea deployment |
| 4 | Scope MVP | Dashboard + automatización vs solo dashboard | **Dashboard + automatización** | Define tamaño del MVP |
| 5 | SaaS desde día 1 | SaaS vs self-operation | **Self-operation primero** | Define complejidad de auth/multi-tenancy |

---

## 6. Criterios de Aceptación Global (Definition of Done)

El MVP está completo cuando:

- [ ] Pipeline de datos ejecuta automáticamente fixtures + odds sin intervención manual por 7 días consecutivos
- [ ] Modelo genera predicciones para todos los fixtures upcoming de las 6 ligas
- [ ] Se detectan y presentan value bets con edge >5% diariamente
- [ ] Kelly Criterion calcula stakes correctamente (validado contra cálculos manuales)
- [ ] Dashboard muestra picks, performance, bankroll y métricas del modelo
- [ ] Telegram bot envía picks de alto edge y reporte diario sin fallar
- [ ] Alertas de drawdown funcionan (testeadas manualmente)
- [ ] Sistema completo corre en Coolify con < $15/mes de costo
- [ ] Documentación de API completa (OpenAPI spec generada por FastAPI)
- [ ] README con instrucciones de setup, configuración y operación

---

## 7. Arquitectura Propuesta (MVP)

```
┌─────────────────────────────────────────────┐
│                  Coolify VPS                │
│                                             │
│  ┌──────────┐    ┌──────────────────────┐   │
│  │ Streamlit │◄──│  FastAPI Backend     │   │
│  │ Dashboard │   │                      │   │
│  └──────────┘    │  /api/v1/fixtures    │   │
│                  │  /api/v1/predictions  │   │
│  ┌──────────┐    │  /api/v1/value-bets  │   │
│  │ Telegram  │◄──│  /api/v1/bankroll    │   │
│  │ Bot       │   │  /api/v1/picks       │   │
│  └──────────┘    │  /api/v1/models      │   │
│                  └──────────┬───────────┘   │
│                             │               │
│                  ┌──────────▼───────────┐   │
│                  │   ML Engine (Python)  │   │
│                  │   - Modelo 136 feats  │   │
│                  │   - Dixon-Coles       │   │
│                  │   - Kelly Criterion   │   │
│                  └──────────┬───────────┘   │
│                             │               │
│                  ┌──────────▼───────────┐   │
│                  │   PostgreSQL 16      │   │
│                  │   - fixtures         │   │
│                  │   - odds             │   │
│                  │   - predictions      │   │
│                  │   - bets             │   │
│                  │   - bankroll_history │   │
│                  └──────────────────────┘   │
│                                             │
│  Cron: fixtures/6h · odds/15min · cleanup/24h│
└─────────────────────────────────────────────┘
         │                    │
    API-Football        The Odds API
```

---

## 8. Plan de Fases

### Fase 1 — Fundación (Semana 1-2)
- Setup de proyecto Python (FastAPI, estructura, CI)
- Schema de PostgreSQL + migración de 184 CSVs
- Endpoints CRUD básicos (fixtures, odds)
- Deploy en Coolify

### Fase 2 — Motor Predictivo (Semana 3-4)
- Integración del modelo 136 features
- Pipeline de predicción automático
- Value bet detection + edge calculation
- Kelly Criterion + bankroll tracking

### Fase 3 — Dashboard + Alertas (Semana 5-6)
- Streamlit dashboard con todas las vistas (F5)
- Telegram bot para alertas (F6)
- Reporte diario automatizado
- Alertas de drawdown y degradación

### Fase 4 — Validación (Semana 7-8)
- Paper trading con bankroll virtual $100K
- Monitoreo de performance 2 semanas
- Ajustes de thresholds basados en datos reales
- Documentación final

---

## 9. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Modelo no mantiene +38% ROI en producción | Media | Alto | Paper trading 2 semanas antes de bankroll real |
| APIs cambian schema o tienen downtime | Baja | Medio | Retry con backoff + fallback a datos cacheados |
| Rate limits insuficientes para odds cada 15min | Media | Medio | Upgradear plan The Odds API ($4.99/mes) |
| Coolify VPS no tiene recursos suficientes | Baja | Alto | Monitorear RAM/CPU; migrar a VPS más grande ($10/mes) si needed |
| Legal: regulación cambia en Colombia | Baja | Crítico | MVP es herramienta de análisis, no integra con bookmakers |

---

*Documento generado por Requirements Agent de MOLINO.*  
*Pendiente revisión y aprobación de Gabriel.*  
*Siguiente paso: Gabriel aprueba stack y scope → se crea plan de Sprint 1.*
