"""Raw-SQL statistics endpoint."""


def test_stats_endpoint(client, alice, bob):
    # Alice's bookmarks.
    for url, title, tags in [
        ("https://a.com", "A", ["python", "sql"]),
        ("https://b.com", "B", ["python"]),
        ("https://c.com", "C", ["python", "fastapi"]),
    ]:
        client.post(
            "/api/bookmarks",
            json={"url": url, "title": title, "tags": tags},
            headers=alice["headers"],
        )
    # Bob's bookmark must not affect Alice's stats.
    client.post(
        "/api/bookmarks",
        json={"url": "https://z.com", "title": "Z", "tags": ["python", "rust"]},
        headers=bob["headers"],
    )

    resp = client.get("/api/bookmarks/stats", headers=alice["headers"])
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_bookmarks"] == 3
    assert body["total_tags"] == 3  # python, sql, fastapi (not rust — that's bob's)

    top = {t["name"]: t["count"] for t in body["top_tags"]}
    assert top["python"] == 3
    assert top["sql"] == 1
    assert top["fastapi"] == 1
    # Ordered by count desc → python first.
    assert body["top_tags"][0]["name"] == "python"

    assert len(body["bookmarks_per_month"]) >= 1
    month_entry = body["bookmarks_per_month"][0]
    assert set(month_entry.keys()) == {"month", "count"}


def test_stats_empty(client, alice):
    resp = client.get("/api/bookmarks/stats", headers=alice["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_bookmarks"] == 0
    assert body["total_tags"] == 0
    assert body["top_tags"] == []
    assert body["bookmarks_per_month"] == []
