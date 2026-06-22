"""
The core of sq64.

This package implements the rules of chess (FIDE) and a fairly efficient move generator.
Instead of the typical 8x8 board, it uses a **0x88** representation that allows for faster
validation of squares using bitwise operations.

### Important components:
- `sq64_chess.board.Chessboard` - Board state (push/unpush move) and move generator.
- `sq64_chess.game.Game` - Extends the board with game logic (clocks, history, PGN).
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
