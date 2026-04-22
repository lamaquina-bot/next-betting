# Despliegue en Coolify — NEXT Predictor

Guía paso a paso para desplegar NEXT en Coolify con Traefik.

---

## Requisitos previos

- Coolify v4.x funcionando con Traefik configurado
- Acceso al panel: `https://taller-de-ines.thefuckinggoat.cloud`
- API Token generado (Settings → API tokens)
- Dominios DNS apuntando al servidor:
  - `api.next.thefuckinggoat.cloud`
  - `next.thefuckinggoat.cloud`

---

## Paso 1 — Crear proyecto

1. Ir a **Projects** → **Add New Project**
2. Nombre: `next-predictor`
3. Descripción: `Predictor de resultados futbolísticos con ML`

---

## Paso 2 — Crear aplicación API (next-api)

1. Dentro del proyecto `next-predictor`, click **Add New Resource** → **Docker Compose (Empty)**
2. Nombre: `next-stack`
3. Pegar el contenido de `docker-compose.yml`

**Alternativa: crear servicios individuales:**

### Opción B — Servicio por servicio

#### 2a. Base de datos (next-db)

1. **Add New Resource** → **Service** → **PostgreSQL**
2. Configurar:
   - Nombre: `next-db`
   - Puerto externo: `5433`
   - Database: `next`
   - Username: `next`
   - Password: *(generar una segura)*
3. Click **Deploy**

#### 2b. API (next-api)

1. **Add New Resource** → **Application** → **Public Repository**
   - O **Docker Compose** si se usa el stack completo
2. Nombre: `next-api`
3. Source: repositorio con el Dockerfile
4. Configurar:
   - Dockerfile location: `api/Dockerfile`
   - Port: `8000`

**Variables de entorno (Configuration → Environment):**
```
DATABASE_URL=postgresql://next:TU_PASSWORD@next-db:5432/next
API_KEY=tu_api_key_secreta
MODEL_PATH=/app/models/model.pkl
LOG_LEVEL=INFO
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

**Dominio (Configuration → Domains):**
```
https://api.next.thefuckinggoat.cloud
```

**Health check:**
- Path: `/health`
- Interval: 15s

5. Click **Deploy**

#### 2c. Dashboard (next-dashboard)

1. **Add New Resource** → **Application**
2. Nombre: `next-dashboard`
3. Port: `8501`

**Variables de entorno:**
```
NEXT_API_URL=http://next-api:8000
NEXT_API_EXTERNAL_URL=https://api.next.thefuckinggoat.cloud
```

**Dominio:**
```
https://next.thefuckinggoat.cloud
```

4. Click **Deploy**

---

## Paso 3 — Verificar red Traefik

Asegurarse de que todos los servicios estén en la red `coolify`:

```bash
docker network inspect coolify | grep -A2 "next-"
```

Si un servicio no está en la red:
```bash
docker network connect coolify next-api
docker network connect coolify next-dashboard
docker network connect coolify next-db
```

---

## Paso 4 — Migrar datos

Ejecutar el script de migración para cargar los 184 CSVs:

```bash
# Desde el servidor, con los CSVs en /path/to/data/
docker exec -it next-api python /app/scripts/migrate_data.py
```

O si prefieres desde fuera:
```bash
# Instalar dependencias
pip install pandas sqlalchemy psycopg2-binary

# Ejecutar
python migrate_data.py
```

Verificar:
```bash
docker exec -it next-db psql -U next -d next -c "SELECT COUNT(*) FROM matches;"
```

---

## Paso 5 — Verificar despliegue

### Health check manual:
```bash
# API
curl https://api.next.thefuckinggoat.cloud/health

# Dashboard
curl https://next.thefuckinggoat.cloud/_stcore/health

# Script automatizado
bash health-check.sh
```

### Verificar en navegador:
- Dashboard: `https://next.thefuckinggoat.cloud`
- API docs: `https://api.next.thefuckinggoat.cloud/docs`

---

## Paso 6 — Configurar SSL/TLS

Coolify con Traefik maneja SSL automáticamente con Let's Encrypt.

Verificar que los certificados se generaron:
1. Ir a **Servers** → tu servidor → **Proxy** → **Certificates**
2. Deberían aparecer `api.next.thefuckinggoat.cloud` y `next.thefuckinggoat.cloud`

Si no se generan automáticamente:
```bash
# Verificar logs de Traefik
docker logs coolify-proxy --tail 50
```

---

## Monitoreo continuo

### Logs:
```bash
docker logs -f next-api --tail 100
docker logs -f next-dashboard --tail 100
docker logs -f next-db --tail 100
```

### Recursos:
En el panel Coolify → `next-stack` → ver métricas de CPU/RAM en tiempo real.

### Backups de BD:
```bash
docker exec next-db pg_dump -U next next > backup_$(date +%Y%m%d).sql
```

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| 502 Bad Gateway | Verificar que next-api está healthy |
| Dashboard no conecta | Verificar `NEXT_API_URL` apunte a `http://next-api:8000` |
| SSL no funciona | Verificar DNS apunte al servidor, revisar logs Traefik |
| BD no accesible | Verificar que next-db está healthy y en la misma red |
| CSVs no cargan | Verificar columna `Date` formato YYYY-MM-DD o DD/MM/YYYY |

---

## Rollback

Si algo falla después de un deploy:

1. Coolify → `next-api` → **Deployments** → click en el deploy anterior → **Redeploy**
2. O via CLI:
```bash
docker tag next-api:previous next-api:latest
docker compose -f docker-compose.yml up -d next-api
```
