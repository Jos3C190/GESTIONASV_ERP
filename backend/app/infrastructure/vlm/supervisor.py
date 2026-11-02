"""Runs the model server only while there is work, so idle means zero VRAM.

The server is a child process bound to loopback. Ending the process is the only
way to be sure the GPU memory comes back, and because the worker is the
container's main process a crash cannot leave the server orphaned.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager


class GpuBusyError(Exception):
    """Another application holds the VRAM; try later without spending an attempt."""


class ModelStartError(Exception):
    """The server did not become ready."""


ReadyCheck = Callable[[], Awaitable[bool]]
FreeVram = Callable[[], Awaitable[int | None]]


class ModelSupervisor:
    def __init__(
        self,
        command: Sequence[str],
        *,
        is_ready: ReadyCheck,
        free_vram_mib: FreeVram,
        min_free_vram_mib: int,
        idle_seconds: float,
        startup_timeout_seconds: float,
        poll_seconds: float = 0.2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._command = tuple(command)
        self._is_ready = is_ready
        self._free_vram_mib = free_vram_mib
        self._min_free_vram_mib = min_free_vram_mib
        self._idle_seconds = idle_seconds
        self._startup_timeout_seconds = startup_timeout_seconds
        self._poll_seconds = poll_seconds
        self._clock = clock
        # El mismo candado protege todo el estado: un cierre y un nuevo uso no pueden cruzarse.
        self._lock = asyncio.Lock()
        self._process: asyncio.subprocess.Process | None = None
        self._in_flight = 0
        self._last_used = clock()
        self.last_load_seconds: float | None = None

    @property
    def loaded(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def idle_seconds_elapsed(self) -> float:
        return self._clock() - self._last_used

    async def _start(self) -> None:
        free = await self._free_vram_mib()
        if free is not None and free < self._min_free_vram_mib:
            raise GpuBusyError
        started = self._clock()
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            # Sin credenciales: el modelo procesa imágenes y no necesita nada del ERP.
            env={"PATH": os.environ.get("PATH", ""), "LD_LIBRARY_PATH": _ld_path()},
            stdin=asyncio.subprocess.DEVNULL,
            # Nunca se registra su salida: podría incluir lo leído en la licencia.
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = started + self._startup_timeout_seconds
        while self._clock() < deadline:
            if self._process.returncode is not None:
                self._process = None
                raise ModelStartError
            if await self._is_ready():
                self.last_load_seconds = self._clock() - started
                return
            await asyncio.sleep(self._poll_seconds)
        await self._stop()
        raise ModelStartError

    async def _stop(self) -> None:
        process, self._process = self._process, None
        if process is None or process.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()

    async def ensure_started(self) -> bool:
        """Load the model if needed. Returns whether this call had to load it."""
        async with self._lock:
            self._last_used = self._clock()
            if self.loaded:
                return False
            self._process = None
            await self._start()
            return True

    @asynccontextmanager
    async def lease(self) -> AsyncIterator[bool]:
        """Keep the model up for one job; yields whether the job paid for a cold start."""
        async with self._lock:
            self._last_used = self._clock()
            cold = not self.loaded
            if cold:
                self._process = None
                await self._start()
            self._in_flight += 1
        try:
            yield cold
        finally:
            async with self._lock:
                self._in_flight -= 1
                self._last_used = self._clock()

    async def stop_if_idle(self) -> bool:
        async with self._lock:
            if (
                not self.loaded
                or self._in_flight > 0
                or self.idle_seconds_elapsed < self._idle_seconds
            ):
                return False
            await self._stop()
            return True

    async def shutdown(self) -> None:
        async with self._lock:
            await self._stop()


def _ld_path() -> str:
    return os.environ.get("LD_LIBRARY_PATH", "")
