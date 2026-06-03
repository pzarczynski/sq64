import logging
from collections import namedtuple
from collections.abc import Iterator
from enum import IntEnum
from threading import Event
from time import perf_counter

from sq64.chess import (
    COLORS,
    PIECES,
    ROOK,
    VALID_SQUARES,
    Board,
    Move,
    Piece,
    SquareInt,
    State,
    sq_mirror,
)

PST_PAWN = (
       0,   0,   0,   0,   0,   0,   0,   0,   0,    0,    0,    0,    0,    0,    0,    0,
      78,  83,  86,  73, 102,  82,  85,  90,   0,    0,    0,    0,    0,    0,    0,    0,
       7,  29,  21,  44,  40,  31,  44,   7,   0,    0,    0,    0,    0,    0,    0,    0,
     -17,  16,  -2,  15,  14,   0,  15, -13,   0,    0,    0,    0,    0,    0,    0,    0,
     -26,   3,  10,   9,   6,   1,   0, -23,   0,    0,    0,    0,    0,    0,    0,    0,
     -22,   9,   5, -11, -10,  -2,   3, -19,   0,    0,    0,    0,    0,    0,    0,    0,
     -31,   8,  -7, -37, -36, -14,   3, -31,   0,    0,    0,    0,    0,    0,    0,    0,
       0,   0,   0,   0,   0,   0,   0,   0,   0,    0,    0,    0,    0,    0,    0,    0,
)
PST_KNIGHT = (
     -66,  -53,  -75,  -75,  -10,  -55,  -58,  -70,    0,    0,    0,    0,    0,    0,    0,    0,
      -3,   -6,  100,  -36,    4,   62,   -4,  -14,    0,    0,    0,    0,    0,    0,    0,    0,
      10,   67,    1,   74,   73,   27,   62,   -2,    0,    0,    0,    0,    0,    0,    0,    0,
      24,   24,   45,   37,   33,   41,   25,   17,    0,    0,    0,    0,    0,    0,    0,    0,
      -1,    5,   31,   21,   22,   35,    2,    0,    0,    0,    0,    0,    0,    0,    0,    0,
     -18,   10,   13,   22,   18,   15,   11,  -14,    0,    0,    0,    0,    0,    0,    0,    0,
     -23,  -15,    2,    0,    2,    0,  -23,  -20,    0,    0,    0,    0,    0,    0,    0,    0,
     -74,  -23,  -26,  -24,  -19,  -35,  -22,  -69,    0,    0,    0,    0,    0,    0,    0,    0,
)

PST_BISHOP = (
     -59,  -78,  -82,  -76,  -23, -107,  -37,  -50,    0,    0,    0,    0,    0,    0,    0,    0,
     -11,   20,   35,  -42,  -39,   31,    2,  -22,    0,    0,    0,    0,    0,    0,    0,    0,
      -9,   39,  -32,   41,   52,  -10,   28,  -14,    0,    0,    0,    0,    0,    0,    0,    0,
      25,   17,   20,   34,   26,   25,   15,   10,    0,    0,    0,    0,    0,    0,    0,    0,
      13,   10,   17,   23,   17,   16,    0,    7,    0,    0,    0,    0,    0,    0,    0,    0,
      14,   25,   24,   15,    8,   25,   20,   15,    0,    0,    0,    0,    0,    0,    0,    0,
      19,   20,   11,    6,    7,    6,   20,   16,    0,    0,    0,    0,    0,    0,    0,    0,
      -7,    2,  -15,  -12,  -14,  -15,  -10,  -10,    0,    0,    0,    0,    0,    0,    0,    0,
)

PST_ROOK = (
      35,   29,   33,    4,   37,   33,   56,   50,    0,    0,    0,    0,    0,    0,    0,    0,
      55,   29,   56,   67,   55,   62,   34,   60,    0,    0,    0,    0,    0,    0,    0,    0,
      19,   35,   28,   33,   45,   27,   25,   15,    0,    0,    0,    0,    0,    0,    0,    0,
       0,    5,   16,   13,   18,   -4,   -9,   -6,    0,    0,    0,    0,    0,    0,    0,    0,
     -28,  -35,  -16,  -21,  -13,  -29,  -46,  -30,    0,    0,    0,    0,    0,    0,    0,    0,
     -42,  -28,  -42,  -25,  -25,  -35,  -26,  -46,    0,    0,    0,    0,    0,    0,    0,    0,
     -53,  -38,  -31,  -26,  -29,  -43,  -44,  -53,    0,    0,    0,    0,    0,    0,    0,    0,
     -30,  -24,  -18,    5,   -2,  -18,  -31,  -32,    0,    0,    0,    0,    0,    0,    0,    0,
)

