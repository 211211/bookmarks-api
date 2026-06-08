"""HTTP hardening: security headers, request IDs, body-size limit."""


def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in r.headers


def test_request_id_echoed_and_generated(client):
    # Generated when absent.
    r = client.get("/health")
    assert r.headers.get("x-request-id")
    # Echoed when supplied.
    rid = "test-correlation-id-123"
    r2 = client.get("/health", headers={"X-Request-ID": rid})
    assert r2.headers["x-request-id"] == rid


def test_readiness_probe_ok(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_oversized_body_rejected(client, alice):
    big = "x" * 2_000_000  # 2 MB > 1 MiB default limit
    r = client.post(
        "/api/bookmarks",
        json={"url": "https://e.com", "title": "t", "description": big},
        headers=alice["headers"],
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
