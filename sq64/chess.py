import random
from collections.abc import Iterator
from dataclasses import dataclass
from functools import reduce
from itertools import count
from operator import or_, xor
from typing import Self

random.seed(0)
ZOBRIST_CASTLING = [random.getrandbits(64) for _ in range(16)]
ZOBRIST_PIECES   = [[random.getrandbits(64) for _ in range(16)] for _ in range(128)]
ZOBRIST_COLOR    = random.getrandbits(64)
ZOBRIST_EP       = [random.getrandbits(64) for _ in range(128)]

Color = int  # 0 = BLACK, 1 = WHITE
COLORS = (BLACK, WHITE) = range(2)
def color_name(c: Color) -> str: return "white" if c else "black"

SquareInt = int  # square in 0x88 representation
def sq_file(sq: SquareInt)   -> int: return sq & 7
def sq_rank(sq: SquareInt)   -> int: return sq >> 4
def sq_to_idx(sq: SquareInt) -> int: return sq & 7 | sq >> 4 << 3
def sq_to_str(sq: SquareInt) -> str: return f"{chr(sq_file(sq) + 97)}{sq_rank(sq) + 1}"
def sq_valid(sq: SquareInt)  -> bool: return not sq & 0x88
def sq_frm_str(s: str)       -> SquareInt: return int(s[1]) - 1 << 4 | ord(s[0]) - 97
def sq_frm_idx(i: int)       -> SquareInt: return i & 7 | i >> 3 << 4
def sq_make(f: int, r: int)  -> SquareInt: return r << 4 | f
def sq_mirror(sq: SquareInt) -> SquareInt: return sq ^ 0x70
VALID_SQUARES = tuple(sq for i in range(128) if sq_valid(sq := sq_frm_idx(i)))

PieceType = int
PIECE_TYPES = (PIECE_TYPE_NONE, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING) = range(7)
PIECE_NAMES = ("none", "pawn", "knight", "bishop", "rook", "queen", "king")
PIECE_CHARS = (".", "p", "n", "b", "r", "q", "k")

STEPPING_PIECES = (KNIGHT, KING)
SLIDING_PIECES  = (BISHOP, ROOK, QUEEN)
PROMOTIONS      = (QUEEN, ROOK, BISHOP, KNIGHT)

DIRECTIONS = (N, S, E, W) = (16, -16, 1, -1)

DELTAS = (
    (),  # NONE
    (),  # NONE
    (N+N+E, E+N+E, E+S+E, S+S+E, S+S+W, W+S+W, W+N+W, N+N+W),
    (N+E, S+E, S+W, N+W),
    (N, E, S, W),
    (N, E, S, W, N+E, S+E, S+W, N+W),
    (N, E, S, W, N+E, S+E, S+W, N+W)
)

class Piece(int):
    __slots__ = ()

    def __new__(cls, c: Color, t: PieceType) -> "Piece":
        return super().__new__(cls, (t << 1) | c)

    @property
    def color(self) -> Color:
        return self & 1

    @property
    def type(self) -> PieceType:
        return self >> 1

    @property
    def name(self) -> str:
        return PIECE_NAMES[self.type]

    @property
    def deltas(self) -> tuple[int, ...]:
        return DELTAS[self.type]

    def can_promote(self, to: SquareInt) -> bool:
        return self.type == PAWN and sq_rank(to) in (0, 7)

    @classmethod
    def from_int(cls, val: int) -> "Piece":
        return super().__new__(cls, val)

    @classmethod
    def from_char(cls, char: str) -> "Piece":
        pt = PIECE_CHARS.index(char.lower())
        return cls(int(char.isupper()), pt)

    @staticmethod
    def promotions(color: Color) -> tuple["Piece", ...]:
        return tuple(Piece(color, pt) for pt in PROMOTIONS)

    @property
    def char(self) -> str:
        return PIECE_CHARS[self.type].upper() if self.color else PIECE_CHARS[self.type].lower()

    def __str__(self) -> str:
        c = PIECE_CHARS[self.type]
        return c.upper() if self.color else c.lower()

    def hash(self, sq: SquareInt) -> int:
        return ZOBRIST_PIECES[sq][self] if self else 0

PIECE_NONE = Piece.from_int(0)

BLACK_PIECES = (
    _, BLACK_PAWN, BLACK_KNIGHT, BLACK_BISHOP, BLACK_ROOK, BLACK_QUEEN, BLACK_KING
) = (PIECE_NONE,) + tuple(Piece(BLACK, t) for t in PIECE_TYPES[1:])

