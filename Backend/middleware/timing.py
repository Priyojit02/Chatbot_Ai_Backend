from __future__ import annotations

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("timing")


class TimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, slow_ms: int = 1200):
        super().__init__(app)
        self.slow_ms = slow_ms

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
        if elapsed_ms > self.slow_ms:
            logger.warning(f"Slow request {request.method} {request.url.path} took {elapsed_ms:.0f}ms")
        else:
            logger.info(f"{request.method} {request.url.path} {response.status_code} {elapsed_ms:.0f}ms")
        return response
