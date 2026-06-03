from abc import ABC, abstractmethod

from sq64 import chess
from sq64.chess import Move, Square
from sq64.game import Game, Movetime
from sq64.uci import UCI


class Player(ABC):
    @abstractmethod
    def begin(self, game: Game) -> None: ...
    @abstractmethod
    def reset(self) -> None: ...
    @abstractmethod
    def quit(self) -> None: ...
    @abstractmethod
    def update_sq(self, sq: Square) -> None: ...
    @abstractmethod
    def update_promo(self, promo: chess.PieceType) -> None: ...
    @abstractmethod
    def getmove(self) -> Move | None: ...
    @property
    @abstractmethod
    def wants_promo(self) -> bool: ...
    @property
    @abstractmethod
    def selected_sq(self) -> Square | None: ...


class Human(Player):
    _move: Move | None
    _wants_promo: bool
    _selected_sq: Square | None
    _game: Game | None

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._game = None
        self._clear()

    def _clear(self) -> None:
        self._selected_sq = None
        self._move = None
        self._wants_promo = False

    def update_sq(self, sq: Square) -> None:
        if self._game:
            piece = self._game[sq]
            if self._selected_sq is not None and (not piece or piece.color != self._game.color):
                self._move = Move(self._selected_sq, sq)
                self._wants_promo = self._game[self._selected_sq].can_promote(sq)
            else:
                self._selected_sq = sq

    def update_promo(self, promo: chess.PieceType) -> None:
        if self._move:
            self._wants_promo = False
            self._move = Move(self._move.frm, self._move.to, promo)

    def begin(self, game: Game) -> None:
        self._game = game
        self._clear()

    @property
    def wants_promo(self) -> bool: return self._wants_promo
    @property
    def selected_sq(self) -> Square | None: return self._selected_sq

    def getmove(self) -> Move | None:
        return self._move if not self._wants_promo else None

    # irrelevant abstract methods
    def quit(self) -> None: pass


class Computer(Player):
    _movetime: Movetime
    _uci: UCI

    def __init__(self, path: str, response_speed: Movetime) -> None:
        self._movetime = response_speed
        self._uci = UCI(path)

    def quit(self) -> None: self._uci.quit()
    def reset(self) -> None: self._uci.newgame()

    def begin(self, game: Game) -> None:
        if not self._uci.thinking:
            time, inc = game.control[game.color]
            movetime = self._movetime(time, inc)
            self._uci.go(game.fen(), movetime=movetime)

    def getmove(self) -> Move | None:
        return Move.parse(self._uci.bestmove) if self._uci.bestmove else None

    @property
    def wants_promo(self) -> bool: return False

    # irrelevant abstract methods
    def update_sq(self, sq: Square) -> None: pass
    def update_promo(self, promo: chess.PieceType) -> None: pass
    @property
    def selected_sq(self) -> Square | None: return None
