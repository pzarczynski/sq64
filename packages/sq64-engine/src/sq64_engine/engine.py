import logging
from collections.abc import Iterator
from enum import IntEnum
from threading import Event
from time import perf_counter
from typing import NamedTuple

from sq64_chess import Move

from sq64_engine.position import Position

MATE_VALUE = 32000
MATE_BOUND = 30000

class Bound(IntEnum):
    EXACT = 0
    LOWER = 1
    UPPER = 2

    def is_bound(self, score: int, alpha: int, beta: int) -> bool:
        if self == Bound.EXACT: return True
        if self == Bound.LOWER: return score >= beta
        if self == Bound.UPPER: return score <= alpha
        return False

class Entry(NamedTuple):
    depth: int
    score: int
    flag: Bound
    move: Move | None

class Info(NamedTuple):
    score: int
    pv: list[Move]
    nodes: int
    time: float

class AbortSearchError(Exception): ...

class Engine:
    tt: dict[int, Entry]
    killers: list[Move | None]
    nodes: int
    stop: Event

    def __init__(self) -> None:
        self.tt = {}
        self.killers = [None] * 256
        self.nodes = 0
        self.stop = Event()

    def clear(self) -> None:
        self.tt.clear()

    def should_abort(self) -> None:
        if self.nodes & 127 == 0 and self.stop.is_set():
            raise AbortSearchError()

    def order_moves(
        self,
        moves: Iterator[Move],
        pos: Position,
        ply: int,
        tt_move: Move | None = None,
    ) -> list[Move]:
        def move_score(m: Move) -> int:
            if m == tt_move:
                return 10_000_000

            if pos.is_capture(m) or m.promo:
                return 1_000_000 + pos.relvalue(m)

            if m == self.killers[ply]:
                return 900_000

            return pos.relvalue(m)

        return sorted(moves, key=move_score, reverse=True)

    def _qs(self, pos: Position, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        self.should_abort()

        stand_pat = pos.relscore

        if stand_pat >= beta: return beta
        if alpha < stand_pat: alpha = stand_pat

        moves = self.order_moves(pos.gen_moves(qs=True), pos, ply)
        for move in moves:
            if stand_pat + pos.relvalue(move) + 200 < alpha: continue
            state = pos.play(move)

            if pos.is_check(side=not pos.color):
                pos.unplay(state)
                continue

            score = -self._qs(pos, -beta, -alpha, ply + 1)
            pos.unplay(state)

            if score >= beta: return beta
            if score > alpha: alpha = score

        return alpha

    def _probe_tt(
        self, pos: Position, depth: int, alpha: int, beta: int, ply: int,
    ) -> tuple[int | None, Move | None]:
        entry = self.tt.get(hash(pos))
        if not entry: return None, None

        tt_move = entry.move
        if entry.depth >= depth:
            score = entry.score
            if   score >=  MATE_BOUND: score -= ply
            elif score <= -MATE_BOUND: score += ply

            if entry.flag.is_bound(score, alpha, beta):
                return score, tt_move

        return None, tt_move

    def _store_tt(self, pos: Position, depth: int, score: int, orig_alpha: int, beta: int, ply: int, move: Move | None) -> None:
        if score   >=  MATE_BOUND: score += ply
        elif score <= -MATE_BOUND: score -= ply

        flag = Bound.UPPER if score <= orig_alpha else (Bound.LOWER if score >= beta else Bound.EXACT)
        self.tt[hash(pos)] = Entry(depth, score, flag, move)

    def _try_nmp(
        self, pos: Position, depth: int, beta: int, ply: int, *, can_null: bool, is_check: bool,
    ) -> bool:
        if not can_null or depth < 3 or is_check:
            return False

        state = pos.play()
        score = -self.negamax(pos, depth - 3, -beta, -beta + 1, ply + 1, can_null=False)
        pos.unplay(state)
        return score >= beta

    def _score_move(self, pos: Position, move: Move, depth: int, alpha: int, beta: int, ply: int, legal_moves: int, is_check: bool) -> int:
        if legal_moves == 1:
            return -self.negamax(pos, depth - 1, -beta, -alpha, ply + 1, can_null=True)

        is_quiet = not pos.is_capture(move) and not move.promo
        reduction = 1 if (depth >= 3 and legal_moves >= 4 and is_quiet and not is_check) else 0

        score = -self.negamax(pos, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1, can_null=True)

        if alpha < score < beta:
            score = -self.negamax(pos, depth - 1, -beta, -alpha, ply + 1, can_null=True)

        return score

    def _search_moves(
        self, pos: Position, depth: int, alpha: int, beta: int, ply: int, tt_move: Move | None, *, is_check: bool,
    ) -> tuple[int, Move | None, int]:
        best = -MATE_VALUE * 2
        best_move = None
        legal_moves = 0

        for move in self.order_moves(pos.gen_moves(), pos, ply, tt_move):
            state = pos.play(move)

            if pos.is_check(side=not pos.color):
                pos.unplay(state)
                continue

            legal_moves += 1
            score = self._score_move(pos, move, depth, alpha, beta, ply, legal_moves, is_check)
            pos.unplay(state)

            if score > best:
                best = score
                best_move = move

            if score > alpha: alpha = score
            if alpha >= beta:
                if not pos.is_capture(move) and not move.promo:
                    self.killers[ply] = move
                break

        return best, best_move, legal_moves

    def negamax(
        self,
        pos: Position,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        *,
        can_null: bool = True,
    ) -> int:
        self.nodes += 1
        self.should_abort()

        # quiescence search
        if depth <= 0: return self._qs(pos, alpha, beta, ply)

        # mdp
        alpha = max(alpha, -MATE_VALUE + ply)
        beta  = min(beta,  +MATE_VALUE - ply - 1)
        if alpha >= beta: return alpha

        # check extension
        is_check = pos.is_check()
        if is_check: depth += 1

        # tt lookup
        tt_score, tt_move = self._probe_tt(pos, depth, alpha, beta, ply)
        if tt_score is not None: return tt_score

        # nmp
        if self._try_nmp(pos, depth, beta, ply, can_null=can_null, is_check=is_check):
            return beta

        # main search
        best, best_move, legal_moves = self._search_moves(
            pos, depth, alpha, beta, ply, tt_move, is_check=is_check,
        )

        if legal_moves == 0: return -MATE_VALUE + ply if is_check else 0
        self._store_tt(pos, depth, best, alpha, beta, ply, best_move)
        return best

    def pv(
        self, pos: Position, max_depth: int = 20, seen: set[int] | None = None,
    ) -> list[Move]:
        if max_depth <= 0: return []
        seen = seen or set()

        entry = self.tt.get(hash(pos))
        if not entry or not (move := entry.move): return []

        line = [move]
        state = pos.push(move)

        if hash(pos) not in seen:
            seen.add(hash(pos))
            line.extend(self.pv(pos, max_depth - 1, seen))

        pos.unpush(state)
        return line

    def go(self, pos: Position, stop: Event) -> Iterator[Info]:
        pos_cp = pos.copy()
        self.nodes = 0
        self.killers = [None] * 256
        self.stop = stop

        t0 = perf_counter()
        score = 0

        for depth in range(1, 100):
            try:
                score = self.negamax(
                    pos_cp, depth, -MATE_VALUE * 2, +MATE_VALUE * 2, ply=0,
                )
                dt = perf_counter() - t0
                logging.debug(f"depth {depth} score {score} nps {int(self.nodes / dt)}")
                yield Info(score, self.pv(pos_cp, max_depth=depth), self.nodes, dt)

            except AbortSearchError:
                logging.debug("search aborted after %.2f seconds", perf_counter() - t0)
                return
