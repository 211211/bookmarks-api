"""Consistent error envelope across error classes."""


def _assert_envelope(body):
    assert set(body.keys()) == {"error"}
    err = body["error"]
    assert "code" in err and isinstance(err["code"], str)
    assert "message" in err and isinstance(err["message"], str)


def test_not_found_envelope(client, alice):
    resp = client.get("/api/bookmarks/424242", headers=alice["headers"])
    assert resp.status_code == 404
    _assert_envelope(resp.json())
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_validation_envelope_has_details(client, alice):
    resp = client.post(
        "/api/bookmarks",
        json={"url": "https://x.com", "title": "x" * 300},  # title too long
        headers=alice["headers"],
    )
    assert resp.status_code == 422
    body = resp.json()
    _assert_envelope(body)
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "title"


def test_auth_envelope(client):
    resp = client.get("/api/bookmarks")
    assert resp.status_code == 401
    _assert_envelope(resp.json())


def test_unknown_route_envelope(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    _assert_envelope(resp.json())
