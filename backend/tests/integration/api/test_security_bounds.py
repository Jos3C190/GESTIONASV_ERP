"""Pruebas Adversariales de Seguridad (Red Team Integration Tests).

Prueba el comportamiento defensivo de la API FastAPI ante:
- Intentos de escalada de privilegios (RBAC)
- Tampering y manipulación de Tokens JWT
- Fuzzing de entradas DTO con payloads maliciosos (SQLi, XSS, NUL bytes)
- Resiliencia de DTOs ante cadenas masivas
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport
import jwt
from app.main import create_app
from app.infrastructure.db.session import get_async_session

@pytest.fixture
async def sec_client():
    """Cliente HTTP asíncrono aislado con mock de base de datos para pruebas de seguridad sin side-effects."""
    app = create_app()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    app.dependency_overrides[get_async_session] = lambda: mock_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_rbac_unauthorized_access_fails(sec_client: AsyncClient):
    """Verifica que invocar endpoints protegidos sin Authorization header retorne 401."""
    response = await sec_client.get("/api/v1/users")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_jwt_tampering_none_algorithm(sec_client: AsyncClient):
    """Ataque de tampering: Intentar usar alg: none en el header del JWT."""
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "role": "superadmin",
        "exp": int(time.time()) + 3600
    }
    forged_token = jwt.encode(payload, "", algorithm="none")
    headers = {"Authorization": f"Bearer {forged_token}"}
    
    response = await sec_client.get("/api/v1/users", headers=headers)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_jwt_tampering_invalid_signature(sec_client: AsyncClient):
    """Ataque de tampering: Firma con clave secreta incorrecta."""
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "role": "superadmin",
        "exp": int(time.time()) + 3600
    }
    fake_token = jwt.encode(payload, "clave-falsa-maliciosa-32bytes-secret!", algorithm="HS256")
    headers = {"Authorization": f"Bearer {fake_token}"}
    
    response = await sec_client.get("/api/v1/users", headers=headers)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_dto_fuzzing_sql_injection_payload(sec_client: AsyncClient):
    """Fuzzing de entrada: Enviar SQL Injection en payload de login."""
    malicious_payload = {
        "login": "' OR '1'='1",
        "password": "' OR '1'='1"
    }
    response = await sec_client.post("/api/v1/auth/login", json=malicious_payload)
    assert response.status_code in (401, 422)

@pytest.mark.asyncio
async def test_dto_fuzzing_xss_payload(sec_client: AsyncClient):
    """Fuzzing de entrada: Enviar script XSS en credenciales de login."""
    xss_payload = {
        "login": "<script>alert('xss')</script>",
        "password": "Password123!"
    }
    response = await sec_client.post("/api/v1/auth/login", json=xss_payload)
    assert response.status_code in (401, 422)

@pytest.mark.asyncio
async def test_dto_fuzzing_null_bytes_and_long_strings(sec_client: AsyncClient):
    """Fuzzing de entrada: Enviar bytes nulos y cadenas extremadamente largas (>10,000 chars)."""
    long_string = "A" * 15000 + "\x00"
    payload = {
        "login": long_string,
        "password": "Password123!"
    }
    response = await sec_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code in (401, 422)
    assert response.status_code != 500
