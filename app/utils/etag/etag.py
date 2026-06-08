"""Version-based ETag service.

The ETag is a **strong** validator derived from the bookmark's integer version
counter, formatted as a quoted string (e.g. ``"3"``). `If-Match` is compared with
strong comparison per RFC 7232 §3.1: weak validators (``W/"..."``) never match,
and ``*`` matches any existing resource.
"""

from __future__ import annotations

from app.utils.etag.interface import IETagService


class VersionETagService(IETagService):
    def make_etag(self, version: int) -> str:
        return f'"{version}"'

    def matches(self, if_match_header: str, version: int) -> bool:
        current = str(version)
        for token in if_match_header.split(","):
            tag = token.strip()
            if not tag:
                continue
            if tag == "*":
                # `*` matches any current representation of an existing resource.
                return True
            if tag.startswith("W/"):
                # Weak validators must not be used for If-Match (strong comparison).
                continue
            # Require a syntactically valid *quoted* strong entity-tag (RFC 7232);
            # bare/unquoted tokens like `1` are invalid and never match.
            if len(tag) >= 2 and tag[0] == '"' and tag[-1] == '"':
                if tag[1:-1] == current:
                    return True
        return False
