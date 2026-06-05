"""Rate limiting (bonus): a tripped limit returns 429 in the consistent envelope.

Builds a tiny isolated app with a 1/minute limit so the test is deterministic and
independent of the main app's (high) test limits.
"""

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.rate_limit import rate_limit_exceeded_handler


def test_rate_limit_returns_429_envelope():
    limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    @limiter.limit("1/minute")
    def ping(request: Request, response: Response):
        return {"ok": True}

    client = TestClient(app)

    assert client.get("/ping").status_code == 200
    resp = client.get("/ping")
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["message"]