PST_QUEEN = (
       6,    1,   -8, -104,   69,   24,   88,   26,    0,    0,    0,    0,    0,    0,    0,    0,
      14,   32,   60,  -10,   20,   76,   57,   24,    0,    0,    0,    0,    0,    0,    0,    0,
      -2,   43,   32,   60,   72,   63,   43,    2,    0,    0,    0,    0,    0,    0,    0,    0,
       1,  -16,   22,   17,   25,   20,  -13,   -6,    0,    0,    0,    0,    0,    0,    0,    0,
     -14,  -15,   -2,   -5,   -1,  -10,  -20,  -22,    0,    0,    0,    0,    0,    0,    0,    0,
     -30,   -6,  -13,  -11,  -16,  -11,  -16,  -27,    0,    0,    0,    0,    0,    0,    0,    0,
     -36,  -18,    0,  -19,  -15,  -15,  -21,  -38,    0,    0,    0,    0,    0,    0,    0,    0,
     -39,  -30,  -31,  -13,  -31,  -36,  -34,  -42,    0,    0,    0,    0,    0,    0,    0,    0,
)

PST_KING = (
       4,   54,   47,  -99,  -99,   60,   83,  -62,    0,    0,    0,    0,    0,    0,    0,    0,
     -32,   10,   55,   56,   56,   55,   10,    3,    0,    0,    0,    0,    0,    0,    0,    0,
     -62,   12,  -57,   44,  -67,   28,   37,  -31,    0,    0,    0,    0,    0,    0,    0,    0,
     -55,   50,   11,   -4,  -19,   13,    0,  -49,    0,    0,    0,    0,    0,    0,    0,    0,
     -55,  -43,  -52,  -28,  -51,  -47,   -8,  -50,    0,    0,    0,    0,    0,    0,    0,    0,
     -47,  -42,  -43,  -79,  -64,  -32,  -29,  -32,    0,    0,    0,    0,    0,    0,    0,    0,
      -4,    3,  -14,  -50,  -57,  -18,   13,    4,    0,    0,    0,    0,    0,    0,    0,    0,
      17,   30,   -3,  -14,    6,   -1,   40,   18,    0,    0,    0,    0,    0,    0,    0,    0,
)

PST_TABLES = ((), PST_PAWN, PST_KNIGHT, PST_BISHOP, PST_ROOK, PST_QUEEN, PST_KING)
PIECE_VALUES = (0, 100, 280, 320, 479, 929, 60000)

PIECE_POSVAL = [[0] * 16 for _ in range(128)]
for c in COLORS:
    for p in PIECES[c][1:]:
        for sq in VALID_SQUARES:
            val = PIECE_VALUES[p.type] + PST_TABLES[p.type][sq_mirror(sq) if c else sq]
            PIECE_POSVAL[sq][p] = val if c else -val

def piece_posval(piece: Piece, sq: SquareInt) -> int:
    return PIECE_POSVAL[sq][piece] if piece else 0

class Position(Board):
    abs_score: int

    def from_fen(self, fen: str) -> None:
        super().from_fen(fen)
        self.abs_score = self.evaluate()

    def evaluate(self) -> int:
        return sum(piece_posval(p, sq) for sq, p in self)

    @property
    def score(self) -> int:
        return self.abs_score if self.color else -self.abs_score

    def abs_value(self, move: Move) -> int:
        frm, to, promo = move.astuple()
        p = self[frm]
        score = -piece_posval(p, frm)

        cap_sq = to if not move.is_en_passant(self) else (to - 16 if p.color else to + 16)
        score -= piece_posval(self[cap_sq], cap_sq)

        if move.is_castling(self):
            rook_frm, rook_to = (frm + 3, frm + 1) if to > frm else (frm - 4, frm - 1)
            rook = Piece(self.color, ROOK)
            score += piece_posval(rook, rook_to) - piece_posval(rook, rook_frm)

        if promo:
            p = Piece(p.color, promo)

        score += piece_posval(p, to)
        return score

    def value(self, move: Move) -> int:
        return self.abs_value(move) if self.color else -self.abs_value(move)

    def push(self, move: Move | None = None) -> State:
        old_score = self.abs_score

        if not move:
            state = super().push(move)
            state.abs_score = old_score
            return state

        self.abs_score += self.abs_value(move)
        state = super().push(move)
        state.abs_score = old_score
        return state

    def unpush(self, state: State) -> None:
        super().unpush(state)
        self.abs_score = state.abs_score

    def __hash__(self) -> int:
        return self.hash

MATE_VALUE = 32000
MATE_BOUND = 30000

Bound = IntEnum("Bound", "EXACT LOWER UPPER")
Entry = namedtuple("Entry", "depth score flag move")
Info = namedtuple("Info", "depth score")
SearchResult = namedtuple("SearchResult", "score pv")

class AbortSearch(Exception): ...

