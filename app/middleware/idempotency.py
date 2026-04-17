"""
Idempotency middleware.

Ensures that state-changing requests (POST/PUT/DELETE) with an
Idempotency-Key header are processed only once. Subsequent retries
with the same key return the cached response.

Keys are stored in Redis with a configurable TTL (default: 24 hours).
"""

import hashlib
import json
import logging

import redis.asyncio as aioredis
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.config import settings

logger = logging.getLogger(__name__)

IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENCY_TTL_SECONDS = 86400  # 24 hours
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed idempotency middleware.

    For POST/PUT/DELETE requests that include an Idempotency-Key header:
    1. Check Redis for a cached response under that key.
    2. If found, return the cached response immediately (no handler invoked).
    3. If not found, process the request normally and cache the response.

    GET/HEAD/OPTIONS are always passed through.
    If Redis is unavailable, the request is processed normally (fail-open).
    """

    def __init__(self, app):
        super().__init__(app)
        self.redis = None

    async def _get_redis(self) -> aioredis.Redis:
        if self.redis is None:
            self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self.redis

    def _make_redis_key(self, idempotency_key: str, api_key: str) -> str:
        """Namespace the idempotency key per caller to avoid collisions."""
        caller_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return f"idempotency:{caller_hash}:{idempotency_key}"

    async def dispatch(self, request: Request, call_next):
        # Only apply to state-changing methods
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Only apply if the caller provides an Idempotency-Key header
        idempotency_key = request.headers.get(IDEMPOTENCY_HEADER)
        if not idempotency_key:
            return await call_next(request)

        # Skip for paths that don't need idempotency (health, docs)
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "anonymous")
        redis_key = self._make_redis_key(idempotency_key, api_key)

        try:
            r = await self._get_redis()

            # Check for cached response
            cached = await r.get(redis_key)
            if cached:
                data = json.loads(cached)
                logger.debug("Idempotency cache hit for key=%s", idempotency_key)
                return JSONResponse(
                    content=data["body"],
                    status_code=data["status_code"],
                    headers={"X-Idempotency-Replayed": "true"},
                )

            # Mark key as "in-progress" to handle concurrent duplicates.
            # NX ensures only the first request wins.
            acquired = await r.set(
                redis_key,
                json.dumps({"status": "processing"}),
                nx=True,
                ex=IDEMPOTENCY_TTL_SECONDS,
            )
            if not acquired:
                # Another request is processing this key right now
                return JSONResponse(
                    content={"detail": "A request with this Idempotency-Key is already being processed. Please retry later."},
                    status_code=409,
                )
        except Exception:
            # If Redis is down, process normally (fail-open)
            logger.exception("Idempotency middleware Redis error, passing through")
            return await call_next(request)

        # Process request once. Never retry call_next on application errors.
        try:
            response = await call_next(request)
        except Exception:
            # Release processing marker so a retry can proceed.
            try:
                await r.delete(redis_key)
            except Exception:
                logger.exception("Idempotency middleware failed to release processing lock")
            raise

        # Read the response body so we can cache it
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk if isinstance(chunk, bytes) else chunk.encode()

        # Try to parse as JSON for caching
        try:
            body_json = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            body_json = body_bytes.decode("utf-8", errors="replace")

        # Cache the response (best-effort)
        try:
            cache_data = {
                "status_code": response.status_code,
                "body": body_json,
            }
            await r.set(redis_key, json.dumps(cache_data), ex=IDEMPOTENCY_TTL_SECONDS)
        except Exception:
            logger.exception("Idempotency middleware failed to cache response")

        # Return a new response with the same body
        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
