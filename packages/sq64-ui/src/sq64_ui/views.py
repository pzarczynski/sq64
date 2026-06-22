from collections.abc import Callable, Iterable
from enum import IntEnum
from functools import partial
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from pathlib import Path

import pygame
from sq64_chess import Color, Piece, PieceType, Square
from sq64_chess.constants import BLACK, COLORS, PROMOS, WHITE
from sq64_chess.game import Tempo
from sq64_chess.types import color_name

from . import gui
from .gui import RGB, Button, ClickEvent, ColorLike, Event, HBox, Image, Text, VBox, Widget


class Assets:
    """Class responsible for loading and providing access to the graphical assets used in the application, such as board and piece images."""
    _path: Traversable
    _boards: dict[Color, pygame.Surface]
    _pieces: dict[Piece, pygame.Surface]

    def __init__(self, path: Path) -> None:
        self._path = files("sq64_ui").joinpath(path)
        self._boards = {c: self._load_board(c) for c in COLORS}
        self._pieces = {p: self._load_piece(p) for p in Piece if p}

    def _load_board(self, c: Color) -> pygame.Surface:
        with as_file(self._path / color_name(c) / "board.png") as path:
            return pygame.image.load(path).convert()

    def _load_piece(self, p: Piece) -> pygame.Surface:
        with as_file(self._path / color_name(p.color) / f"{p.name}.png") as path:
            return pygame.image.load(path).convert_alpha()

    def board(self, c: Color) -> pygame.Surface:
        return self._boards[c]

    def piece(self, p: Piece) -> pygame.Surface:
        return self._pieces[p]


class WidgetPriority(IntEnum):
    """Enum representing the priority of widgets within a cell, used to determine the drawing order of overlays and pieces."""
    OVERLAY = 0
    PIECE = 1

SquareWidget = gui.WidgetDict[WidgetPriority]

class BoardViewer(gui.Grid[SquareWidget]):
    """Widget that displays the chess board and pieces, and handles user interactions such as square clicks."""
    _assets: Assets
    _orient: Color
    _on_square_click: Callable[[Square], None]
    _size: int
    _overlays: dict[RGB, Image]

    def __init__(
        self,
        assets: Assets,
        orient: Color,
        on_square_click: Callable[[Square], None],
    ) -> None:
        super().__init__(SquareWidget, rows=8, cols=8, spacing=0)
        self._assets = assets
        self._orient = orient
        self._on_square_click = on_square_click

        self._size = 0
        self._overlays = {c: self._make_overlay(c.with_alpha(150)) for c in RGB}
        self.set_bg(Image(self._assets.board(self._orient)))

    def _make_overlay(self, color: ColorLike) -> Image:
        overlay = pygame.Surface((1, 1), pygame.SRCALPHA)
        overlay.fill(color)
        return Image(overlay)

    def _set_overlay(self, sq: Square, color: RGB) -> None:
        cell = self[*self.sq_to_coord(sq)]
        cell[WidgetPriority.OVERLAY] = self._overlays[color]

    def sq_to_coord(self, sq: Square) -> tuple[int, int]:
        sq = sq.rotate(self._orient)
        return sq.rank, sq.file

    def square_at(self, pos: tuple[int, int]) -> Square | None:
        if not self._rect.collidepoint(pos): return None

        x, y = (pos[0] - self._rect.left, pos[1] - self._rect.top)
        rank, file = (int(y / (self._size / 8)), int(x / (self._size / 8)))
        return Square.make(file, rank).rotate(self._orient)

    def handle_event(self, event: Event) -> bool:
        if isinstance(event, ClickEvent) and (sq := self.square_at(event.pos)) is not None:
            self._on_square_click(sq)
            return True
        return False

    def sync(
        self,
        board_state: Iterable[tuple[Square, Piece]],
        orient: Color,
        check_sq: Square | None,
        last_move_sq: Square | None,
        selected_sq: Square | None,
    ) -> None:
        """Synchronizes the board view with the current game state, updating piece positions, orientation, and overlays for checks and moves."""
        if self._orient != orient:
            self._orient = orient
            self.set_bg(gui.Image(self._assets.board(self._orient)))
            if self._rect.w > 0:
                self.layout(self._rect)

        for cell in filter(None, self._cells): cell.clear()

        for sq, p in board_state:
            cell = self[*self.sq_to_coord(sq)]
            cell[WidgetPriority.PIECE] = gui.Image(self._assets.piece(p))

        if selected_sq is not None:
            self._set_overlay(selected_sq, RGB.YELLOW)
        if last_move_sq is not None:
            self._set_overlay(last_move_sq, RGB.GREEN)
        if check_sq is not None:
            self._set_overlay(check_sq, RGB.RED)

        self.layout(self._rect)

    def draw(self, screen: pygame.Surface) -> None:
        super().draw(screen)

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        self._size = max(1, int(min(rect.w, rect.h)))


