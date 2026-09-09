"""Core layer: cross-cutting infrastructure (config, logging, security, deps).

This package must NOT depend on `app.api`, `app.application`, or
`app.infrastructure` beyond the bare minimum needed for type hints (which we
keep one-directional via the dependency-injection container in `deps.py`).
"""

from app.core.config import settings

__all__ = ["settings"]
