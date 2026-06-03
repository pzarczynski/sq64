from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial

from sq64 import chess
from sq64.chess import Board, Move, Piece, Square, State

consume = partial(deque, maxlen=0)  # consume iterator with side effects


@dataclass(slots=True)
class Time:
    time_ms: int
    incr_ms: int

    @classmethod
    def natural(cls, minutes: int, incr: int) -> "Time":
        """a natural way to specify time control (minutes + increment in seconds)"""
        return cls(minutes * 60000, incr * 1000)  # to ms

    @property
    def minutes(self) -> int: return self.time_ms // 60000
    @property
    def seconds(self) -> int: return (self.time_ms // 1000) % 60
    @property
    def increment(self) -> int: return self.incr_ms // 1000

    def tick(self, dt_ms: int) -> None: self.time_ms -= dt_ms
    def add_increment(self) -> None: self.time_ms += self.incr_ms

    def __str__(self) -> str: return f"{self.minutes:02d}:{self.seconds:02d}"
    def __iter__(self) -> Iterator[int]: return iter((self.time_ms, self.incr_ms))


class Tempo(Enum):
    # factories so that the time is not shared between instances
    BULLET = ('bullet', lambda: Time.natural( 1, 0))
    BLITZ  = ('blitz',  lambda: Time.natural( 3, 2))
    RAPID  = ('rapid',  lambda: Time.natural(10, 5))

    @property
    def value(self) -> str: return self.label

    def __init__(self, label: str, time_fn: Callable[[], Time]) -> None:
        self.label = label
        self.time_fn = time_fn

    def __str__(self) -> str:
        t = self.time_fn()
        return f"{t.minutes}\" + {t.increment}\'"


class Movetime(Enum):
    FAST   = ('fast',   lambda time, inc: int(min(time / 80 + inc * 0.5, time / 4)))
    NORMAL = ('normal', lambda time, inc: int(min(time / 40 + inc * 0.7, time / 2)))
    SLOW   = ('slow',   lambda time, inc: int(min(time / 30 + inc * 0.9, time * 0.9)))

    def __init__(self, label: str, movetime_fn: Callable[[int, int], int]) -> None:
        self.label = label
        self.movetime_fn = movetime_fn

    def __call__(self, time: int, inc: int) -> int: return self.movetime_fn(time, inc)


class Outcome(Enum):
    CHECKMATE = auto()
    TIME_OVER = auto()

    STALEMATE = auto()
    THREEFOLD = auto()
    FIFTY_MOVES = auto()
    INSUFFICIENT = auto()

    def pretty(self, enemy: str) -> str:
        match self:
            case Outcome.CHECKMATE:
                return f"{enemy} wins by checkmate"
            case Outcome.TIME_OVER:
                return f"{enemy} wins on time"
            case Outcome.STALEMATE:
                return  "Draw by stalemate"
            case Outcome.THREEFOLD:
                return "Draw by threefold repetition"
            case Outcome.FIFTY_MOVES:
                return "Draw by fifty-move rule"
            case Outcome.INSUFFICIENT:
                return "Draw by insufficient material"


class Game(Board):
    fullmoves: int
    halfmoves: int
    history: list[State]
    control: list[Time]

    def __init__(self, fen: str, control: list[Time]) -> None:
        super().__init__(fen)
        *_, fn, hc = fen.split()
        self.fullmoves, self.halfmoves = int(fn), int(hc)
        self.history = []
        self.control = control

    def is_insufficient_material(self) -> bool:
        pieces = [p for _, p in self]
        if len(pieces) == 2: return True  # only kings
        return len(pieces) == 3 and any(p.type in (chess.BISHOP, chess.KNIGHT) for p in pieces)

    def is_stalemate(self) -> bool: return not self.is_check() and not self.legal_moves()
    def is_checkmate(self) -> bool: return self.is_check() and not self.legal_moves()
    def is_threefold(self) -> bool: return sum(1 for s in self.history if s.hash == self.hash) >= 2
    def is_fifty_moves(self) -> bool: return self.halfmoves >= 100
    def is_time_over(self) -> bool: return self.control[self.color].time_ms <= 0

    def is_decisive(self) -> bool:
        return self.is_checkmate() or self.is_time_over()

    def is_draw(self) -> bool:
        return (self.is_stalemate() or self.is_fifty_moves() or
                self.is_threefold() or self.is_insufficient_material())

    def is_game_over(self) -> bool:
        return self.is_decisive() or self.is_draw()

    @property
    def outcome(self) -> Outcome | None:
        if self.is_checkmate(): return Outcome.CHECKMATE
        if self.is_time_over(): return Outcome.TIME_OVER
        if self.is_stalemate(): return Outcome.STALEMATE
        if self.is_threefold(): return Outcome.THREEFOLD
        if self.is_fifty_moves(): return Outcome.FIFTY_MOVES
        if self.is_insufficient_material(): return Outcome.INSUFFICIENT
        return None

    def play(self, move: Move) -> None:
        self.control[self.color].add_increment()
        self.history.append(super().push(move))
        self.fullmoves += self.color ^ 1  # increment after black

        if self[move.to] or self[move.frm].type == chess.PAWN:
            self.halfmoves = 0
        else:
            self.halfmoves += 1

    def fen(self) -> str:
        return super().fen() + f" {self.fullmoves} {self.halfmoves}"

    def copy(self) -> "Game":
        return Game(self.fen(), [Time(*t) for t in self.control])

    def pgn(self) -> str:
        board = self.copy()
        consume(map(board.unpush, reversed(self.history)))

        moves = []
        for i, state in enumerate(self.history):
            if i == 0:
                full = board.fullmoves
                moves.append(f"{full}." if board.color else f"{full}...")
            elif board.color:
                moves.append(f"{board.fullmoves}.")

            assert state.move
            moves.append(f"{state.move.san(board)}")
            board.push(state.move)

        if board.outcome:
            outcome_str = ("0-1" if board.color else "1-0") if board.is_decisive() else "1/2-1/2"
            moves.append(outcome_str)

        return ' '.join(moves)

    def tick(self, dt_ms: int) -> None:
        self.control[self.color].tick(dt_ms)

    def __iter__(self) -> Iterator[tuple[Square, Piece]]:
        yield from ((Square(sq), p) for sq, p in super().__iter__())
