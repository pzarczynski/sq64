import logging
import os
import sys
from functools import partial
from itertools import islice
from threading import Event, Thread, Timer

from .engine import Engine
from .position import Position

logging.basicConfig(format="%(levelname)s: %(message)s", stream=sys.stderr)

print = partial(print, flush=True)  # noqa: A001


def go_loop(
    engine: Engine, pos: Position, stop: Event, movetime: float | None, depth: int,
) -> None:
    """Runs the engine's search loop, printing info lines and the best move when done."""
    if movetime is not None:  # infinite when none
        Timer(movetime, stop.set).start()

    pv = None

    # iterate no deeper than requested `depth` w/ islice
    for d, (cp, pv, nds, t) in enumerate(islice(engine.go(pos, stop=stop), depth)):
        pvs = " ".join(str(m) for m in pv)
        print(f"info score cp {cp} depth {d+1} nodes {nds} nps {int(nds / t)} pv {pvs}")
        if stop.is_set(): break

    bestmove = pv[0] if pv else "(none)"
    print("bestmove ", bestmove)
    logging.debug("bestmove '%s'", bestmove)


def uci_loop() -> None:
    """Main loop to handle UCI commands from standard input and interact with the chess engine accordingly."""
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

                fen = None if next(iargs) == "startpos" else " ".join(islice(iargs, 6))
                pos = Position(fen)

                if next(iargs, None) == "moves":
                    _ = all(map(pos.push_uci, iargs))  # push all moves

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
                    daemon=True,
                ).start()

            case _: ...


def main() -> None:
    debug = int(os.getenv("DEBUG", 0))
    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
    uci_loop()


if __name__ == "__main__":
    main()
