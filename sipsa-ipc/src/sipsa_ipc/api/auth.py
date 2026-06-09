"""Autenticación por API Key y rate limiting para la API SIPSA IPC.

Configuración:
  - SIPSA_API_KEY : variable de entorno con la clave secreta.
    Por defecto "dev-key-sipsa" (solo para desarrollo local).
  - Rate limit   : 60 peticiones / minuto por IP (configurable via
    SIPSA_RATE_LIMIT, ej.: "120/minute").
"""
from __future__ import annotations

import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

_API_KEY_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=_API_KEY_NAME, auto_error=False)

_RATE_LIMIT = os.environ.get("SIPSA_RATE_LIMIT", "60/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[_RATE_LIMIT])


def _get_configured_key() -> str:
    return os.environ.get("SIPSA_API_KEY", "dev-key-sipsa")


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Dependencia FastAPI: valida el header X-API-Key."""
    if not api_key or api_key != _get_configured_key():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key inválida o ausente. Incluye el header X-API-Key.",
        )
    return api_key
