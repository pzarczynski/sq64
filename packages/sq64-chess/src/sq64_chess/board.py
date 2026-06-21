import random
from collections.abc import Container, Iterator, Sequence
from functools import reduce
from operator import xor  # pyright: ignore[reportUnknownVariableType]
from typing import NamedTuple, Self

from .constants import BLACK, DELTAS, PIECES, PROMOS, SPOILERS, SQUARES, WHITE, E, N, S, W
from .types import CastlRights, Color, Move, Piece, PieceType, Square


class Zobrist:
    _rng: random.Random
    _color_hash: int
    _sq_hash: list[int]
    _castl_hash: list[int]
    _piece_hash: list[list[int]]

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)  # noqa: S311
        self._color_hash = self.rand64()
        self._sq_hash    = [self.rand64() for _ in range(128)]
        self._castl_hash = [self.rand64() for _ in range(16)]
        self._piece_hash = [[self.rand64() for _ in range(16)] for _ in range(128)]

    def rand64(self) -> int:
        return self._rng.getrandbits(64)

    def board_hash(self, board: "Board") -> int:
        return (
            self.color_hash() ^ self.castl_hash(board.castling_rights) ^
            reduce(xor, (self.piece_hash(p, sq) for sq, p in board)) ^  # pyright: ignore[reportUnknownArgumentType]
            (self.square_hash(board.ep_square) if board.ep_square else 0)
        )

    def color_hash(self) -> int:
        return self._color_hash

    def square_hash(self, sq: Square) -> int:
        return self._sq_hash[sq]

    def castl_hash(self, cr: CastlRights) -> int:
        return self._castl_hash[cr]

    def piece_hash(self, piece: Piece, sq: Square) -> int:
        return self._piece_hash[sq][piece]


class Transition(NamedTuple):
    move: Move | None
    ep_sq: Square | None
    cr: CastlRights
    hash: int
    cap: Piece = Piece.NONE
    is_ep: bool = False


