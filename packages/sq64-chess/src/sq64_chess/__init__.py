"""
Rdzeń logiczny sq64.

Pakiet ten implementuje zasady gry w szachy (FIDE) oraz całkiem wydajny generator ruchów.
Zamiast standardowej tablicy 8x8, wykorzystuje reprezentację **0x88** pozwalającą na szybszą
weryfikację poprawności pól za pomocą operacji bitowych.

### Ważne komponenty:
- `sq64_chess.board.Chessboard` - Stan planszy (push/unpush move) i generator ruchów.
- `sq64_chess.game.Game` - Rozszerzenie planszy o logikę partii (zegary, historia, PGN).
"""

__all__: list[str] = []

from .board import Chessboard, Transition

__all__ += ["Chessboard", "Transition"]

from .types import CastlRights, Color, Direction, Move, Piece, PieceType, Square

__all__ += ["CastlRights", "Color", "Direction", "Move", "Piece", "PieceType", "Square"]

from .constants import BLACK, COLORS, PIECES, PROMOS, SQUARES, WHITE

__all__ += ["BLACK", "COLORS", "PIECES", "PROMOS", "SQUARES", "WHITE"]

from . import board, constants, game, types

__all__ += ["board", "constants", "game", "types"]
