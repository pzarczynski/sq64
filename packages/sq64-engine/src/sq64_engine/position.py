from typing import NamedTuple

from sq64_chess import Chessboard, Move, Piece, PieceType, Transition

from .tables import piece_value_at


class PosTransition(NamedTuple):
    trans: Transition
    score: int


class Position(Chessboard):
    """Represents a chess position with an evaluation score."""
    _score: int

    def __init__(self, fen: str | None = None) -> None:
        super().__init__(fen)
        self._score = self.evaluate()

    def evaluate(self) -> int:
        """Evaluates the position by summing the values of all pieces on the board, adjusted for their positions."""
        return sum(piece_value_at(p, sq) for sq, p in self)

    @property
    def relscore(self) -> int:
        """Returns the evaluation score from the perspective of the side to move."""
        return self._score if self.color else -self._score

    def _value(self, move: Move | None) -> int:
        if not move:
            return 0

        frm, to, promo = move
        p = self[frm]
        score = -piece_value_at(p, frm)

        cap_sq = (
            to if not self.is_en_passant(move) else (to - 16 if p.color else to + 16)
        )
        score -= piece_value_at(self[cap_sq], cap_sq)

        if self.is_castling(move):
            rook_frm, rook_to = (frm + 3, frm + 1) if to > frm else (frm - 4, frm - 1)
            rook = Piece.make(PieceType.ROOK, self.color)
            score += piece_value_at(rook, rook_to) - piece_value_at(rook, rook_frm)

        if promo:
            p = Piece.make(promo, p.color)

        score += piece_value_at(p, to)
        return score

    def relvalue(self, move: Move) -> int:
        """Returns the change in evaluation score resulting from making the given move, from the perspective of the side to move."""
        return self._value(move) if self.color else -self._value(move)

    def play(self, move: Move | None = None) -> PosTransition:
        """Plays a move on the board, updating the position and evaluation score accordingly, and returns the transition state."""
        old_score = self._score
        self._score += self._value(move)
        return PosTransition(super().push(move), old_score)

    def unplay(self, state: PosTransition) -> None:
        """Reverts a move on the board, restoring the previous position and evaluation score from the given transition state."""
        super().unpush(state.trans)
        self._score = state.score
