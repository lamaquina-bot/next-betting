FROM python:3.11-slim

# Metadatos
LABEL maintainer="MOLINO"
LABEL description="Backend API para predicciones de fútbol con ML"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MODEL_PATH=/app/models/latest_model.joblib

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Copiar modelo ML
COPY models/ ./models/

# Copiar datos de features
COPY data/ ./data/

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
