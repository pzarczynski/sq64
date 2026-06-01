import contextlib
import logging
import os
import sys
import threading
from collections import deque
from functools import partial
from itertools import islice
from subprocess import PIPE, Popen
from threading import Event, Thread, Timer

from sq64.engine import Engine
from sq64.position import Position

logging.basicConfig(format='%(levelname)s: %(message)s', stream=sys.stderr)

print = partial(print, flush=True)
consume = partial(deque, maxlen=0)  # consume iterator with side effects

class UCI:
    _process: Popen
    _bestmove: str | None
    _thinking: bool
    _ready: Event

    def __init__(self, path: str) -> None:
        self._process = Popen(path, stdin=PIPE, stdout=PIPE, text=True, bufsize=1)
        self._bestmove: str | None = None
        self._thinking = False
        self._ready = threading.Event()

        def reader() -> None:
            for line in map(str.strip, self._process.stdout): # type: ignore
                if line.startswith("bestmove"):
                    self._bestmove = line.split()[1]
                    self._thinking = False
                elif line == "readyok":
                    self._ready.set()

        threading.Thread(target=reader, daemon=True).start()
        self._send("uci")
        self.wait_for_ready()

    @property
    def bestmove(self) -> str | None: return self._bestmove

    @property
    def thinking(self) -> bool: return self._thinking

    def _send(self, cmd: str) -> None:
        with contextlib.suppress(BrokenPipeError):
            self._process.stdin.write(cmd + "\n")  # type: ignore
            self._process.stdin.flush()  # type: ignore

    def wait_for_ready(self, timeout: float = 2.0) -> bool:
        self._ready.clear()
        self._send("isready")
        return self._ready.wait(timeout=timeout)

    def stop(self) -> None:
        self._send("stop")
        if not self.wait_for_ready(timeout=1.0): raise TimeoutError
        self._bestmove = None
        self._thinking = False

    def newgame(self) -> None:
        self.stop()
        self._send("ucinewgame")

    def quit(self) -> int:
        self._send("quit")
        self._process.terminate()
        return self._process.wait(timeout=1)

    def go(self, fen: str | None = None, movetime: int | None = None) -> None:
        self.stop()
        self._send("position " + (f"fen {fen}" if fen else "startpos"))
        self._send("go " + ("infinite" if movetime is None else f"movetime {movetime}"))
        self._thinking = True


def go_loop(
    engine: Engine, pos: Position, stop: Event, movetime: float | None, depth: int
) -> None:
    if movetime is not None:  # infinite when none
        Timer(movetime, stop.set).start()

    pv = None

    # iterate no deeper than requested `depth` w/ islice
    for d, (cp, pv, nds, t) in enumerate(islice(engine.go(pos, stop=stop), depth)):
        pvs = ' '.join(str(m) for m in pv)
        print(f"info score cp {cp} depth {d+1} nodes {nds} nps {int(nds / t)} pv {pvs}")
        if stop.is_set(): break

    bestmove = pv[0] if pv else "(none)"
    print("bestmove ", bestmove)
    logging.debug("bestmove '%s'", bestmove)


def uci_loop() -> None:
    engine = Engine()
    pos = Position()
    stop = Event()

    for line in map(str.strip, sys.stdin):
        logging.debug("received command '%s'", line)
        cmd, *args = line.split()

        match cmd:
            case "stop" | "quit":
                stop.set()
                if cmd == "quit": break

            case "uci":
                print("id name sq64 v1")
                print("id author Piotr Zarczynski")
                print("uciok")

            case "isready":
                print("readyok")

            case "ucinewgame":
                engine.clear()

            case "position":
                iargs = iter(args)

                fen = None if next(iargs) == "startpos" else ' '.join(islice(iargs, 6))
                pos = Position(fen)

                if next(iargs, None) == "moves":
                    consume(map(pos.push_uci, iargs))  # push all moves

            case "go":
                stop.set()
                movetime, depth = None, 100
                wtime = btime = winc = binc = 0

                def to_s(ms: str) -> float:
                    return int(ms) / 1000

                iargs = iter(args)
                for arg in iargs:
                    match arg:
                        case "movetime": movetime = to_s(next(iargs))
                        case "wtime":    wtime    = to_s(next(iargs))
                        case "btime":    btime    = to_s(next(iargs))
                        case "winc":     winc     = to_s(next(iargs))
                        case "binc":     binc     = to_s(next(iargs))
                        case "depth":    depth    =  int(next(iargs))

                # we prioritize movetime over time+inc
                if movetime is None:
                    t, inc = (wtime, winc) if pos.color else (btime, binc)
                    if t > 0:
                        movetime = min(t / 40 + 0.9 * inc, t / 2 - 0.1)

                stop = Event()
                Thread(
                    target=go_loop,
                    args=(engine, pos, stop, movetime, depth),
                    daemon=True
                ).start()

if __name__ == "__main__":
    debug = int(os.getenv("DEBUG", 0))
    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
    uci_loop()
