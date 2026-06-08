"""ETag / optimistic-concurrency (If-Match) behaviour at the HTTP layer."""


def _create(client, headers, title="Doc"):
    return client.post(
        "/api/bookmarks",
        json={"url": "https://example.com", "title": title, "tags": ["python"]},
        headers=headers,
    )


def test_create_returns_etag_and_version(client, alice):
    resp = _create(client, alice["headers"])
    assert resp.status_code == 201
    assert resp.headers["etag"] == '"1"'
    assert resp.json()["version"] == 1


def test_get_returns_etag(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    resp = client.get(f"/api/bookmarks/{bid}", headers=alice["headers"])
    assert resp.status_code == 200
    assert resp.headers["etag"] == '"1"'


def test_update_without_if_match_is_rejected(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    resp = client.put(
        f"/api/bookmarks/{bid}", json={"title": "New"}, headers=alice["headers"]
    )
    assert resp.status_code == 428
    assert resp.json()["error"]["code"] == "PRECONDITION_REQUIRED"


def test_update_with_stale_if_match_conflicts(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    resp = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "New"},
        headers={**alice["headers"], "If-Match": '"999"'},
    )
    assert resp.status_code == 412
    assert resp.json()["error"]["code"] == "PRECONDITION_FAILED"


def test_update_with_correct_if_match_succeeds_and_bumps_version(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    resp = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "New"},
        headers={**alice["headers"], "If-Match": '"1"'},
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 2
    assert resp.headers["etag"] == '"2"'


def test_update_with_wildcard_if_match(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    resp = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "New"},
        headers={**alice["headers"], "If-Match": "*"},
    )
    assert resp.status_code == 200


def test_delete_requires_and_validates_if_match(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    # Missing → 428
    assert client.delete(f"/api/bookmarks/{bid}", headers=alice["headers"]).status_code == 428
    # Wrong → 412
    assert client.delete(
        f"/api/bookmarks/{bid}", headers={**alice["headers"], "If-Match": '"5"'}
    ).status_code == 412
    # Correct → 204
    assert client.delete(
        f"/api/bookmarks/{bid}", headers={**alice["headers"], "If-Match": '"1"'}
    ).status_code == 204


def test_lost_update_is_prevented(client, alice):
    """Two clients read the same version; the first write wins, the second
    (with the now-stale ETag) is rejected with 412 — no silent lost update."""
    bid = _create(client, alice["headers"]).json()["id"]

    # Both clients hold ETag "1".
    etag_a = etag_b = '"1"'

    # Client A updates successfully → version becomes 2.
    first = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "From A"},
        headers={**alice["headers"], "If-Match": etag_a},
    )
    assert first.status_code == 200
    assert first.headers["etag"] == '"2"'

    # Client B tries with the stale ETag "1" → conflict, A's write preserved.
    second = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "From B"},
        headers={**alice["headers"], "If-Match": etag_b},
    )
    assert second.status_code == 412

    # The bookmark still has A's change.
    current = client.get(f"/api/bookmarks/{bid}", headers=alice["headers"]).json()
    assert current["title"] == "From A"
    assert current["version"] == 2


def test_tag_only_update_bumps_version_and_etag(client, alice):
    """A tag-only edit must advance the version + ETag (not freeze the guard)."""
    bid = _create(client, alice["headers"]).json()["id"]  # version 1, tags ["python"]
    r = client.put(
        f"/api/bookmarks/{bid}",
        json={"tags": ["sql"]},
        headers={**alice["headers"], "If-Match": '"1"'},
    )
    assert r.status_code == 200
    assert r.json()["tags"] == ["sql"]
    assert r.json()["version"] == 2
    assert r.headers["etag"] == '"2"'
    # The old ETag is now stale → rejected (guard works for tag-only edits too).
    r2 = client.put(
        f"/api/bookmarks/{bid}",
        json={"tags": ["x"]},
        headers={**alice["headers"], "If-Match": '"1"'},
    )
    assert r2.status_code == 412


def test_if_match_list_matches_any(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    r = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "L"},
        headers={**alice["headers"], "If-Match": '"999", "1"'},
    )
    assert r.status_code == 200


def test_weak_etag_is_rejected(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    r = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "W"},
        headers={**alice["headers"], "If-Match": 'W/"1"'},
    )
    assert r.status_code == 412


def test_unquoted_if_match_is_rejected(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    r = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "U"},
        headers={**alice["headers"], "If-Match": "1"},  # bare, unquoted → invalid
    )
    assert r.status_code == 412


def test_not_found_precedes_precondition(client, alice):
    """A mutation on a missing/non-owned id is 404 — never 412/428 — so the
    precondition path can't be used to probe for existence."""
    assert client.put(
        "/api/bookmarks/999999",
        json={"title": "x"},
        headers={**alice["headers"], "If-Match": '"1"'},
    ).status_code == 404
    assert client.delete(
        "/api/bookmarks/999999",
        headers={**alice["headers"], "If-Match": '"1"'},
    ).status_code == 404


def test_412_carries_recovery_etag(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    r = client.put(
        f"/api/bookmarks/{bid}",
        json={"title": "x"},
        headers={**alice["headers"], "If-Match": '"999"'},
    )
    assert r.status_code == 412
    assert r.json()["error"]["details"]["expected"] == '"1"'
    assert r.headers["etag"] == '"1"'  # client can retry without an extra GET


def test_428_carries_current_etag(client, alice):
    bid = _create(client, alice["headers"]).json()["id"]
    r = client.put(f"/api/bookmarks/{bid}", json={"title": "x"}, headers=alice["headers"])
    assert r.status_code == 428
    assert r.headers["etag"] == '"1"'
