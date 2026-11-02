from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from app.domain.ports.vision_extractor import VisionExtractionError
from app.infrastructure.vlm.client import clean_values
from app.infrastructure.vlm.supervisor import GpuBusyError, ModelStartError, ModelSupervisor

SERVER = [sys.executable, "-c", "import time; time.sleep(60)"]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def _ready() -> bool:
    return True


async def _plenty_of_vram() -> int | None:
    return 6000


def _supervisor(clock: Clock, **overrides: object) -> ModelSupervisor:
    options: dict[str, object] = {
        "is_ready": _ready,
        "free_vram_mib": _plenty_of_vram,
        "min_free_vram_mib": 3000,
        "idle_seconds": 300,
        "startup_timeout_seconds": 5,
        "poll_seconds": 0.01,
        "clock": clock,
        **overrides,
    }
    return ModelSupervisor(options.pop("command", SERVER), **options)  # type: ignore[arg-type]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def test_starts_only_when_leased_and_reports_cold_then_warm() -> None:
    supervisor = _supervisor(Clock())
    assert not supervisor.loaded

    async with supervisor.lease() as first:
        assert first is True
        assert supervisor.loaded
    async with supervisor.lease() as second:
        assert second is False

    await supervisor.shutdown()


async def test_idle_model_is_stopped_and_its_process_ends() -> None:
    clock = Clock()
    supervisor = _supervisor(clock)
    async with supervisor.lease():
        pid = supervisor._process.pid  # type: ignore[union-attr]

    clock.now += 299
    assert await supervisor.stop_if_idle() is False
    assert supervisor.loaded

    clock.now += 2
    assert await supervisor.stop_if_idle() is True
    assert not supervisor.loaded
    await asyncio.sleep(0.05)
    assert not _alive(pid)


async def test_model_in_use_is_never_stopped_however_long_it_takes() -> None:
    clock = Clock()
    supervisor = _supervisor(clock)

    async with supervisor.lease():
        clock.now += 10_000
        assert await supervisor.stop_if_idle() is False
        assert supervisor.loaded

    await supervisor.shutdown()


async def test_new_lease_restarts_the_clock_so_it_cannot_cross_with_a_stop() -> None:
    clock = Clock()
    supervisor = _supervisor(clock)
    async with supervisor.lease():
        pass
    clock.now += 1_000

    lease = supervisor.lease()
    await lease.__aenter__()
    stopped = await supervisor.stop_if_idle()
    await lease.__aexit__(None, None, None)

    assert stopped is False
    assert supervisor.loaded
    await supervisor.shutdown()


async def test_crashed_server_is_replaced_on_the_next_lease() -> None:
    supervisor = _supervisor(Clock())
    async with supervisor.lease():
        process = supervisor._process
    assert process is not None
    process.kill()
    await process.wait()
    assert not supervisor.loaded

    async with supervisor.lease() as cold:
        assert cold is True
        assert supervisor.loaded

    await supervisor.shutdown()


async def test_not_enough_vram_does_not_start_anything() -> None:
    async def little() -> int | None:
        return 1000

    supervisor = _supervisor(Clock(), free_vram_mib=little)

    with pytest.raises(GpuBusyError):
        async with supervisor.lease():
            pytest.fail("no debe entregar el modelo")

    assert not supervisor.loaded


async def test_unknown_free_vram_still_tries_to_start() -> None:
    async def unknown() -> int | None:
        return None

    supervisor = _supervisor(Clock(), free_vram_mib=unknown)

    async with supervisor.lease():
        assert supervisor.loaded
    await supervisor.shutdown()


async def test_server_that_exits_at_startup_is_reported() -> None:
    async def never() -> bool:
        return False

    supervisor = _supervisor(
        Clock(), command=[sys.executable, "-c", "raise SystemExit(1)"], is_ready=never
    )

    with pytest.raises(ModelStartError):
        await asyncio.wait_for(supervisor.ensure_started(), timeout=0.5)


async def test_server_stuck_loading_is_killed_after_the_timeout() -> None:
    async def never() -> bool:
        return False

    clock = Clock()

    async def advancing() -> bool:
        clock.now += 10
        return await never()

    supervisor = _supervisor(clock, is_ready=advancing)

    with pytest.raises(ModelStartError):
        await supervisor.ensure_started()

    assert not supervisor.loaded


async def test_server_gets_no_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    output = os.path.join(str(tmp_path), "env.txt")
    command = [
        sys.executable,
        "-c",
        f"import os,time; open({output!r},'w').write(os.environ.get('DATABASE_URL','none')); "
        "time.sleep(60)",
    ]
    supervisor = _supervisor(Clock(), command=command)

    async with supervisor.lease():
        for _ in range(100):
            if os.path.exists(output) and os.path.getsize(output):
                break
            await asyncio.sleep(0.05)
    await supervisor.shutdown()

    assert Path(output).read_text(encoding="utf-8") == "none"


def test_clean_values_keeps_only_requested_keys_and_drops_rambling() -> None:
    raw = '{"vence": " 02-2027 ", "dui": null, "extra": "x", "numero": "' + "9" * 200 + '"}'

    values = clean_values(raw, ("vence", "dui", "numero", "clase"))

    assert values == {"vence": "02-2027", "dui": None, "numero": None, "clase": None}


@pytest.mark.parametrize("raw", ["no es json", "[1, 2]", ""])
def test_clean_values_rejects_anything_but_an_object(raw: str) -> None:
    with pytest.raises(VisionExtractionError):
        clean_values(raw, ("vence",))