WHITE_PIECES = (
    _, WHITE_PAWN, WHITE_KNIGHT, WHITE_BISHOP, WHITE_ROOK, WHITE_QUEEN, WHITE_KING
) = (PIECE_NONE,) + tuple(Piece(WHITE, t) for t in PIECE_TYPES[1:])

PIECES = (BLACK_PIECES, WHITE_PIECES)

class Move(int):
    __slots__ = ()

    def __new__(
        cls, frm: SquareInt, to: SquareInt, promotion: PieceType = PIECE_NONE
    ) -> "Move":
        return super().__new__(cls, frm << 10 | to << 3 | promotion)

    @property
    def frm(self) -> SquareInt:
        return self >> 10 & 0x7F

    @property
    def to(self) -> SquareInt:
        return self >> 3 & 0x7F

    @property
    def promotion(self) -> PieceType:
        return self & 0x7

    @property
    def delta(self) -> int:
        return abs(self.to - self.frm)

    @property
    def between(self) -> SquareInt:
        return (self.frm + self.to) >> 1

    def is_en_passant(self, board: "Board") -> bool:
        return board[self.frm].type == PAWN and self.to == board.ep_sq

    def is_capture(self, board: "Board") -> bool:
        return bool(board[self.to]) or self.is_en_passant(board)

    def is_castling(self, board: "Board") -> bool:
        return board[self.frm].type == KING and self.delta == 2

    def is_check(self, board: "Board") -> bool:
        state = board.push(self)
        check = board.is_check(board.color ^ 1)
        board.unpush(state)
        return check

    def is_checkmate(self, board: "Board") -> bool:
        state = board.push(self)
        mate = board.is_check(board.color ^ 1) and not board.legal_moves()
        board.unpush(state)
        return mate

    @classmethod
    def parse(cls, s: str) -> "Move":
        frm = sq_frm_str(s[:2])
        to  = sq_frm_str(s[2:4])
        promotion = PIECE_CHARS.index(s[4].lower()) if len(s) > 4 else PIECE_TYPE_NONE
        return cls(frm, to, promotion)

    def astuple(self) -> tuple[SquareInt, SquareInt, PieceType]:
        return self.frm, self.to, self.promotion

    def san(self, board: "Board") -> str:
        if self.is_castling(board):
            s = "O-O-O" if self.to < self.frm else "O-O"

        else:
            p = board[self.frm]
            s = "" if p.type == PAWN else p.char.upper()

            if p.type != PAWN:
                to_same = [
                    m for m in board.legal_moves()
                    if m.to == self.to and m.frm != self.frm and board[m.frm] == p
                ]

                if to_same:
                    same_file = any(sq_file(m.frm) == sq_file(self.frm) for m in to_same)
                    same_rank = any(sq_rank(m.frm) == sq_rank(self.frm) for m in to_same)

                    if not same_file:
                        s += sq_to_str(self.frm)[0]
                    elif not same_rank:
                        s += sq_to_str(self.frm)[1]
                    else:
                        s += sq_to_str(self.frm)

            if self.is_capture(board):
                if p.type == PAWN: s += sq_to_str(self.frm)[0]
                s += "x"

            s += sq_to_str(self.to)

            if self.promotion:
                s += f"={PIECE_CHARS[self.promotion].upper()}"

        if self.is_checkmate(board):
            s += "#"
        elif self.is_check(board):
            s += "+"

        return s

    def __str__(self) -> str:
        frm_file  = chr(sq_file(self.frm) + ord("a"))
        frm_rank  = str(sq_rank(self.frm) + 1)
        to_file   = chr(sq_file(self.to) + ord("a"))
        to_rank   = str(sq_rank(self.to) + 1)
        promo_str = f"{PIECE_CHARS[self.promotion].lower()}" if self.promotion else ""
        return f"{frm_file}{frm_rank}{to_file}{to_rank}{promo_str}"

    def __repr__(self) -> str:
        return f"Move({self})"

