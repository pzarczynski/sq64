import logging
from dataclasses import dataclass
from pathlib import Path

import pygame
from sq64_chess import Color
from sq64_chess.constants import WHITE
from sq64_chess.game import Game, Movetime, Tempo

from .controller import Controller
from .gui import Event, Widget, Window
from .player import Computer, Human
from .views import Assets, BoardViewer, Menu, OutcomeOverlay, PromotionOverlay

logging.basicConfig(level=logging.INFO)


class Layout(Widget):
    """A simple layout widget that arranges a board and a menu side by side."""
    _board: Widget
    _menu: Widget
    _panel_frac: float

    def __init__(self, board: Widget, menu: Widget, panel_frac: float) -> None:
        super().__init__()
        self._board = board
        self._menu = menu
        self._panel_frac = panel_frac

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        bs = min(rect.w * (1 - 2 * self._panel_frac), rect.h)
        pw = (rect.w - bs) / 2
        top = rect.y + (rect.h - bs) / 2
        board_rect = pygame.Rect(rect.x + pw, top, bs, bs)
        menu_rect = pygame.Rect(rect.x + bs + pw, top, pw, bs)
        self._board.layout(board_rect)
        self._menu.layout(menu_rect)

    def handle_event(self, event: Event) -> bool:
        return self._menu.handle_event(event) or self._board.handle_event(event)

    def draw(self, screen: pygame.Surface) -> None:
        self._board.draw(screen)
        self._menu.draw(screen)


class BoardArea(Widget):
    """A widget that contains the chess board, promotion overlay, and outcome overlay."""
    _board: BoardViewer
    _promo: PromotionOverlay
    _outcome: OutcomeOverlay
    _ctrl: Controller

    def __init__(
        self, board: BoardViewer, promo: PromotionOverlay, outcome: OutcomeOverlay, ctrl: Controller,
    ) -> None:
        super().__init__()
        self._board = board
        self._promo = promo
        self._outcome = outcome
        self._ctrl = ctrl

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        self._board.layout(rect)
        self._promo.layout(rect)
        self._outcome.layout(rect)

    def handle_event(self, event: Event) -> bool:
        if self._ctrl.ended: return False

        if self._ctrl.needs_promo:
            return self._promo.handle_event(event)

        return self._board.handle_event(event)

    def draw(self, screen: pygame.Surface) -> None:
        self._board.draw(screen)

        if self._ctrl.needs_promo:
            self._promo.draw(screen)

        self._outcome.draw(screen)


class App(Window):
    """Main application class that sets up the GUI and controls the game flow."""
    panel_frac: float
    ctrl: Controller
    board: BoardViewer
    menu: Menu
    promo: PromotionOverlay
    outcome: OutcomeOverlay

    def __init__(self, cfg: "Config") -> None:
        self.panel_frac = cfg.panel_frac
        width = cfg.height / (1 - 2 * self.panel_frac)
        super().__init__(width=width, height=cfg.height, title="sq64 GUI")

        self.ctrl = Controller(
            Human(), Computer(cfg.engine_path, cfg.response_speed),
            cfg.fen, cfg.local_color, cfg.tempo,
        )

        assets = Assets(cfg.assets_dir)

        self.board = BoardViewer(assets, cfg.local_color, on_square_click=self.ctrl.handle_sq_click)
        self.menu = Menu(
            assets,
            on_new_game=self.ctrl.handle_new_game,
            on_copy_fen=self.ctrl.handle_copy_fen,
            on_copy_pgn=self.ctrl.handle_copy_pgn,
        )

        self.promo = PromotionOverlay(assets, on_promo_select=self.ctrl.handle_promo_select)
        self.outcome = OutcomeOverlay()

        self.ctrl.set_views(self.board, self.menu, self.promo, self.outcome)

        board_area = BoardArea(self.board, self.promo, self.outcome, self.ctrl)
        self.set_root(Layout(board_area, self.menu, cfg.panel_frac))

    def update(self, dt: int) -> None:
        self.ctrl.update(dt)


@dataclass(slots=True)
class Config:
    """Configuration for the chess GUI application."""
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
    App(cfg).run()


if __name__ == "__main__":
    main()
