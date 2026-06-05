"""Bookmark CRUD, validation, and ownership scoping."""


def _create(client, headers, **overrides):
    payload = {
        "url": "https://example.com/article",
        "title": "Great Article",
        "description": "An insightful read.",
        "tags": ["Python", "tutorial", "python"],  # mixed case + duplicate on purpose
    }
    payload.update(overrides)
    return client.post("/api/bookmarks", json=payload, headers=headers)


def test_create_bookmark(client, alice):
    resp = _create(client, alice["headers"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Great Article"
    assert body["url"].startswith("https://example.com/article")
    # Tags normalized to lowercase + de-duplicated.
    assert body["tags"] == ["python", "tutorial"]
    assert "id" in body and "created_at" in body and "updated_at" in body


def test_create_bookmark_invalid_url(client, alice):
    resp = _create(client, alice["headers"], url="not-a-valid-url")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_bookmark_missing_title(client, alice):
    resp = client.post(
        "/api/bookmarks",
        json={"url": "https://example.com", "tags": []},
        headers=alice["headers"],
    )
    assert resp.status_code == 422


def test_get_bookmark(client, alice):
    created = _create(client, alice["headers"]).json()
    resp = client.get(f"/api/bookmarks/{created['id']}", headers=alice["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_missing_bookmark(client, alice):
    resp = client.get("/api/bookmarks/999999", headers=alice["headers"])
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_update_bookmark_replaces_tags(client, alice):
    created = _create(client, alice["headers"]).json()
    resp = client.put(
        f"/api/bookmarks/{created['id']}",
        json={"title": "Updated Title", "tags": ["sql", "backend"]},
        headers=alice["headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated Title"
    assert body["tags"] == ["backend", "sql"]  # ordered by name


def test_delete_bookmark(client, alice):
    created = _create(client, alice["headers"]).json()
    resp = client.delete(f"/api/bookmarks/{created['id']}", headers=alice["headers"])
    assert resp.status_code == 204
    # Now gone.
    gone = client.get(f"/api/bookmarks/{created['id']}", headers=alice["headers"])
    assert gone.status_code == 404


def test_ownership_isolation(client, alice, bob):
    """Bob must never see or touch Alice's bookmark."""
    created = _create(client, alice["headers"]).json()

    # Bob's list is empty; Alice's has one.
    assert client.get("/api/bookmarks", headers=bob["headers"]).json()["pagination"]["total"] == 0
    assert client.get("/api/bookmarks", headers=alice["headers"]).json()["pagination"]["total"] == 1

    # Bob gets 404 (not 403) — no leak that the bookmark exists.
    assert client.get(f"/api/bookmarks/{created['id']}", headers=bob["headers"]).status_code == 404
    assert client.put(
        f"/api/bookmarks/{created['id']}", json={"title": "hax"}, headers=bob["headers"]
    ).status_code == 404
    assert client.delete(
        f"/api/bookmarks/{created['id']}", headers=bob["headers"]
    ).status_code == 404

    # Alice's bookmark is untouched.
    assert client.get(f"/api/bookmarks/{created['id']}", headers=alice["headers"]).json()[
        "title"
    ] == "Great Article"
