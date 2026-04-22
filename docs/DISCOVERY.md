# DISCOVERY — MOLINO NEXT

**Plataforma de inversión cuantitativa en apuestas deportivas**
**Fecha:** 2026-04-22

---

## Estado Actual

- **Modelo:** 136 features, XGBoost/LightGBM, Dixon-Coles + Kelly Criterion
- **Datos:** 47K partidos, 6 ligas
- **Paper trading:** +38% ROI
- **APIs:** API-Football, The Odds API, Sportmonks configuradas

---

## 1. Mercado

- Mercado global de apuestas deportivas: **$70B+ USD** (2025)
- Colombia: **~$2B USD**, crecimiento **20% anual**
- Regulación vigente desde 2016 (Coljuegos)
- Players dominantes: **Bet365, Rushbet, Wplay, Codere**
- Tendencia: migración a móvil, apuestas en vivo, micro-apuestas
- LATAM es la región de mayor crecimiento del sector

## 2. Competencia

| Segmento | Ejemplos | Calidad |
|----------|----------|---------|
| Tipsters emocionales | Twitter, Telegram, YouTube | Baja — sin edge estadístico |
| Casas sharp | Pinnacle | Odds reflejan "smart money" |
| Syndicates profesionales | Cerrados, exclusivos | Alta — inaccesibles |
| Herramientas cuantitativas | Betegy, Accuscore | Media, caras, enfocadas en Europa |

**Gap identificado:** No existen herramientas accesibles en español para apostadores cuantitativos individuales en LATAM.

## 3. Factibilidad Técnica

| Componente | Solución | Costo |
|------------|----------|-------|
| Datos de fixtures | API-Football | $9.99/mes (paid tier necesario) |
| Odds en vivo | The Odds API | Free tier disponible |
| Datos históricos | Sportmonks | Plans desde €19/mes |
| ML Pipeline | XGBoost/LightGBM | Ya probado, +38% paper |
| Automatización | APIs de casas de apuestas | Riesgo: limitación de cuenta |

**Stack probado:** Python, pandas, scikit-learn, XGBoost. Pipeline funcional.

## 4. Regulación Colombia

- **Coljuegos** exige licencia para operar como casa de apuestas (costo: $500M+ COP)
- **ANALIZAR datos ≠ APOSTAR** — una plataforma de análisis NO requiere licencia de operador
- Ganancias de apuestas tributan como **renta ordinaria** (hasta 39%)
- Posicionamiento legal: "herramienta de análisis e inversión", no casa de apuestas
- Recomendación: consultar abogado tributario antes de operar con bankroll propio

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Overfitting del modelo | Alto | Walk-forward validation, out-of-sample testing |
| Limitación de cuentas | Alto | Múltiples casas,staking conservador |
| Regímenes cambiantes (lesiones, transfers) | Medio | Features dinámicos, reentrenamiento semanal |
| Drawdown | Medio | Max estimado: 20-30% bankroll, Kelly fraccional |
| Cambio regulatorio | Bajo | Monitoreo Coljuegos, modelo SaaS como plan B |

## 6. Modelo de Ingresos

| Modelo | Ingreso estimado | Escalabilidad |
|--------|-----------------|---------------|
| **Self-operation** | ROI 10-20% mensual (conservador) | Limitada por bankroll y casas |
| **SaaS** | $50-200/mes × suscriptor | TAM ~10K usuarios LATAM |
| **Consulting** | $5K-20K por proyecto | Alta, baja frecuencia |

**Prioridad:** Self-operation primero → validar con capital real → SaaS como segundo paso.

## 7. GO/NO-GO

### ✅ GO Condicional

**A favor:**
- Modelo validado: +38% ROI en paper trading
- 47K partidos, 136 features, pipeline funcional
- Gap de mercado claro en LATAM
- Costo de datos bajo ($10-30/mes)

**Condiciones para ejecutar:**
1. Upgrade API-Football a plan pago para datos en tiempo real
2. Validar con bankroll real ($500K-$1M COP) durante 1 mes
3. Implementar walk-forward validation antes de operar

**Riesgo principal:** Limitación de cuentas por casas de apuestas. Mitigación: diversificar entre 3+ casas.

---

*Próximo paso: MVP con capital real + dashboard de monitoreo.*
