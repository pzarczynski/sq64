import contextlib
from subprocess import PIPE, Popen
from threading import Event, Thread


class UCI:
    _process: Popen[str]
    _bestmove: str | None
    _thinking: bool
    _ready_event: Event
    _move_event: Event

    @property
    def bestmove(self) -> str | None: return self._bestmove
    @property
    def thinking(self) -> bool: return self._thinking

    def __init__(self, cmd: str) -> None:
        self._process = Popen(cmd.split(), stdin=PIPE, stdout=PIPE, text=True, bufsize=1)  # noqa: S603
        self._bestmove = None
        self._thinking = False
        self._ready_event = Event()
        self._move_event = Event()

        def reader() -> None:
            if self._process.stdout is not None:
                for line in map(str.strip, self._process.stdout): # type: ignore
                    if line.startswith("bestmove"):
                        self._bestmove = line.split()[1]
                        self._thinking = False
                        self._move_event.set()
                    elif line == "readyok":
                        self._ready_event.set()

        Thread(target=reader, daemon=True).start()
        self._send("uci")

        if not self.wait_for_ready():
            raise TimeoutError("UCI engine did not respond in time.")

    def _send(self, cmd: str) -> None:
        with contextlib.suppress(BrokenPipeError):
            if self._process.stdin is not None:
                _ = self._process.stdin.write(cmd + "\n")
                self._process.stdin.flush()

    def wait_for_ready(self, timeout: float = 2.0) -> bool:
        self._ready_event.clear()
        self._send("isready")
        return self._ready_event.wait(timeout=timeout)

    def wait_for_move(self, timeout: float = 5.0) -> bool:
        return self._thinking and self._move_event.wait(timeout=timeout)

    def stop(self) -> None:
        self._send("stop")
        if not self.wait_for_ready(timeout=1.0): raise TimeoutError
        self._bestmove = None
        self._thinking = False
        self._move_event.clear()

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