class CastlingRights(int):
    __slots__ = ()

    NONE = 0
    WHITE_KINGSIDE  = 1 << 0
    WHITE_QUEENSIDE = 1 << 1
    BLACK_KINGSIDE  = 1 << 2
    BLACK_QUEENSIDE = 1 << 3

    WHITE_BOTH = WHITE_KINGSIDE | WHITE_QUEENSIDE
    BLACK_BOTH = BLACK_KINGSIDE | BLACK_QUEENSIDE
    ALL        = WHITE_BOTH     | BLACK_BOTH

    @classmethod
    def from_fen(cls, fen: str) -> "CastlingRights":
        mapping = {"K": cls.WHITE_KINGSIDE, "Q": cls.WHITE_QUEENSIDE,
                   "k": cls.BLACK_KINGSIDE, "q": cls.BLACK_QUEENSIDE,}
        return cls(reduce(or_, (mapping[c] for c in fen if c in mapping), cls.NONE))

    def __str__(self) -> str:
        if self == self.NONE: return "-"
        s = ""
        if self & self.WHITE_KINGSIDE:  s += "K"
        if self & self.WHITE_QUEENSIDE: s += "Q"
        if self & self.BLACK_KINGSIDE:  s += "k"
        if self & self.BLACK_QUEENSIDE: s += "q"
        return s

    def __and__(self, other: int) -> "CastlingRights":
        return CastlingRights(super().__and__(other))

    def __iand__(self, other: int) -> "CastlingRights":
        return self.__and__(other)

COLOR_CASTLING_RIGHTS = (
    (CastlingRights.BLACK_KINGSIDE, CastlingRights.BLACK_QUEENSIDE),
    (CastlingRights.WHITE_KINGSIDE, CastlingRights.WHITE_QUEENSIDE)
)

CASTLING_SPOILERS = bytearray([CastlingRights.ALL] * 128)
CASTLING_SPOILERS[0]   = ~CastlingRights.WHITE_QUEENSIDE & 0xF  # A1
CASTLING_SPOILERS[7]   = ~CastlingRights.WHITE_KINGSIDE  & 0xF  # H1
CASTLING_SPOILERS[4]   = ~CastlingRights.WHITE_BOTH      & 0xF  # E1
CASTLING_SPOILERS[112] = ~CastlingRights.BLACK_QUEENSIDE & 0xF  # A8
CASTLING_SPOILERS[119] = ~CastlingRights.BLACK_KINGSIDE  & 0xF  # H8
CASTLING_SPOILERS[116] = ~CastlingRights.BLACK_BOTH      & 0xF  # E8


@dataclass(slots=True)
class State:
    move: Move | None
    captured: Piece
    ep_sq: SquareInt | None
    castling_rights: CastlingRights
    is_ep: bool
    hash: int
    abs_score: int = 0


