import time
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.config import settings


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed rate limiter per API key.
    Limits requests per minute based on the X-API-Key header.
    """

    def __init__(self, app):
        super().__init__(app)
        self.redis: Optional[aioredis.Redis] = None
        self.rate_limit = settings.rate_limit_per_minute

    async def _get_redis(self) -> aioredis.Redis:
        if self.redis is None:
            self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self.redis

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health endpoints
        if request.url.path in ("/health", "/ready", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "anonymous")
        key = f"rate_limit:{api_key}:{int(time.time() // 60)}"

        try:
            r = await self._get_redis()
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, 60)

            # Set rate limit headers
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.rate_limit - current))

            if current > self.rate_limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            return response
        except HTTPException:
            raise
        except Exception:
            # If Redis is down, allow the request through
            return await call_next(request)
