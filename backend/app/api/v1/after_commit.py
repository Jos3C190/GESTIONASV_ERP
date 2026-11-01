"""Run work once a request's database transaction has committed.

A request session commits after the endpoint and its background tasks have
run, so follow-up work that must read the committed data (syncing Traccar,
archiving a trail) starts from the commit itself, and never on rollback.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

#: Tasks started after a commit; kept so they are not garbage-collected mid-flight.
_pending: set[asyncio.Task[None]] = set()


def run_after_commit(session: AsyncSession, job: Callable[[], Coroutine[Any, Any, None]]) -> None:
    def _start(_sync_session: Any) -> None:
        task = asyncio.get_running_loop().create_task(job())
        _pending.add(task)
        task.add_done_callback(_pending.discard)

    event.listen(session.sync_session, "after_commit", _start, once=True)


async def wait_for_pending() -> None:
    """Await work started by recent commits (tests and graceful shutdown)."""
    while _pending:
        tasks = list(_pending)
        await asyncio.gather(*tasks, return_exceptions=True)
        _pending.difference_update(tasks)
