"""Search, filtering, and pagination on the list endpoint."""


def _seed_bookmarks(client, headers):
    rows = [
        ("https://a.com", "Python tutorial", "learn python", ["python", "tutorial"]),
        ("https://b.com", "FastAPI guide", "build apis", ["python", "fastapi"]),
        ("https://c.com", "SQL basics", "joins and indexes", ["sql"]),
        ("https://d.com", "Rust intro", "systems language", ["rust"]),
    ]
    for url, title, desc, tags in rows:
        resp = client.post(
            "/api/bookmarks",
            json={"url": url, "title": title, "description": desc, "tags": tags},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text


def test_filter_by_tag(client, alice):
    _seed_bookmarks(client, alice["headers"])
    resp = client.get("/api/bookmarks", params={"tag": "python"}, headers=alice["headers"])
    assert resp.status_code == 200
    titles = {b["title"] for b in resp.json()["items"]}
    assert titles == {"Python tutorial", "FastAPI guide"}


def test_search_keyword(client, alice):
    _seed_bookmarks(client, alice["headers"])
    # Keyword matches title or description, case-insensitively.
    resp = client.get("/api/bookmarks", params={"q": "JOINS"}, headers=alice["headers"])
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "SQL basics"


def test_combined_tag_and_keyword(client, alice):
    _seed_bookmarks(client, alice["headers"])
    resp = client.get(
        "/api/bookmarks", params={"tag": "python", "q": "guide"}, headers=alice["headers"]
    )
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "FastAPI guide"


def test_date_range_filter(client, alice):
    _seed_bookmarks(client, alice["headers"])
    # Everything was created today; an old upper bound excludes all.
    resp = client.get("/api/bookmarks", params={"to": "2000-01-01"}, headers=alice["headers"])
    assert resp.json()["pagination"]["total"] == 0
    # A wide range includes all four.
    resp = client.get(
        "/api/bookmarks", params={"from": "2000-01-01", "to": "2999-12-31"}, headers=alice["headers"]
    )
    assert resp.json()["pagination"]["total"] == 4


def test_pagination_total_count(client, alice):
    _seed_bookmarks(client, alice["headers"])
    resp = client.get(
        "/api/bookmarks", params={"page": 1, "per_page": 2}, headers=alice["headers"]
    )
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["pagination"]["total"] == 4
    assert body["pagination"]["total_pages"] == 2
    assert body["pagination"]["has_next"] is True
    assert body["pagination"]["has_prev"] is False

    page2 = client.get(
        "/api/bookmarks", params={"page": 2, "per_page": 2}, headers=alice["headers"]
    ).json()
    assert len(page2["items"]) == 2
    assert page2["pagination"]["has_next"] is False
    assert page2["pagination"]["has_prev"] is True


def test_cursor_pagination(client, alice):
    _seed_bookmarks(client, alice["headers"])
    first = client.get(
        "/api/bookmarks", params={"per_page": 2, "cursor": 999999}, headers=alice["headers"]
    ).json()
    assert len(first["items"]) == 2
    assert first["pagination"]["next_cursor"] is not None

    cursor = first["pagination"]["next_cursor"]
    second = client.get(
        "/api/bookmarks", params={"per_page": 2, "cursor": cursor}, headers=alice["headers"]
    ).json()
    assert len(second["items"]) == 2
    # No overlap between pages.
    first_ids = {b["id"] for b in first["items"]}
    second_ids = {b["id"] for b in second["items"]}
    assert first_ids.isdisjoint(second_ids)
