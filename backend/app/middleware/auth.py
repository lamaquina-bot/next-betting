"""Middleware de autenticación por API Key (Fix 1 - CRÍTICO)"""
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Rutas que no requieren autenticación
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Verifica X-API-Key header contra la variable de entorno API_KEY."""

    async def dispatch(self, request: Request, call_next):
        # Skip rutas públicas
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        api_key = os.getenv("API_KEY", "")
        # Si no hay API_KEY configurada, permitir todo (modo desarrollo)
        if not api_key:
            return await call_next(request)

        # Verificar header
        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "API Key inválida o no proporcionada"},
            )

        return await call_next(request)
