"""Repository layer: persistence behind per-entity interfaces.

Each entity has its own subpackage with an ``interface.py`` (the abstract
``I<Entity>Repository``) and a ``repository.py`` (the SQLAlchemy implementation).
Implementations commit on write operations (one session == one unit of work
per request).
"""
