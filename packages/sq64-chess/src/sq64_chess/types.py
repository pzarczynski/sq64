from enum import IntEnum, IntFlag, nonmember
from typing import NamedTuple

Color = bool
def color_name(c: Color) -> str: return "white" if c else "black"


class Square(int):  # square in 0x88 representation
    """Represents a square on the chessboard using 0x88 encoding."""
    @property
    def file(self) -> int: return self & 7
    @property
    def rank(self) -> int: return self >> 4
    @property
    def idx(self) -> int: return self.file | self.rank << 3
    @property
    def valid(self) -> bool: return not self & 0x88
    @property
    def mirror(self) -> "Square": return Square(self ^ 0x70)

    @classmethod
    def frm_idx(cls, i: int) -> "Square": return cls(i & 7 | i >> 3 << 4)
    @classmethod
    def frm_str(cls, s: str) -> "Square": return cls(ord(s[0]) - 97 | (int(s[1]) - 1) << 4)
    @classmethod
    def make(cls, f: int, r: int) -> "Square": return cls(r << 4 | f)

    def rotate(self, orient: Color) -> "Square": return Square(0x77 - self) if orient else self

    def __bool__(self) -> bool: return self.valid
    def __add__(self, other: int) -> "Square": return Square(int(self) + other)
    def __sub__(self, other: int) -> "Square": return Square(int(self) - other)
    def __str__(self) -> str: return f"{chr(self.file + 97)}{self.rank + 1}"


class PieceType(IntEnum):
    """Represents the type of a chess piece (pawn, knight, bishop, rook, queen, king)."""
    NONE   = 0
    PAWN   = 1
    KNIGHT = 2
    BISHOP = 3
    ROOK   = 4
    QUEEN  = 5
    KING   = 6

    CHARS  = nonmember((".", "p", "n", "b", "r", "q", "k"))
    NAMES  = nonmember(("", "pawn", "knight", "bishop", "rook", "queen", "king"))

    @property
    def char(self) -> str: return self.CHARS[self]
    @property
    def name(self) -> str: return self.NAMES[self]

    @classmethod
    def frm_char(cls, char: str) -> "PieceType":
        return cls(cls.CHARS.index(char.lower()))

Direction = int

class Piece(IntEnum):
    """Represents a chess piece."""
    NONE = 0

    BLACK_PAWN   = PieceType.PAWN   << 1
    BLACK_KNIGHT = PieceType.KNIGHT << 1
    BLACK_BISHOP = PieceType.BISHOP << 1
    BLACK_ROOK   = PieceType.ROOK   << 1
    BLACK_QUEEN  = PieceType.QUEEN  << 1
    BLACK_KING   = PieceType.KING   << 1

    WHITE_PAWN   = PieceType.PAWN   << 1 | 1
    WHITE_KNIGHT = PieceType.KNIGHT << 1 | 1
    WHITE_BISHOP = PieceType.BISHOP << 1 | 1
    WHITE_ROOK   = PieceType.ROOK   << 1 | 1
    WHITE_QUEEN  = PieceType.QUEEN  << 1 | 1
    WHITE_KING   = PieceType.KING   << 1 | 1

    @property
    def color(self) -> Color: return Color(self & 1)
    @property
    def type(self) -> PieceType: return PieceType(self >> 1)

    @property
    def char(self) -> str:
        ch = self.type.char
        return ch.upper() if self.color else ch.lower()

    @property
    def name(self) -> str: return self.type.name

    @classmethod
    def make(cls, pt: PieceType, c: Color) -> "Piece":
        return cls(pt << 1 | c)

    @classmethod
    def frm_char(cls, char: str) -> "Piece":
        return cls.make(PieceType.frm_char(char), char.isupper())

    def can_promote(self, to: Square) -> bool:
        """Returns True if this piece can promote by moving to the given square."""
        return self.type == PieceType.PAWN and to.rank in (0, 7)

    def __str__(self) -> str: return self.char


class Move(NamedTuple):
    """Represents a chess move."""
    frm: Square
    to: Square
    promo: PieceType = PieceType.NONE

    @property
    def delta(self) -> int:
        """Returns the difference between the destination and origin squares."""
        return abs(self.to - self.frm)

    @property
    def between(self) -> Square:
        """Returns the square between the origin and destination squares."""
        return Square((self.frm + self.to) >> 1)

    @classmethod
    def parse(cls, s: str) -> "Move":
        """Parses a move from a string in long algebraic notation (e.g., "e2e4" or "e7e8q")."""
        frm = Square.frm_str(s[:2])
        to  = Square.frm_str(s[2:4])
        promo = PieceType.frm_char(s[4].lower()) if len(s) > 4 else PieceType.NONE
        return cls(frm, to, promo)

    def __str__(self) -> str:
        frm_file  = chr(self.frm.file + ord("a"))
        frm_rank  = str(self.frm.rank + 1)
        to_file   = chr(self.to.file + ord("a"))
        to_rank   = str(self.to.rank + 1)
        promo_str = f"{self.promo.char.lower()}" if self.promo else ""
        return f"{frm_file}{frm_rank}{to_file}{to_rank}{promo_str}"

    def __repr__(self) -> str:
        return f"Move({self})"


class CastlRights(IntFlag):
    """Represents the castling rights for both players using bit flags."""
    NONE     = 0
    WHITE_KS = 1 << 0
    WHITE_QS = 1 << 1
    BLACK_KS = 1 << 2
    BLACK_QS = 1 << 3

    WHITE_BOTH = WHITE_KS | WHITE_QS
    BLACK_BOTH = BLACK_KS | BLACK_QS
    ALL        = WHITE_BOTH | BLACK_BOTH

    @classmethod
    def by(cls, c: Color) -> tuple["CastlRights", "CastlRights"]:
        return (cls.WHITE_KS, cls.WHITE_QS) if c else (cls.BLACK_KS, cls.BLACK_QS)

    @classmethod
    def frm_fen(cls, fen: str) -> "CastlRights":
        cr = cls.NONE
        if "K" in fen: cr |= cls.WHITE_KS
        if "Q" in fen: cr |= cls.WHITE_QS
        if "k" in fen: cr |= cls.BLACK_KS
        if "q" in fen: cr |= cls.BLACK_QS
        return cr

    def __str__(self) -> str:
        if self == CastlRights.NONE: return "-"
        s = ""
        if self & CastlRights.WHITE_KS:  s += "K"
        if self & CastlRights.WHITE_QS: s += "Q"
        if self & CastlRights.BLACK_KS:  s += "k"
        if self & CastlRights.BLACK_QS: s += "q"
        return s
