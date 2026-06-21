from .types import CastlRights, Color, Direction, Piece, PieceType, Square

COLORS: tuple[Color, Color] = (BLACK := False, WHITE := True)

SQUARES = [sq for i in range(128) if (sq := Square(i))]

PROMOS = (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT)

N, S, E, W = (Direction(16), Direction(-16), Direction(1), Direction(-1))
DELTAS: tuple[tuple[Direction, ...], ...] = (
    (),  # NONE
    (),  # PAWN
    (N+N+E, E+N+E, E+S+E, S+S+E, S+S+W, W+S+W, W+N+W, N+N+W),
    (N+E, S+E, S+W, N+W),
    (N, E, S, W),
    (N, E, S, W, N+E, S+E, S+W, N+W),
    (N, E, S, W, N+E, S+E, S+W, N+W),
)

PIECES = (
    [Piece.make(pt, BLACK) for pt in PieceType if pt != PieceType.NONE],
    [Piece.make(pt, WHITE) for pt in PieceType if pt != PieceType.NONE],
)

SPOILERS = bytearray([CastlRights.ALL] * 128)
SPOILERS[0]   = ~CastlRights.WHITE_QS   & 0xF  # A1
SPOILERS[7]   = ~CastlRights.WHITE_KS   & 0xF  # H1
SPOILERS[4]   = ~CastlRights.WHITE_BOTH & 0xF  # E1
SPOILERS[112] = ~CastlRights.BLACK_QS   & 0xF  # A8
SPOILERS[119] = ~CastlRights.BLACK_KS   & 0xF  # H8
SPOILERS[116] = ~CastlRights.BLACK_BOTH & 0xF  # E8