class Board:
    STARTING_FEN: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    _hasher: Zobrist = Zobrist()

    _buf: bytearray
    _king_sq: list[Square]
    _ep_sq: Square | None
    _cr: CastlRights
    _color: Color
    _hash: int

    @property
    def color(self) -> Color: return self._color
    @property
    def ep_square(self) -> Square | None: return self._ep_sq
    @property
    def castling_rights(self) -> CastlRights: return self._cr

    def __init__(self, fen: str | None = None) -> None:
        fen = fen or self.STARTING_FEN

        parts = fen.strip().split()
        self._color = WHITE if parts[1] == "w" else BLACK
        self._cr = CastlRights.frm_fen(parts[2])
        self._ep_sq = Square.frm_str(parts[3]) if parts[3] != "-" else None

        self._buf = bytearray(128)
        idx = 0
        for c in parts[0]:
            if c == "/":
                continue
            if c.isdigit():
                idx += int(c)
            else:
                sq = Square.frm_idx(idx).mirror
                self[sq] = Piece.frm_char(c)
                idx += 1

        self._king_sq = [0, 0]  # pyright: ignore[reportAttributeAccessIssue]
        for sq, p in self.pieces_by_type(PieceType.KING):
            self._king_sq[p.color] = sq

        self._hash = self._hasher.board_hash(self)

    def king_square(self, color: Color) -> Square:
        return self._king_sq[color]

    def _is_attacked_by(
        self,
        sq: Square,
        deltas: Sequence[int],
        sentinels: Container["Piece"],
        *,
        stepper: bool = False,
    ) -> bool:
        for d in deltas:
            cur = sq + d
            while cur:
                val = self[cur]
                if val or stepper:
                    if val in sentinels:
                        return True
                    break
                cur += d
        return False

    def is_attacked(self, sq: Square, by: Color) -> bool:
        pawn, knight, bishop, rook, queen, king = PIECES[by]
        pawn_dir = S if by else N

        p_sq1 = sq + pawn_dir + W
        if p_sq1 and self[p_sq1] == pawn: return True
        p_sq2 = sq + pawn_dir + E
        if p_sq2 and self[p_sq2] == pawn: return True

        for p in (knight, king):
            if self._is_attacked_by(sq, DELTAS[p.type], (p,), stepper=True):
                return True

        if self._is_attacked_by(sq, DELTAS[rook.type], (rook, queen)):
            return True

        return self._is_attacked_by(sq, DELTAS[bishop.type], (bishop, queen))

    def is_check(self, side: Color | None = None) -> bool:
        side = self._color if side is None else side
        return self.is_attacked(self._king_sq[side], by=not side)

    def is_check_after(self, move: Move) -> bool:
        state = self.push(move)
        check = self.is_check(not self._color)
        self.unpush(state)
        return check

    def is_checkmate_after(self, move: "Move") -> bool:
        state = self.push(move)
        mate = self.is_check(not self._color) and not self.legal_moves()
        self.unpush(state)
        return mate

    def is_legal(self, move: Move) -> bool:
        state = self.push(move)
        check = self.is_attacked(self._king_sq[self._color^1], self._color)
        self.unpush(state)
        return not check

    def is_en_passant(self, move: Move) -> bool:
        return self[move.frm].type == PieceType.PAWN and move.to == self._ep_sq

    def is_capture(self, move: Move) -> bool:
        return bool(self[move.to]) or self.is_en_passant(move)

    def is_castling(self, move: Move) -> bool:
        return self[move.frm].type == PieceType.KING and move.delta == 2

    def gen_pawn_moves(self, frm: Square, *, qs: bool = False) -> Iterator[Move]:
        pawn_dir, promo_rank = (N, 7) if self._color else (S, 0)
        start_rank = promo_rank ^ 0x6

        one = frm + pawn_dir
        if one and not self[one]:
            if one.rank == promo_rank:
                yield from (Move(frm, one, pt) for pt in PROMOS)
            elif not qs:
                yield Move(frm, one)
            two = frm + 2 * pawn_dir
            if not qs and frm.rank == start_rank and not self[two]:
                yield Move(frm, two)

        for offset in (pawn_dir + W, pawn_dir + E):
            to = frm + offset
            if to:
                tgt = self[to]
                if (tgt and tgt.color != self._color) or to == self._ep_sq:
                    if to.rank == promo_rank:
                        yield from (Move(frm, to, pt) for pt in PROMOS)
                    else:
                        yield Move(frm, to)

    def gen_castling_moves(self, *, qs: bool = False) -> Iterator[Move]:
        if qs or not self._cr or self.is_check():
            return

        cr  = self._cr
        r   = CastlRights.by(self._color)
        frm = self.king_square(self._color)

        ks_clear = cr & r[0] and self[frm + 1] == self[frm + 2] == 0
        if ks_clear and not self.is_attacked(frm + 1, by=not self._color):
            yield Move(frm, frm + 2)

        qs_clear = cr & r[1] and self[frm - 1] == self[frm - 2] == self[frm - 3] == 0
        if qs_clear and not self.is_attacked(frm - 1, by=not self._color):
            yield Move(frm, frm - 2)

    def gen_moves(self, *, qs: bool = False) -> Iterator[Move]:
        for frm, p in self.pieces_by_color(self._color):
            pt = p.type

            if pt == PieceType.PAWN:
                yield from self.gen_pawn_moves(frm, qs=qs)
                continue

            for d in DELTAS[pt]:
                to = frm + d
                while to:
                    tgt = self[to]
                    if not tgt:
                        if not qs:
                            yield Move(frm, to)
                    else:
                        if tgt.color != self._color:
                            yield Move(frm, to)
                        break
                    if pt in (PieceType.KNIGHT, PieceType.KING):
                        break
                    to += d

        yield from self.gen_castling_moves(qs=qs)

    def legal_moves(self) -> list[Move]:
        return [m for m in self.gen_moves() if self.is_legal(m)]

    def push(self, move: Move | None = None) -> Transition:
        old_hash = self._hash
        cr = self._cr
        ep = self._ep_sq
        self._ep_sq = None

        self._hash ^= self._hasher.color_hash()

        if ep is not None:
            self._hash ^= self._hasher.square_hash(ep)

        if move is None:
            self._color = not self._color
            return Transition(move, ep, cr, old_hash)

        frm, to, promo = move

        p = self[frm]
        self[frm] = Piece.NONE
        self._hash ^= self._hasher.piece_hash(p, frm)

        cap = self[to]
        is_ep = False
        pt = p.type

        cap_sq = to

        if pt == PieceType.PAWN and to == ep:
            is_ep = True
            cap_sq = to - 16 if p.color else to + 16
            cap = self[cap_sq]
            self[cap_sq] = Piece.NONE

        elif pt == PieceType.KING:
            self._king_sq[self._color] = move.to
            if move.delta == 2:
                rook_frm, rook_to = (frm + 3, frm + 1) if to > frm else (frm - 4, frm - 1)
                rook = Piece.make(PieceType.ROOK, p.color)
                self[rook_to]  = self[rook_frm]
                self[rook_frm] = Piece.NONE
                self._hash ^= self._hasher.piece_hash(rook, rook_frm) ^ self._hasher.piece_hash(rook, rook_to)

        self._hash ^= self._hasher.piece_hash(cap, cap_sq)

        if promo:
            p = Piece.make(promo, p.color)

        self[to]  = p
        self._hash ^= self._hasher.piece_hash(p, to)

        if pt == PieceType.PAWN and move.delta == 32:
            self._ep_sq = move.between
            self._hash ^= self._hasher.square_hash(self._ep_sq)

        self._cr &= SPOILERS[to]
        self._cr &= SPOILERS[frm]
        self._hash ^= self._hasher.castl_hash(cr) ^ self._hasher.castl_hash(self._cr)
        self._color = not self._color
        return Transition(move, ep, cr, old_hash, cap, is_ep)

    def push_uci(self, s: str) -> Transition:
        return self.push(Move.parse(s))

    def unpush(self, t: Transition) -> None:
        self._color = not self._color
        self._hash = t.hash
        self._ep_sq = t.ep_sq

        move = t.move
        if move is None:
            return

        frm, to, promo = move

        self._cr = t.cr
        p = Piece.make(PieceType.PAWN, self._color) if promo else self[to]
        self[frm] = p

        if t.is_ep:
            self[to] = Piece.NONE
            self[to - 16 if p.color else to + 16] = t.cap
        else:
            self[to] = t.cap

        if p.type == PieceType.KING:
            self._king_sq[self._color] = frm
            if move.delta == 2:
                rook_frm, rook_to = (frm + 3, frm + 1) if to > frm else (frm - 4, frm - 1)
                self[rook_frm] = self[rook_to]
                self[rook_to]  = Piece.NONE

    def pieces_by_color(self, c: Color) -> Iterator[tuple[Square, Piece]]:
        for sq in SQUARES:
            v = self._buf[sq]
            if v and (v & 1) == c:
                yield sq, Piece(v)

    def pieces_by_type(self, pt: PieceType) -> Iterator[tuple[Square, Piece]]:
        for sq in SQUARES:
            v = self._buf[sq]
            if v and (v >> 1) == pt:
                yield sq, Piece(v)

    def fen(self) -> str:
        def row(r: int) -> str:
            s = ""
            empty_count = 0
            for f in range(8):
                sq = Square.make(f, r)
                val = self._buf[sq]
                if not val:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        s += str(empty_count)
                        empty_count = 0
                    s += str(Piece(val))
            if empty_count > 0:
                s += str(empty_count)
            return s

        board_fen = "/".join(row(r) for r in reversed(range(8)))
        color_fen = "w" if self._color == WHITE else "b"
        cr_fen = str(self._cr) if self._cr else "-"
        ep_fen = str(self._ep_sq) if self._ep_sq is not None else "-"
        return f"{board_fen} {color_fen} {cr_fen} {ep_fen} 0 0"

    def _disambiguate(self, move: "Move", p: Piece) -> str:
        if p.type == PieceType.PAWN:
            return ""

        to_same = [
            m for m in self.legal_moves()
            if m.to == move.to and m.frm != move.frm and self[m.frm] == p
        ]

        if not to_same:
            return ""

        same_file = any(m.frm.file == move.frm.file for m in to_same)
        same_rank = any(m.frm.rank == move.frm.rank for m in to_same)

        if not same_file:
            return str(move.frm)[0]
        if not same_rank:
            return str(move.frm)[1]
        return str(move.frm)

    def san(self, move: "Move") -> str:
        if self.is_castling(move):
            s = "O-O-O" if move.to < move.frm else "O-O"
        else:
            p = self[move.frm]
            s = "" if p.type == PieceType.PAWN else p.char.upper()

            s += self._disambiguate(move, p)

            if self.is_capture(move):
                if p.type == PieceType.PAWN:
                    s += str(move.frm)[0]
                s += "x"

            s += str(move.to)

            if move.promo:
                s += f"={move.promo.char.upper()}"

        if self.is_checkmate_after(move):
            s += "#"
        elif self.is_check_after(move):
            s += "+"

        return s

    def copy(self) -> Self: return type(self)(self.fen())

    def __hash__(self) -> int: return self._hash
    def __str__(self) -> str: return self.fen()
    def __getitem__(self, sq: Square) -> Piece: return Piece(self._buf[sq])
    def __setitem__(self, sq: Square, piece: Piece) -> None: self._buf[sq] = piece
    def __iter__(self) -> Iterator[tuple[Square, Piece]]:
        for sq in SQUARES:
            v = self._buf[sq]
            if v:
                yield sq, Piece(v)

    def perft(self, depth: int) -> int:
        if depth == 0: return 1
        nodes = 0
        side = self._color

        for move in self.gen_moves():
            state = self.push(move)

            if not self.is_check(side):
                nodes += self.perft(depth - 1) if depth > 1 else 1

            self.unpush(state)

        return nodes
