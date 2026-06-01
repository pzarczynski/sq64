import logging
from collections import namedtuple
from collections.abc import Iterator
from enum import IntEnum
from threading import Event
from time import perf_counter

from sq64.core import Move
from sq64.position import Position

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

