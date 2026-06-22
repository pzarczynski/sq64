from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto

from . import Chessboard, Color, Move, PieceType, Transition
from .types import color_name


@dataclass(slots=True)
class Time:
    """Represents a player's remaining time and increment in miliseconds."""
    _time_ms: int
    _incr_ms: int

    @classmethod
    def natural(cls, minutes: int, incr: int) -> "Time":
        """a natural way to specify time control (minutes + increment in seconds)"""
        return cls(minutes * 60000, incr * 1000)  # to ms

    @property
    def minutes(self) -> int: return self._time_ms // 60000
    @property
    def seconds(self) -> int: return (self._time_ms // 1000) % 60
    @property
    def increment(self) -> int: return self._incr_ms // 1000

    def tick(self, dt_ms: int) -> None:
        self._time_ms = max(0, self._time_ms - dt_ms)

    def add_increment(self) -> None:
        self._time_ms += self._incr_ms

    def is_over(self) -> bool:
        return self._time_ms <= 0

    def astuple(self) -> tuple[int, int]:
        return (self.minutes, self.seconds)

    def __str__(self) -> str: return f"{self.minutes:02d}:{self.seconds:02d}"
    def __iter__(self) -> Iterator[int]: return iter((self._time_ms, self._incr_ms))


class Tempo(Enum):
    """Represents common time controls for chess games."""
    BULLET = auto()
    BLITZ  = auto()
    RAPID  = auto()

    def __call__(self) -> Time:
        match self:
            case Tempo.BULLET: return Time.natural( 1, 0)
            case Tempo.BLITZ:  return Time.natural( 3, 2)
            case Tempo.RAPID:  return Time.natural(10, 5)

    def __str__(self) -> str:
        t = self()
        return f"{t.minutes}\" + {t.increment}'"


class Movetime(Enum):
    """Represents different time management strategies for chess engines."""
    FAST   = auto()
    NORMAL = auto()
    SLOW   = auto()

    def __call__(self, time: int, inc: int) -> int:
        match self:
            case Movetime.FAST:   return int(min(time / 80 + inc * 0.5, time / 4))
            case Movetime.NORMAL: return int(min(time / 40 + inc * 0.7, time / 2))
            case Movetime.SLOW:   return int(min(time / 30 + inc * 0.9, time * 0.9))


class Outcome(Enum):
    """Represents the possible outcomes of a chess game."""
    CHECKMATE = auto()
    TIME_OVER = auto()

    STALEMATE = auto()
    THREEFOLD = auto()
    FIFTY_MOVES = auto()
    INSUFFICIENT = auto()

    def pretty(self, enemy: Color) -> str:
        enemy_str = color_name(enemy).capitalize()
        match self:
            case Outcome.CHECKMATE: return f"{enemy_str} wins by checkmate"
            case Outcome.TIME_OVER: return f"{enemy_str} wins on time"
            case Outcome.STALEMATE: return "Draw by stalemate"
            case Outcome.THREEFOLD: return "Draw by threefold repetition"
            case Outcome.FIFTY_MOVES: return "Draw by fifty-move rule"
            case Outcome.INSUFFICIENT: return "Draw by insufficient material"


class Game(Chessboard):
    """Represents a chess game, including the current board state, move history, and time control."""
    fullmoves: int
    halfmoves: int
    history: list[Transition]
    control: tuple[Time, Time]

    def __init__(self, fen: str, control: tuple[Time, Time]) -> None:
        super().__init__(fen)
        *_, fn, hc = fen.split()
        self.fullmoves = int(fn)
        self.halfmoves = int(hc)
        self.history = []
        self.control = control

    def is_insufficient_material(self) -> bool:
        pieces = [p for _, p in self]
        if len(pieces) == 2: return True  # only kings
        return len(pieces) == 3 and any(p.type in (PieceType.BISHOP, PieceType.KNIGHT) for p in pieces)

    def is_stalemate(self) -> bool: return not self.is_check() and not self.legal_moves()
    def is_checkmate(self) -> bool: return self.is_check() and not self.legal_moves()
    def is_threefold(self) -> bool: return sum(s.hash == self._hash for s in self.history) >= 2
    def is_time_over(self) -> bool: return self.control[self.color].is_over()
    def is_fifty_moves(self) -> bool: return self.halfmoves >= 100

    def is_decisive(self) -> bool:
        """Returns True if the game has a decisive outcome (checkmate or time over)."""
        return self.is_checkmate() or self.is_time_over()

    def is_draw(self) -> bool:
        return (self.is_stalemate() or self.is_fifty_moves() or
                self.is_threefold() or self.is_insufficient_material())

    def is_game_over(self) -> bool: return self.is_decisive() or self.is_draw()

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
        """Plays a move on the board, updating the game state and time control accordingly."""
        self.control[self.color].add_increment()
        self.history.append(super().push(move))
        self.fullmoves += self.color ^ 1  # increment after black

        if self[move.to] or self[move.frm].type == PieceType.PAWN:
            self.halfmoves = 0
        else:
            self.halfmoves += 1

    def fen(self) -> str:
        return super().fen() + f" {self.fullmoves} {self.halfmoves}"

    def copy(self) -> "Game":
        return Game(self.fen(), (Time(*self.control[0]), Time(*self.control[1])))

    def pgn(self) -> str:
        """Generates a PGN string representing the game history."""
        board = self.copy()
        _ = any(map(board.unpush, reversed(self.history)))

        def pgn_gen() -> Iterator[str]:
            for i, state in enumerate(self.history):
                if i == 0:
                    full = board.fullmoves
                    yield f"{full}." if board.color else f"{full}..."
                elif board.color:
                    yield f"{board.fullmoves}."

                yield f"{board.san(state.move)}" if state.move else "null"
                _ = board.push(state.move)

            if board.outcome:
                yield ("0-1" if board.color else "1-0") if board.is_decisive() else "1/2-1/2"

        return " ".join(pgn_gen())

    def tick(self, dt_ms: int) -> None:
        """Advances the game clock by the given number of milliseconds."""
        self.control[self.color].tick(dt_ms)
