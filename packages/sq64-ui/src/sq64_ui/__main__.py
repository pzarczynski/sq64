import logging
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum
from functools import partial
from importlib.resources import as_file, files
from pathlib import Path

import pygame
from pygame import Rect
from sq64_chess import Color, Piece, PieceType, Square
from sq64_chess.constants import BLACK, COLORS, PROMOS, WHITE
from sq64_chess.game import Game, GameViewer, Movetime, Outcome, Tempo, Time
from sq64_chess.types import color_name

from . import gui
from .gui import (
    RGB,
    Button,
    ClickEvent,
    ColorLike,
    Event,
    Grid,
    HBox,
    Image,
    StackBox,
    Text,
    VBox,
    Widget,
)
from .player import Computer, Human, Player

logging.basicConfig(level=logging.INFO)


@dataclass(slots=True, frozen=True)
class SquareSelectedEvent(Event):
    square: Square

@dataclass(slots=True, frozen=True)
class PromoEvent(Event):
    pt: PieceType

@dataclass(slots=True, frozen=True)
class NewGameEvent(Event):
    orient: Color
    tempo: Tempo

@dataclass(slots=True, frozen=True)
class GameUpdatedEvent(Event): ...

@dataclass(slots=True, frozen=True)
class BoardUpdatedEvent(Event): ...

class Assets:
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

    def board(self, c: Color) -> pygame.Surface: return self._boards[c]
    def piece(self, p: Piece) -> pygame.Surface: return self._pieces[p]

class WidgetPriority(IntEnum):
    OVERLAY = 0
    PIECE = 1

SquareWidget = gui.WidgetDict[WidgetPriority]

