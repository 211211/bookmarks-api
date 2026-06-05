"""Search, filtering, and pagination on the list endpoint."""

from datetime import datetime, timedelta, timezone


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
    today = datetime.now(timezone.utc).date()
    yesterday = (today - timedelta(days=1)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()

    # An old upper bound excludes all.
    resp = client.get("/api/bookmarks", params={"to": "2000-01-01"}, headers=alice["headers"])
    assert resp.json()["pagination"]["total"] == 0
    # A wide range includes all four.
    resp = client.get(
        "/api/bookmarks",
        params={"from": "2000-01-01", "to": "2999-12-31"},
        headers=alice["headers"],
    )
    assert resp.json()["pagination"]["total"] == 4
    # Inclusive same-day boundary: from=today AND to=today must include all four
    # (exercises the time.min/time.max UTC expansion of the date bounds).
    resp = client.get(
        "/api/bookmarks",
        params={"from": today.isoformat(), "to": today.isoformat()},
        headers=alice["headers"],
    )
    assert resp.json()["pagination"]["total"] == 4
    # A lower bound of tomorrow excludes everything created today.
    resp = client.get("/api/bookmarks", params={"from": tomorrow}, headers=alice["headers"])
    assert resp.json()["pagination"]["total"] == 0
    # An upper bound of yesterday excludes everything created today.
    resp = client.get("/api/bookmarks", params={"to": yesterday}, headers=alice["headers"])
    assert resp.json()["pagination"]["total"] == 0


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
    _seed_bookmarks(client, alice["headers"])  # 4 bookmarks, per_page=2 → exact multiple

    seen: list[int] = []
    cursor = 999999
    pages = 0
    while True:
        body = client.get(
            "/api/bookmarks", params={"per_page": 2, "cursor": cursor}, headers=alice["headers"]
        ).json()
        ids = [b["id"] for b in body["items"]]
        seen.extend(ids)
        pages += 1
        if not body["pagination"]["has_next"]:
            # Terminator: the final page reports no next page and a null cursor,
            # even though it was a full page (4 is an exact multiple of 2).
            assert body["pagination"]["next_cursor"] is None
            break
        cursor = body["pagination"]["next_cursor"]
        assert cursor is not None
        assert pages < 10  # guard against an infinite loop

    # Exactly two full pages, no overlap, full coverage — no trailing empty request.
    assert pages == 2
    assert len(seen) == len(set(seen)) == 4