class Board:
    STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    buf: bytearray
    king_sq: list[SquareInt]
    ep_sq: SquareInt | None
    castling_rights: CastlingRights
    color: Color

    def __init__(self, fen: str | None = None) -> None:
        fen = fen or self.STARTING_FEN
        self.from_fen(fen)
        self.hash = self.compute_hash()

    def compute_hash(self) -> int:
        return ZOBRIST_COLOR * self.color ^ \
               ZOBRIST_CASTLING[self.castling_rights] ^ \
               reduce(xor, (p.hash(sq) for sq, p in self), 0) ^ \
              (ZOBRIST_EP[self.ep_sq] if self.ep_sq is not None else 0)

    def from_fen(self, fen: str) -> None:
        parts = fen.strip().split()
        self._from_board_fen(parts[0])
        self.color = WHITE if parts[1] == "w" else BLACK
        self.castling_rights = CastlingRights.from_fen(parts[2])
        self.ep_sq = sq_frm_str(parts[3]) if parts[3] != "-" else None

    def _from_board_fen(self, board_fen: str) -> None:
        self.buf = bytearray(128)
        idx = 0
        for c in board_fen:
            if c == "/":
                continue
            if c.isdigit():
                idx += int(c)
            else:
                sq = sq_mirror(sq_frm_idx(idx))
                self[sq] = Piece.from_char(c)
                idx += 1

        self.king_sq = [0, 0]
        for sq, p in self.pieces_by_type(KING):
            self.king_sq[p.color] = sq

    def king_square(self, color: Color) -> SquareInt:
        return self.king_sq[color]

    def is_check(self, side: Color | None = None) -> bool:
        side = self.color if side is None else side
        return self.is_attacked(self.king_sq[side], by=side^1)

    def is_legal(self, move: Move) -> bool:
        state = self.push(move)
        check = self.is_attacked(self.king_sq[self.color^1], self.color)
        self.unpush(state)
        return not check

    def _is_attacked_by(
        self,
        sq: SquareInt,
        deltas: tuple[int, ...],
        sentinels: tuple[Piece, ...],
        stepper: bool = False
    ) -> bool:
        for d in deltas:
            for cur_sq in count(sq + d, d):
                if not sq_valid(cur_sq): break
                val = self[cur_sq]
                if val or stepper:
                    if val in sentinels: return True
                    break
        return False

    def is_attacked(self, sq: SquareInt, by: Color) -> bool:
        _, pawn, knight, bishop, rook, queen, king = PIECES[by]
        pawn_dir = S if by else N

        p_sq1 = sq + pawn_dir + W
        if sq_valid(p_sq1) and self[p_sq1] == pawn: return True
        p_sq2 = sq + pawn_dir + E
        if sq_valid(p_sq2) and self[p_sq2] == pawn: return True

        for p in (knight, king):
            if self._is_attacked_by(sq, p.deltas, (p,), stepper=True):
                return True

        if self._is_attacked_by(sq, rook.deltas, (rook, queen)):
            return True

        return self._is_attacked_by(sq, bishop.deltas, (bishop, queen))

    def gen_moves(self, qs: bool = False) -> Iterator[Move]:
        pawn_dir, promo_rank = (N, 7) if self.color else (S, 0)
        start_rank = promo_rank ^ 0x6

        for frm, p in self.pieces_by_color(self.color):
            pt = p.type

            if pt == PAWN:
                one = frm + pawn_dir
                if sq_valid(one) and not self[one]:
                    if sq_rank(one) == promo_rank:
                        yield from (Move(frm, one, pt) for pt in PROMOTIONS)
                    elif not qs:
                        yield Move(frm, one)
                    two = frm + 2 * pawn_dir
                    if not qs and sq_rank(frm) == start_rank and not self[two]:
                        yield Move(frm, two)

                for offset in (pawn_dir + W, pawn_dir + E):
                    to = frm + offset
                    if sq_valid(to):
                        tgt = self[to]
                        if (tgt and tgt.color != self.color) or to == self.ep_sq:
                            if sq_rank(to) == promo_rank:
                                yield from (Move(frm, to, pt) for pt in PROMOTIONS)
                            else:
                                yield Move(frm, to)
                continue

            for d in p.deltas:
                for to in count(frm + d, d):
                    if not sq_valid(to): break
                    tgt = self[to]
                    if not tgt:
                        if not qs:
                            yield Move(frm, to)
                    else:
                        if tgt.color != self.color:
                            yield Move(frm, to)
                        break
                    if pt in STEPPING_PIECES:
                        break

        if not qs and self.castling_rights and not self.is_check():
            cr  = self.castling_rights
            r   = COLOR_CASTLING_RIGHTS[self.color]
            frm = self.king_sq[self.color]

            ks_clear = cr & r[0] and self[frm+1] == self[frm+2] == 0
            if ks_clear and not self.is_attacked(frm+1, by=self.color^1):
                yield Move(frm, frm+2)

            qs_clear = cr & r[1] and self[frm-1] == self[frm-2] == self[frm-3] == 0
            if qs_clear and not self.is_attacked(frm-1, by=self.color^1):
                yield Move(frm, frm-2)

    def legal_moves(self) -> list[Move]:
        return [m for m in self.gen_moves() if self.is_legal(m)]

    def push(self, move: Move | None = None) -> State:
        old_hash = self.hash
        cr = self.castling_rights
        ep = self.ep_sq
        self.ep_sq = None

        self.hash ^= ZOBRIST_COLOR

        if ep is not None:
            self.hash ^= ZOBRIST_EP[ep]

        if move is None:
            self.color ^= 1
            return State(move, PIECE_NONE, ep, cr, False, old_hash)

        frm, to, promo = move.astuple()

        p = self[frm]
        self[frm] = PIECE_NONE
        self.hash ^= p.hash(frm)

        cap = self[to]
        is_ep = False
        pt = p.type

        if pt == PAWN and to == ep:
            is_ep = True
            ep_sq = to - 16 if p.color else to + 16
            cap = self[ep_sq]
            self[ep_sq] = PIECE_NONE

        elif pt == KING:
            self.king_sq[self.color] = move.to
            if move.delta == 2:
                rook_frm, rook_to = (frm + 3, frm + 1) if to > frm else (frm - 4, frm - 1)
                rook = Piece(self.color, ROOK)
                self[rook_to]  = self[rook_frm]
                self[rook_frm] = PIECE_NONE
                self.hash ^= rook.hash(rook_frm) ^ rook.hash(rook_to)

        cap_sq = to if not is_ep else (to - 16 if p.color else to + 16)
        self.hash ^= cap.hash(cap_sq)

        if promo:
            p = Piece(p.color, promo)

        self[to]  = p
        self.hash ^= p.hash(to)

        if pt == PAWN and move.delta == N+N:
            self.ep_sq = move.between
            self.hash ^= ZOBRIST_EP[self.ep_sq]

        self.castling_rights &= CASTLING_SPOILERS[frm]
        self.castling_rights &= CASTLING_SPOILERS[to]
        self.hash ^= ZOBRIST_CASTLING[self.castling_rights] ^ ZOBRIST_CASTLING[cr]
        self.color ^= 1
        return State(move, cap, ep, cr, is_ep, old_hash)

    def push_uci(self, s: str) -> State:
        return self.push(Move.parse(s))

    def unpush(self, state: State) -> None:
        self.color ^= 1
        self.hash = state.hash
        self.ep_sq = state.ep_sq

        move = state.move
        if move is None:
            return

        frm, to, promo = move.astuple()

        self.castling_rights = state.castling_rights
        p = Piece(self.color, PAWN) if promo else self[to]
        self[frm] = p

        if state.is_ep:
            self[to] = PIECE_NONE
            self[to - 16 if p.color else to + 16] = state.captured
        else:
            self[to] = state.captured

        if p.type == KING:
            self.king_sq[self.color] = frm
            if move.delta == 2:
                rook_frm, rook_to = (frm + 3, frm + 1) if to > frm else (frm - 4, frm - 1)
                self[rook_frm] = self[rook_to]
                self[rook_to]  = PIECE_NONE

    def pieces_by_color(self, c: Color) -> Iterator[tuple[SquareInt, Piece]]:
        for sq in VALID_SQUARES:
            v = self.buf[sq]
            if v and (v & 1) == c:
                yield sq, Piece.from_int(v)

    def pieces_by_type(self, pt: PieceType) -> Iterator[tuple[SquareInt, Piece]]:
        for sq in VALID_SQUARES:
            v = self.buf[sq]
            if v and (v >> 1) == pt:
                yield sq, Piece.from_int(v)

    def fen(self) -> str:
        rows = []
        for r in range(7, -1, -1):
            row = ""
            empty_count = 0
            for f in range(8):
                sq = sq_make(f, r)
                val = self.buf[sq]
                if not val:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row += str(empty_count)
                        empty_count = 0
                    row += str(Piece.from_int(val))
            if empty_count > 0:
                row += str(empty_count)
            rows.append(row)
        board_fen = "/".join(rows)
        color_fen = "w" if self.color == WHITE else "b"
        cr_fen = str(self.castling_rights) if self.castling_rights else "-"
        ep_fen = sq_to_str(self.ep_sq) if self.ep_sq is not None else "-"
        return f"{board_fen} {color_fen} {cr_fen} {ep_fen}"

    def copy(self) -> Self:
        return self.__class__(self.fen())

    def __iter__(self) -> Iterator[tuple[SquareInt, Piece]]:
        for sq in VALID_SQUARES:
            v = self.buf[sq]
            if v:
                yield sq, Piece.from_int(v)

    def __str__(self) -> str:
        return self.fen()

    def __getitem__(self, sq: SquareInt) -> Piece:
        return Piece.from_int(self.buf[sq])

    def __setitem__(self, sq: SquareInt, piece: Piece) -> None:
        self.buf[sq] = piece

    def perft(self, depth: int) -> int:
        if depth == 0: return 1
        nodes = 0
        side = self.color

        for move in self.gen_moves():
            state = self.push(move)

            if not self.is_check(side):
                nodes += self.perft(depth - 1) if depth > 1 else 1

            self.unpush(state)

        return nodes

class Square(int):
    __slots__ = ()

    @classmethod
    def make(cls, file: int, rank: int) -> "Square":
        return cls(sq_make(file, rank))

    @classmethod
    def from_idx(cls, idx: int) -> "Square":
        return cls(sq_frm_idx(idx))

    def to_idx(self) -> int:
        return sq_to_idx(self)

    def is_valid(self) -> bool:
        return sq_valid(self)

    @property
    def file(self) -> int:
        return sq_file(self)

    @property
    def rank(self) -> int:
        return sq_rank(self)

    def __str__(self) -> str:
        return sq_to_str(self)


if __name__ == "__main__":
    import argparse
    from time import perf_counter

    parser = argparse.ArgumentParser()
    parser.add_argument("depth", nargs="?", type=int, default=4)
    args = parser.parse_args()

    t0 = perf_counter()
    nodes = Board().perft(args.depth)
    elapsed = perf_counter() - t0
    print(f"{nodes} nodes ({int(nodes / elapsed)} nps)")