class Engine:
    tt: dict[int, Entry]
    killers: list[Move | None]
    nodes: int
    stop: Event

    def __init__(self) -> None:
        self.tt = {}
        self.killers = [None] * 256

    def clear(self) -> None:
        self.tt.clear()

    def should_abort(self) -> None:
        if self.nodes & 127 == 0 and self.stop.is_set():
            raise AbortSearch()

    def order_moves(
        self, moves: Iterator[Move], pos: Position, ply: int, tt_move: Move | None = None
    ) -> list[Move]:
        def move_score(m: Move) -> int:
            if m == tt_move:
                return 10_000_000

            if m.is_capture(pos) or m.promotion:
                return 1_000_000 + pos.value(m)

            if m == self.killers[ply]:
                return 900_000

            return pos.value(m)

        return sorted(moves, key=move_score, reverse=True)

    def quiescence(self, pos: Position, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        self.should_abort()

        stand_pat = pos.score

        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        moves = self.order_moves(pos.gen_moves(qs=True), pos, ply)
        for move in moves:
            if stand_pat + pos.value(move) + 200 < alpha:
                continue

            state = pos.push(move)

            if pos.is_check(side=pos.color ^ 1):
                pos.unpush(state)
                continue

            score = -self.quiescence(pos, -beta, -alpha, ply + 1)
            pos.unpush(state)

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def negamax(
        self,
        pos: Position,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        can_null: bool = True
    ) -> int:
        self.nodes += 1
        self.should_abort()

        if depth <= 0:
            return self.quiescence(pos, alpha, beta, ply)

        alpha = max(alpha, -MATE_VALUE + ply)
        beta  = min(beta,  +MATE_VALUE - ply - 1)
        if alpha >= beta:
            return alpha

        is_check = pos.is_check()

        if is_check:
            depth += 1

        tt_entry = self.tt.get(pos.hash)
        tt_move = None
        if tt_entry is not None:
            tt_move = tt_entry.move
            if tt_entry.depth >= depth:
                tt_score = tt_entry.score
                if   tt_score >= +MATE_BOUND: tt_score -= ply
                elif tt_score <= -MATE_BOUND: tt_score += ply

                if (tt_entry.flag == Bound.EXACT) or \
                   (tt_entry.flag == Bound.LOWER and tt_score >= beta) or \
                   (tt_entry.flag == Bound.UPPER and tt_score <= alpha):
                    return tt_score

        if can_null and depth >= 3 and not is_check:  # Null Move Pruning
            state = pos.push()
            null_score = -self.negamax(pos, depth-3, -beta, -beta+1, ply+1, can_null=False)
            pos.unpush(state)
            if null_score >= beta:
                return beta

        best = -MATE_VALUE * 2
        best_move = None
        orig_alpha = alpha
        legal_moves = 0

        moves = self.order_moves(pos.gen_moves(), pos, ply, tt_move)

        for move in moves:
            state = pos.push(move)

            if pos.is_check(side=pos.color ^ 1):
                pos.unpush(state)
                continue

            legal_moves += 1
            is_quiet = not move.is_capture(pos) and not move.promotion

            if legal_moves == 1:  # PVS
                score = -self.negamax(pos, depth - 1, -beta, -alpha, ply + 1, True)
            else:
                reduction = 0
                if depth >= 3 and legal_moves >= 4 and is_quiet and not is_check:  # LMR
                    reduction = 1

                score = -self.negamax(pos, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1, True)

                if alpha < score < beta:
                    score = -self.negamax(pos, depth - 1, -beta, -alpha, ply + 1, True)

            pos.unpush(state)

            if score > best:
                best = score
                best_move = move

            if score > alpha:
                alpha = score

            if alpha >= beta:
                if is_quiet: self.killers[ply] = move
                break

        if legal_moves == 0:
            return -MATE_VALUE + ply if is_check else 0

        store_score = best
        if   store_score >= +MATE_BOUND: store_score += ply
        elif store_score <= -MATE_BOUND: store_score -= ply

        flag = Bound.UPPER if best <= orig_alpha else (Bound.LOWER if best >= beta else Bound.EXACT)
        self.tt[pos.hash] = Entry(depth, store_score, flag, best_move)

        return best

    def pv(
        self, pos: Position, max_depth: int = 20, seen: set | None = None
    ) -> list[Move]:
        if max_depth <= 0: return []
        seen = seen or set()

        entry = self.tt.get(pos.hash)
        if not entry or not (move := entry.move): return []

        line = [move]
        state = pos.push(move)

        if pos.hash not in seen:
            seen.add(pos.hash)
            line.extend(self.pv(pos, max_depth - 1, seen))

        pos.unpush(state)
        return line

    def go(
        self, pos: Position, stop: Event
    ) -> Iterator[tuple[int, list[Move], int, float]]:
        pos_cp = pos.copy()
        self.nodes = 0
        self.killers = [None] * 256
        self.stop = stop

        t0 = perf_counter()
        score = 0

        for depth in range(1, 100):
            try:
                score = self.negamax(pos_cp, depth, -MATE_VALUE*2, +MATE_VALUE*2, ply=0)
                dt = perf_counter() - t0
                logging.debug(f"depth {depth} score {score} nps {int(self.nodes / dt)}")
                yield score, self.pv(pos_cp, max_depth=depth), self.nodes, dt

            except AbortSearch:
                logging.debug("search aborted after %.2f seconds", perf_counter() - t0)
                return
