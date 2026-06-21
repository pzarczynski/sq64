import time
from collections.abc import Iterator

import pytest
from sq64_engine import UCI


@pytest.fixture
def engine() -> Iterator[UCI]:
    uci = UCI("uv run -m sq64_engine.uci")
    yield uci
    uci.quit()


def test_basic_lifecycle(engine: UCI) -> None:
    assert engine._process.poll() is None
    assert engine.quit() is not None


@pytest.mark.parametrize("movetime_ms", [0, 50, 100, 200, 500])
def test_movetime(engine: UCI, movetime_ms: int) -> None:
    engine.newgame()

    t0 = time.perf_counter()
    engine.go(movetime=movetime_ms)

    got_move = engine.wait_for_move(timeout=movetime_ms / 1000 + 1)
    assert got_move is True
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert engine.bestmove is not None
    assert elapsed_ms <= movetime_ms + 50
