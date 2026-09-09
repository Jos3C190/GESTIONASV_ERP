"""Pydantic DTOs (Data Transfer Objects).

DTOs are intentionally separate from ORM models. Routers never return ORM
models directly; they always serialize through a `*Out` schema. This keeps the
HTTP contract stable even if the DB model evolves.
"""