class Board(Grid[SquareWidget]):
    _promo_rects: list[tuple[PieceType, pygame.Rect]]

    def __init__(self, bus: gui.EventBus, assets: Assets, state: GameViewer) -> None:
        super().__init__(SquareWidget, rows=8, cols=8, spacing=0)
        self._assets = assets
        self._bus = bus
        self._size: int = 0

        self._state = state
        self._promo_rects = []
        self._orient: Color | None = None
        self._outcome_text = Text("", RGB.WHITE, scale=0.8)

        self._overlays: dict[RGB, Image] = {
            c: self._make_overlay(c.with_alpha(150)) for c in RGB
        }

        self._bus.register(BoardUpdatedEvent, self.handle_board_updated)
        self._bus.register(GameUpdatedEvent, self.handle_game_updated)
        self._bus.register(NewGameEvent, self.handle_new_game)

    def _make_overlay(self, color: ColorLike) -> Image:
        overlay = pygame.Surface((1, 1), pygame.SRCALPHA)
        overlay.fill(color)
        return Image(overlay)

    def _set_overlay(self, sq: Square, color: RGB) -> None:
        cell = self[*self.sq_to_coord(sq)]
        cell[WidgetPriority.OVERLAY] = self._overlays[color]

    def sq_to_coord(self, sq: Square) -> tuple[int, int]:
        assert self._orient is not None
        row = 7 - sq.rank if self._orient else sq.rank
        col = sq.file if self._orient else 7 - sq.file
        return row, col

    def square_at(self, pos: tuple[int, int]) -> Square | None:
        assert self._orient is not None
        if not self._rect.collidepoint(pos):
            return None

        x, y = (pos[0] - self._rect.left, pos[1] - self._rect.top)
        rank, file = (int(y / (self._size / 8)), int(x / (self._size / 8)))

        rel_rank = 7 - rank if self._orient else rank
        rel_file = file if self._orient else 7 - file
        return Square.make(rel_file, rel_rank)

    def handle_game_updated(self, event: GameUpdatedEvent) -> None:
        for cell in self._cells:
            cell.pop(WidgetPriority.OVERLAY)

        if last_sq := self._state.lastmove_to:
            self._set_overlay(last_sq, RGB.GREEN)

        if (sel_sq := self._state.selected_sq) is not None:
            self._set_overlay(sel_sq, RGB.YELLOW)

        if self._state.is_check:
            self._set_overlay(self._state.king_sq, RGB.RED)

        self.layout(self._rect)

    def handle_new_game(self, event: NewGameEvent) -> None:
        self._orient = event.orient
        self.handle_board_updated(BoardUpdatedEvent())

    def handle_board_updated(self, event: BoardUpdatedEvent) -> None:
        if self._orient is None: return

        self.set_bg(Image(self._assets.board(self._orient)))

        for cell in filter(None, self._cells):
            cell.clear()

        for sq, p in self._state.board:
            cell = self[*self.sq_to_coord(sq)]
            img = Image(self._assets.piece(p))
            cell[WidgetPriority.PIECE] = img

        self.layout(self._rect)

    def handle_event(self, event: Event) -> bool:
        if isinstance(event, ClickEvent):
            for pt, rect in self._promo_rects:
                if rect.collidepoint(event.pos):
                    self._promo_rects.clear()
                    self._bus.emit(PromoEvent(pt))
                    return True
            if (sq := self.square_at(event.pos)) is not None:
                self._bus.emit(SquareSelectedEvent(sq))
                return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        super().draw(screen)

        outcome = self._state.outcome
        self._promo_rects.clear()

        if self._state.wants_promo and not outcome:
            s = self._size / 8
            x = self._rect.left + self._size / 4
            y = self._rect.top + self._size / 2 - s / 2
            pygame.draw.rect(screen, RGB.GRAY, (x, y, self._size / 2, s))

            for i, pt in enumerate(PROMOS):
                rect = pygame.Rect(int(x + i * s), int(y), int(s), int(s))
                p = Piece.make(pt, self._state.color)
                self._promo_rects.append((p.type, rect))

                if img := self._assets.piece(p):
                    scaled_img = pygame.transform.smoothscale(img, (int(s), int(s)))
                    screen.blit(scaled_img, rect.topleft)

        if outcome:
            overlay = pygame.Surface((self._size, self._size), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            screen.blit(overlay, (self._rect.left, self._rect.top))

            msg = outcome.pretty(not self._state.color)
            self._outcome_text.set_text(msg)
            self._outcome_text.layout(self._rect)
            self._outcome_text.draw(screen)

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        self._size = max(1, int(min(rect.w, rect.h)))


class Menu(VBox):
    def __init__(
        self,
        bus: gui.EventBus,
        assets: Assets,
        state: GameViewer,
    ) -> None:
        super().__init__()
        self._assets = assets
        self._bus = bus
        self._color: Color | None = None
        self._orient: Color | None = None
        self._state = state

        self._bus.register(NewGameEvent, self.handle_new_game)
        self._bus.register(GameUpdatedEvent, self.handle_game_updated)

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
            HBox.pad(Button.from_text("Copy FEN", self.handle_fen_copy), pad=0.2),
            HBox.pad(Button.from_text("Copy PGN", self.handle_pgn_copy), pad=0.2),
            pad=0.3,
            spacing=0.05,
        )

        tempo_btns = [
            HBox.pad(
                Button.from_text(f"{tempo}", partial(self._new_game, tempo=tempo)),
                pad=0.2,
            )
            for tempo in Tempo
        ]
        tempo_view = VBox.pad(VBox.pad(*tempo_btns, pad=0.2, spacing=0.02), pad=0.3)
        self._stack = StackBox(main_view, tempo_view)

        super().__init__(
            self._ck_top, self._stack, self._ck_bot, weights=[0.2, 0.6, 0.2],
        )

    def _tempo(self, color: Color) -> None:
        self._color = color
        self._stack.set_active(1)

    def _new_game(self, tempo: Tempo) -> None:
        if self._color is not None:
            self._bus.emit(NewGameEvent(self._color, tempo))
            self._stack.set_active(0)

    def handle_fen_copy(self) -> None:
        pygame.scrap.put_text(self._state.fen)

    def handle_pgn_copy(self) -> None:
        pygame.scrap.put_text(self._state.pgn)

    def handle_game_updated(self, event: GameUpdatedEvent) -> None:
        if self._orient is None: return
        b_clk = str(self._state.clock(BLACK))
        w_clk = str(self._state.clock(WHITE))
        self._ck_top.set_text(b_clk if self._orient else w_clk)
        self._ck_bot.set_text(w_clk if self._orient else b_clk)

    def handle_new_game(self, event: NewGameEvent) -> None:
        self._orient = event.orient


class Layout(Widget):
    def __init__(self, board_view: Widget, menu: Widget, panel_frac: float) -> None:
        super().__init__()
        self._board_view = board_view
        self._menu = menu
        self._panel_frac = panel_frac

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        bs = min(rect.w * (1 - 2 * self._panel_frac), rect.h)
        pw = (rect.w - bs) / 2
        top = rect.y + (rect.h - bs) / 2
        board_rect = pygame.Rect(rect.x + pw, top, bs, bs)
        menu_rect = pygame.Rect(rect.x + bs + pw, top, pw, bs)
        self._board_view.layout(board_rect)
        self._menu.layout(menu_rect)

    def handle_event(self, event: Event) -> bool:
        return self._menu.handle_event(event) or self._board_view.handle_event(event)

    def draw(self, screen: pygame.Surface) -> None:
        self._board_view.draw(screen)
        self._menu.draw(screen)