class PromotionOverlay(Widget):
    """Widget that displays the promotion options when a pawn is promoted."""
    _assets: Assets
    _on_promo_select: Callable[[PieceType], None]
    _box: HBox
    _bg_rect: pygame.Rect

    def __init__(self, assets: Assets, on_promo_select: Callable[[PieceType], None]) -> None:
        super().__init__()
        self._assets = assets
        self._on_promo_select = on_promo_select
        self._color: Color | None = None
        self._box = gui.HBox()
        self._bg_rect = pygame.Rect(0, 0, 0, 0)

    def sync(self, color: Color) -> None:
        """Synchronizes the promotion overlay with the current promotion color, updating the displayed options accordingly."""
        if self._color == color: return
        self._color = color
        btns = [
            gui.Button(
                gui.Image(self._assets.piece(Piece.make(pt, color))),
                on_click=partial(self._on_promo_select, pt),
                bg=RGB.GRAY,
            ) for pt in PROMOS
        ]
        self._box = gui.HBox.pad(*btns, pad=0.1, spacing=0.05)

        if self._bg_rect.w > 0:
            self.layout(self._bg_rect)

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        w, h = rect.w * 0.6, rect.h * 0.15
        x, y = rect.centerx - w/2, rect.centery - h/2
        self._bg_rect = pygame.Rect(int(x), int(y), int(w), int(h))
        self._box.layout(self._bg_rect)

    def handle_event(self, event: Event) -> bool:
        return self._box.handle_event(event)

    def draw(self, screen: pygame.Surface) -> None:
        overlay = pygame.Surface((self._bg_rect.w, self._bg_rect.h), pygame.SRCALPHA)
        overlay.fill(RGB.GRAY.with_alpha(200))
        screen.blit(overlay, self._bg_rect.topleft)
        self._box.draw(screen)


class OutcomeOverlay(Widget):
    """Widget that displays the outcome of the game when it has ended."""
    _text: Text
    _bg_rect: pygame.Rect
    _msg: str

    def __init__(self) -> None:
        super().__init__()
        self._text = gui.Text("", RGB.WHITE, scale=0.8)
        self._bg_rect = pygame.Rect(0, 0, 0, 0)
        self._msg = ""

    def sync(self, msg: str | None) -> None:
        """Synchronizes the outcome overlay with the current game outcome message."""
        if self._msg != msg:
            self._msg = msg or ""
            self._text.set_text(self._msg)
            if self._bg_rect.w > 0:
                self.layout(self._bg_rect)

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        self._bg_rect = rect
        self._text.layout(rect)

    def draw(self, screen: pygame.Surface) -> None:
        if not self._msg: return
        overlay = pygame.Surface((self._bg_rect.w, self._bg_rect.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, self._bg_rect.topleft)
        self._text.draw(screen)


class Menu(VBox):
    """Widget that displays the menu for starting a new game, copying FEN/PGN, and showing the clocks for both players."""
    _on_new_game: Callable[[Color, Tempo], None]
    _color: Color | None
    _assets: Assets
    _ck_top: Text
    _ck_bot: Text
    _stack: gui.StackBox

    def __init__(
        self,
        assets: Assets,
        on_new_game: Callable[[Color, Tempo], None],
        on_copy_fen: Callable[[], None],
        on_copy_pgn: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_new_game = on_new_game
        self._color = None
        self._assets = assets
        self._ck_top = Text("", RGB.WHITE, scale=0.6)
        self._ck_bot = Text("", RGB.WHITE, scale=0.6)

        wk_btn = Button(
            Image(assets.piece(Piece.WHITE_KING)),
            on_click=partial(self._tempo, color=WHITE),
        )
        bk_btn = Button(
            Image(assets.piece(Piece.BLACK_KING)),
            on_click=partial(self._tempo, color=BLACK),
        )

        main_view = VBox.pad(
            HBox.pad(wk_btn, bk_btn, pad=0.3),
            HBox.pad(Button.from_text("Copy FEN", on_copy_fen), pad=0.2),
            HBox.pad(Button.from_text("Copy PGN", on_copy_pgn), pad=0.2),
            pad=0.3, spacing=0.05,
        )

        tempo_btns = [
            HBox.pad(
                Button.from_text(f"{tempo}", partial(self._new_game, tempo=tempo)),
                pad=0.2,
            )
            for tempo in Tempo
        ]
        tempo_view = VBox.pad(VBox.pad(*tempo_btns, pad=0.2, spacing=0.02), pad=0.3)
        self._stack = gui.StackBox(main_view, tempo_view)

        super().__init__(
            self._ck_top, self._stack, self._ck_bot, weights=[0.2, 0.6, 0.2],
        )

    def _tempo(self, color: Color) -> None:
        self._color = color
        self._stack.set_active(1)

    def _new_game(self, tempo: Tempo) -> None:
        if self._color is not None:
            self._on_new_game(self._color, tempo)
            self._stack.set_active(0)

    def sync_clocks(self, top_time: str, bot_time: str) -> None:
        self._ck_top.set_text(top_time)
        self._ck_bot.set_text(bot_time)

