from __future__ import annotations

import uuid

import pytest
from app.api.v1.routers import purchase_consolidations as router
from fastapi import HTTPException
from starlette.requests import Request


class SelectedRequestUseCases:
    def __init__(self, resolutions: list[dict[str, object]]) -> None:
        self.resolutions = resolutions
        self.requested_ids: tuple[uuid.UUID, ...] | None = None

    async def resolve_selected_requests(
        self, company_id: uuid.UUID, request_ids: tuple[uuid.UUID, ...]
    ) -> list[dict[str, object]]:
        self.requested_ids = request_ids
        return self.resolutions

    async def get(self, company_id: uuid.UUID, consolidation_id: uuid.UUID) -> object:
        return object()


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/purchase-consolidations/selected-requests",
            "raw_path": b"/api/v1/purchase-consolidations/selected-requests",
            "query_string": b"",
            "headers": [],
            "client": ("test", 0),
            "server": ("test", 80),
            "state": {},
            "app": object(),
        }
    )


@pytest.mark.asyncio
async def test_selected_request_resolution_hides_consolidation_outside_user_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = uuid.uuid4()
    request_id = uuid.uuid4()
    consolidation_id = uuid.uuid4()
    fake = SelectedRequestUseCases(
        [
            {
                "id": request_id,
                "code": "SCR-00035",
                "eligibility": "already_consolidated",
                "consolidations": (
                    {
                        "id": consolidation_id,
                        "code": "CD-00005",
                        "status": "draft",
                    },
                ),
            }
        ]
    )

    async def allow_request_scope(**kwargs: object) -> None:
        return None

    async def deny_consolidation_scope(*args: object, **kwargs: object) -> None:
        raise HTTPException(status_code=403, detail="No tiene acceso a todas las sucursales.")

    monkeypatch.setattr(router, "request_company_id", lambda request: company_id)
    monkeypatch.setattr(router, "_assert_request_scope", allow_request_scope)
    monkeypatch.setattr(router, "_assert_consolidation_scope", deny_consolidation_scope)

    result = await router.resolve_selected_purchase_requests(
        request=_request(),
        session=None,  # type: ignore[arg-type]
        current=None,  # type: ignore[arg-type]
        request_ids=[request_id, request_id],
        use_cases=fake,  # type: ignore[arg-type]
    )

    assert fake.requested_ids == (request_id,)
    assert len(result) == 1
    assert result[0].eligibility == "unavailable"
    assert result[0].code == "SCR-00035"
    assert result[0].consolidations == ()
    assert str(consolidation_id) not in str(result[0].model_dump())
