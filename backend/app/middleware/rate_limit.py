"""Middleware de rate limiting en memoria (Fix 2 - CRÍTICO)"""
import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Configuración: 60 peticiones por minuto por IP
MAX_REQUESTS = 60
WINDOW_SECONDS = 60

# Almacén en memoria: IP → lista de timestamps
_request_log: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limita peticiones por IP: 60 req/min."""

    async def dispatch(self, request: Request, call_next):
        # Rutas de health no cuentan para el límite
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Limpiar timestamps fuera de la ventana
        timestamps = _request_log[client_ip]
        _request_log[client_ip] = [ts for ts in timestamps if now - ts < WINDOW_SECONDS]

        # Verificar límite
        if len(_request_log[client_ip]) >= MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas peticiones. Intenta de nuevo en un minuto."},
            )

        # Registrar petición
        _request_log[client_ip].append(now)
        return await call_next(request)
