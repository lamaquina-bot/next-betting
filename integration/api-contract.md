# Contrato API — NEXT Predictor

Base URL: `https://api.next.thefuckinggoat.cloud`

Autenticación: Header `X-API-Key: <API_KEY>`

---

## Health

### `GET /health`

Verifica que la API está corriendo.

**Response `200`:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "db": "connected",
  "model_loaded": true
}
```

---

## Partidos

### `GET /api/v1/matches`

Lista partidos históricos con filtros opcionales.

**Query params:**
| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `league` | string | all | Liga (ej: "E0" = Premier League) |
| `season` | string | all | Temporada (ej: "2324") |
| `team` | string | all | Nombre del equipo (home o away) |
| `date_from` | string | null | Fecha inicio (YYYY-MM-DD) |
| `date_to` | string | null | Fecha fin (YYYY-MM-DD) |
| `limit` | int | 100 | Máximo resultados |
| `offset` | int | 0 | Paginación |

**Response `200`:**
```json
{
  "total": 18400,
  "limit": 100,
  "offset": 0,
  "matches": [
    {
      "id": 1,
      "date": "2023-08-11",
      "league": "E0",
      "season": "2324",
      "home_team": "Arsenal",
      "away_team": "Nottm Forest",
      "fthg": 2,
      "ftag": 1,
      "ftr": "H",
      "b365h": 1.53,
      "b365d": 4.33,
      "b365a": 6.50
    }
  ]
}
```

### `GET /api/v1/matches/{id}`

Detalle de un partido específico.

**Response `200`:**
```json
{
  "id": 1,
  "date": "2023-08-11",
  "league": "E0",
  "season": "2324",
  "home_team": "Arsenal",
  "away_team": "Nottm Forest",
  "fthg": 2,
  "ftag": 1,
  "ftr": "H",
  "b365h": 1.53,
  "b365d": 4.33,
  "b365a": 6.50,
  "hthg": 1,
  "htag": 0,
  "htr": "H",
  "referee": "M Oliver",
  "hs": 17,
  "as": 6,
  "hst": 6,
  "ast": 2,
  "hf": 11,
  "af": 9,
  "hc": 7,
  "ac": 3,
  "hy": 1,
  "ay": 2,
  "hr": 0,
  "ar": 0
}
```

**Response `404`:**
```json
{"detail": "Partido no encontrado"}
```

---

## Predicciones

### `POST /api/v1/predict`

Genera predicción para un partido.

**Request:**
```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "league": "E0",
  "date": "2024-03-15"
}
```

**Response `200`:**
```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "league": "E0",
  "date": "2024-03-15",
  "prediction": {
    "result": "H",
    "confidence": 0.62,
    "probabilities": {
      "home_win": 0.62,
      "draw": 0.23,
      "away_win": 0.15
    },
    "predicted_score": {
      "home": 2,
      "away": 0
    }
  },
  "odds_analysis": {
    "implied_home": 0.55,
    "implied_draw": 0.27,
    "implied_away": 0.18,
    "value_bet": "away_win",
    "edge": 0.03
  },
  "historical_stats": {
    "h2h_matches": 12,
    "home_wins": 7,
    "draws": 3,
    "away_wins": 2,
    "avg_home_goals": 1.8,
    "avg_away_goals": 0.7
  },
  "generated_at": "2024-03-14T18:30:00Z"
}
```

**Response `400`:**
```json
{"detail": "Equipo no encontrado en la base de datos: Unknown FC"}
```

---

## Estadísticas

### `GET /api/v1/stats/leagues`

Lista ligas disponibles con conteo de partidos.

**Response `200`:**
```json
{
  "leagues": [
    {"code": "E0", "name": "Premier League", "country": "England", "matches": 3800},
    {"code": "SP1", "name": "La Liga", "country": "Spain", "matches": 3200}
  ]
}
```

### `GET /api/v1/stats/teams/{team_name}`

Estadísticas históricas de un equipo.

**Query params:**
| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `league` | string | all | Filtrar por liga |
| `last_n` | int | 20 | Últimos N partidos |

**Response `200`:**
```json
{
  "team": "Arsenal",
  "total_matches": 456,
  "wins": 268,
  "draws": 98,
  "losses": 90,
  "goals_for": 782,
  "goals_against": 389,
  "avg_goals_for": 1.71,
  "avg_goals_against": 0.85,
  "form": ["W", "W", "D", "W", "L"],
  "home_record": {"w": 82, "d": 28, "l": 18},
  "away_record": {"w": 45, "d": 32, "l": 51}
}
```

---

## Modelos

### `GET /api/v1/model/info`

Información del modelo ML cargado.

**Response `200`:**
```json
{
  "model_type": "XGBoost",
  "version": "1.0.0",
  "trained_at": "2024-03-01T00:00:00Z",
  "features": ["home_form", "away_form", "h2h_ratio", "odds_implied", "home_advantage"],
  "accuracy": 0.54,
  "f1_score": 0.52,
  "total_training_samples": 45000
}
```

### `POST /api/v1/model/retrain`

Re-entrena el modelo con datos actualizados (async).

**Response `202`:**
```json
{
  "job_id": "retrain-20240314-183000",
  "status": "queued",
  "estimated_minutes": 5
}
```

### `GET /api/v1/model/retrain/{job_id}`

Estado de re-entrenamiento.

**Response `200`:**
```json
{
  "job_id": "retrain-20240314-183000",
  "status": "completed",
  "started_at": "2024-03-14T18:30:01Z",
  "completed_at": "2024-03-14T18:34:22Z",
  "new_accuracy": 0.55,
  "samples_used": 46500
}
```

---

## Errores generales

| Código | Significado |
|--------|-------------|
| `400` | Parámetros inválidos |
| `401` | API Key faltante o inválida |
| `404` | Recurso no encontrado |
| `422` | JSON malformado |
| `429` | Rate limit excedido |
| `500` | Error interno del servidor |

Formato error:
```json
{"detail": "Descripción del error"}
```