class Controller:
    def __init__(
        self,
        bus: gui.EventBus,
        fen: str,
        local: Player,
        opponent: Player,
    ) -> None:
        self._bus = bus
        self._fen = fen
        self._local = local
        self._opponent = opponent
        self._ended = False

        self._game: Game | None = None
        self._players: tuple[Player, Player] | None = None
        self._curr_player: Player | None = None

        self._bus.register(NewGameEvent, self.handle_new_game)
        self._bus.register(SquareSelectedEvent, self.handle_sq_selected)
        self._bus.register(PromoEvent, self.handle_promo)

    def start_game(self, local_color: Color, tempo: Tempo) -> None:
        self._game = Game(self._fen, (tempo(), tempo()))
        self._ended = self._game.outcome is not None

        self._players = (
            (self._opponent, self._local)
            if local_color
            else (self._local, self._opponent)
        )

        for p in self._players:
            p.reset()

        self._curr_player = self._players[self._game.color]
        self._curr_player.begin(self._game)

    def handle_sq_selected(self, event: SquareSelectedEvent) -> None:
        if self._curr_player and not self.ended:
            self._curr_player.update_sq(event.square)

    def handle_promo(self, event: PromoEvent) -> None:
        if self._curr_player and not self.ended:
            self._curr_player.update_promo(event.pt)

    def handle_new_game(self, event: NewGameEvent) -> None:
        self.start_game(event.orient, event.tempo)
        self._bus.emit(GameUpdatedEvent())

    @property
    def ended(self) -> bool:
        return self._ended or not self._game or self._game.is_time_over()

    @property
    def color(self) -> Color:
        assert self._game
        return self._game.color

    @property
    def is_check(self) -> bool:
        assert self._game
        return self._game.is_check()

    @property
    def board(self) -> Iterable[tuple[Square, Piece]]:
        if self._game:
            yield from self._game

    @property
    def outcome(self) -> Outcome | None:
        assert self._game
        return self._game.outcome

    @property
    def selected_sq(self) -> Square | None:
        assert self._curr_player
        return self._curr_player.selected_sq

    @property
    def wants_promo(self) -> bool:
        assert self._curr_player
        return self._curr_player.wants_promo

    @property
    def lastmove_to(self) -> Square | None:
        assert self._game
        lastmove = self._game.history[-1].move if self._game.history else None
        return Square(lastmove.to) if lastmove else None

    @property
    def king_sq(self) -> Square:
        assert self._game
        return Square(self._game.king_square(self.color))

    @property
    def fen(self) -> str:
        assert self._game
        return self._game.fen()

    @property
    def pgn(self) -> str:
        assert self._game
        return self._game.pgn()

    def clock(self, c: Color) -> Time:
        assert self._game
        return self._game.control[c]

    def quit(self) -> None:
        if self._players:
            for p in self._players:
                p.quit()

    def update(self, dt: int) -> None:
        if self._ended or not self._game or not self._players or not self._curr_player:
            return

        if self._game.is_time_over():
            self._ended = True
            self._bus.emit(BoardUpdatedEvent())
            self._bus.emit(GameUpdatedEvent())
            return

        self._game.tick(dt)
        move = self._curr_player.getmove()

        if move and move in self._game.legal_moves():
            self._game.play(move)
            self._ended = bool(self._game.outcome)
            self._curr_player = self._players[self._game.color]
            self._curr_player.begin(self._game)
            self._bus.emit(BoardUpdatedEvent())

        self._bus.emit(GameUpdatedEvent())


class App(gui.Window[Layout]):
    def __init__(
        self,
        assets_dir: Path,
        height: float,
        panel_frac: float,
        fen: str,
        local_color: Color,
        tempo: Tempo,
        local_player: Player,
        opponent: Player,
    ) -> None:
        self.panel_frac = panel_frac
        width = height / (1 - 2 * self.panel_frac)
        super().__init__(width=width, height=height, title="sq64 GUI")

        self.controller = Controller(self.bus, fen, local_player, opponent)

        assets = Assets(assets_dir)
        self.board = Board(self.bus, assets, self.controller)
        self.menu = Menu(self.bus, assets, self.controller)

        root = Layout(self.board, self.menu, panel_frac)
        self.set_root(root)

        self.bus.emit(NewGameEvent(local_color, tempo))
        self.root.layout(self.screen.get_rect())

    def update(self, dt: int) -> None:
        self.controller.update(dt)

    def quit(self) -> None:
        self.controller.quit()


@dataclass(slots=True)
class Config:
    engine_path: str = "./sq64.sh"
    assets_dir: Path = Path("assets")
    panel_frac: float = 0.2
    height: float = 800.0

    fen: str = Game.STARTING_FEN
    tempo: Tempo = Tempo.BLITZ
    local_color: Color = WHITE
    response_speed: Movetime = Movetime.FAST


def main() -> None:
    pygame.init()

    cfg = Config()
    app = App(
        assets_dir=cfg.assets_dir,
        height=cfg.height,
        panel_frac=cfg.panel_frac,
        fen=cfg.fen,
        local_color=cfg.local_color,
        tempo=cfg.tempo,
        local_player=Human(),
        opponent=Computer(cfg.engine_path, cfg.response_speed),
    )

    try:
        app.run()
    finally:
        app.quit()


if __name__ == "__main__":
    main()
