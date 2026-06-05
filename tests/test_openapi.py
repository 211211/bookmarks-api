"""OpenAPI spec validity + contract validation of real responses against the
component schemas the API advertises."""

import pytest
from jsonschema import Draft202012Validator

try:  # openapi-spec-validator >= 0.7
    from openapi_spec_validator import validate as validate_openapi
except ImportError:  # pragma: no cover - older API
    from openapi_spec_validator import validate_spec as validate_openapi

from tests.conftest import register


@pytest.fixture
def spec(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()


def _validate(spec, component: str, instance) -> None:
    """Validate `instance` against `#/components/schemas/<component>`,
    resolving internal $refs within the spec document."""
    schema = {"$ref": f"#/components/schemas/{component}", "components": spec["components"]}
    Draft202012Validator(schema).validate(instance)


def test_openapi_spec_is_valid(spec):
    validate_openapi(spec)
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"]


def test_swagger_docs_served(client):
    assert client.get("/docs").status_code == 200


def test_security_scheme_documented(spec):
    schemes = spec.get("components", {}).get("securitySchemes", {})
    bearer = [
        s for s in schemes.values() if s.get("type") == "http" and s.get("scheme") == "bearer"
    ]
    assert bearer, "A bearer (JWT) security scheme must be documented."

    # Protected operations must declare a security requirement.
    create_op = spec["paths"]["/api/bookmarks"]["post"]
    assert create_op.get("security"), "POST /api/bookmarks must require auth in the spec."

    # Public auth routes should NOT require security.
    login_op = spec["paths"]["/api/auth/login"]["post"]
    assert not login_op.get("security")


def test_auth_response_conforms(client, spec):
    data = register(client)
    _validate(spec, "AuthResponse", data)


def test_bookmark_response_conforms(client, spec, alice):
    resp = client.post(
        "/api/bookmarks",
        json={"url": "https://example.com", "title": "Doc", "tags": ["python"]},
        headers=alice["headers"],
    )
    assert resp.status_code == 201
    _validate(spec, "BookmarkOut", resp.json())


def test_list_response_conforms(client, spec, alice):
    client.post(
        "/api/bookmarks",
        json={"url": "https://example.com", "title": "Doc", "tags": ["python"]},
        headers=alice["headers"],
    )
    resp = client.get("/api/bookmarks", headers=alice["headers"])
    _validate(spec, "BookmarkPage", resp.json())


def test_stats_response_conforms(client, spec, alice):
    resp = client.get("/api/bookmarks/stats", headers=alice["headers"])
    _validate(spec, "StatsResponse", resp.json())


def test_error_response_conforms(client, spec, alice):
    resp = client.get("/api/bookmarks/999999", headers=alice["headers"])
    assert resp.status_code == 404
    _validate(spec, "ErrorResponse", resp.json())
