import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import pygame

import sq64.chess as chess
from sq64.chess import Board, Piece, Square
from sq64.game import Game, Movetime, Tempo
from sq64.gui import Button
from sq64.player import Computer, Human, Player

logging.basicConfig(level=logging.INFO)

consume = partial(deque, maxlen=0)  # consume iterator with side effects

class Assets:
    BLACK    = (0, 0, 0)
    WHITE    = (255, 255, 255)
    GRAY     = (128, 128, 128)
    DARKGRAY = (50, 50, 50)
    RED      = (255, 0, 0)
    GREEN    = (0, 255, 0)
    YELLOW   = (255, 255, 0)

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

        self._board_imgs = {
            color: self._load_board_img(color) for color in chess.COLORS
        }
        self._piece_imgs = {
            p: self._load_piece_img(p) for p in chess.PIECES[0] + chess.PIECES[1] if p
        }

    def _load_board_img(self, color: chess.Color) -> pygame.Surface:
        path = self._path / chess.color_name(color) / "board.png"
        return pygame.image.load(path).convert()

    def board_img(self, c: chess.Color, size: float) -> pygame.Surface:
        return pygame.transform.scale(self._board_imgs[c], (size, size))

    def _load_piece_img(self, p: Piece) -> pygame.Surface:
        path = self._path / chess.color_name(p.color) / f"{p.name}.png"
        return pygame.image.load(path).convert_alpha()

    def piece_img(self, piece: Piece, size: float) -> pygame.Surface:
        return pygame.transform.scale(self._piece_imgs[piece], (size, size))

    def piece_imgs(self, size: float) -> dict[Piece, pygame.Surface]:
        return {p: self.piece_img(p, size) for p in self._piece_imgs}


class BoardView:
    _promo_rects: list[tuple[int, pygame.Rect]]

    def __init__(
        self,
        screen: pygame.Surface,
        assets: Assets,
    ) -> None:
        self._screen = screen
        self._assets = assets
        self.clear()

    def update_callbacks(
        self,
        on_select: Callable[[Square], None],
        on_promo: Callable[[chess.PieceType], None]
    ) -> None:
        self.on_select = on_select
        self.on_promo = on_promo

    def clear(self) -> None:
        self._promo_rects = []

    def set_orientation(self, color: chess.Color) -> None:
        self._orient = color

    def square_at(self, pos: tuple[int, int]) -> Square | None:
        if not self._board_rect.collidepoint(pos): return None
        x_rel, y_rel = (pos[0] - self._left, pos[1] - self._top)  # relative board coords
        rank = int(y_rel / (self._size / 8))
        rel_rank = 7 - rank if self._orient else rank
        return Square.make(int(x_rel / (self._size / 8)), rel_rank)

    def handle_click(self, event: pygame.Event) -> None:
        for pt, rect in self._promo_rects:
            if rect.collidepoint(event.pos):
                self._promo_rects.clear()
                self.on_promo(pt)
                return

        if (sq := self.square_at(event.pos)) is not None:
            self.on_select(sq)

    def draw(self, game: Game, selected_sq: Square | None, draw_promo: bool) -> None:
        self._screen.fill(self._assets.DARKGRAY)
        self._screen.blit(self._board_img, (self._left, self._top))
        s = self._size / 8

        lastmove = game.history[-1].move if game.history else None

        for sq, piece in game:
            rel_rank = 7 - sq.rank if self._orient else sq.rank
            sq_rect = pygame.Rect(self._left + sq.file*s, self._top + rel_rank*s, s, s)

            overlay = pygame.Surface((s, s), pygame.SRCALPHA)
            if lastmove and sq == lastmove.to:
                overlay.fill((*self._assets.GREEN, 150))
                self._screen.blit(overlay, sq_rect)
            elif sq == selected_sq:
                overlay.fill((*self._assets.YELLOW, 150))
                self._screen.blit(overlay, sq_rect)
            elif game.is_check() and sq == game.king_square(game.color):
                overlay.fill((*self._assets.RED, 150))
                self._screen.blit(overlay, sq_rect)

            img = self._piece_imgs[piece]
            self._screen.blit(img, img.get_rect(center=sq_rect.center))

        outcome = game.outcome

        if draw_promo and not outcome:
            x = self._left + self._size / 4
            y = self._top + self._size / 2 - s / 2
            pygame.draw.rect(self._screen, self._assets.GRAY, (x, y, self._size / 2, s))

            for i, p in enumerate(Piece.promotions(game.color)):
                rect = pygame.Rect(x + i*s, y, s, s)
                self._promo_rects.append((p.type, rect))
                self._screen.blit(self._piece_imgs[p], rect.topleft)

        if outcome:
            overlay = pygame.Surface((self._size, self._size), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self._screen.blit(overlay, (self._left, self._top))

            enemy = chess.color_name(game.color ^ 1).capitalize()
            surf = self._font.render(outcome.pretty(enemy), True, self._assets.WHITE)
            self._screen.blit(surf, surf.get_rect(center=self._board_rect.center))

    def relayout(self, top: float, left: float, size: float) -> None:
        self._top = top
        self._left = left
        self._size = size
        self._font = pygame.font.SysFont(None, int(self._size / 10))
        self._piece_imgs = self._assets.piece_imgs(self._size * 0.11)
        self._board_img = self._assets.board_img(self._orient, self._size)
        self._board_rect = pygame.Rect(self._left, self._top, self._size, self._size)


class Menu:
    _select_tempo: bool
    _main_btns: list[Button]
    _tempo_btns: list[Button]

    def __init__(
        self,
        screen: pygame.Surface,
        assets: Assets,
        on_new_game: Callable[[int, Tempo], None],
        on_copy_fen: Callable[[], None],
        on_copy_pgn: Callable[[], None]
    ) -> None:
        self._screen = screen
        self._assets = assets
        self._select_tempo = False

        self.on_new_game = on_new_game
        self.on_copy_fen = on_copy_fen
        self.on_copy_pgn = on_copy_pgn

    def handle_click(self, pos: tuple[int, int]) -> None:
        if any(b.handle_click(pos) for b in self._main_btns):
            self._select_tempo = False

        consume(
            b.handle_click(pos) for b in
            (self._tempo_btns if self._select_tempo else self._newgame_btns)
        )

    def draw(self, game: Game, orient: chess.Color) -> None:
        tb = self._font_l.render(str(game.control[0]), True, self._assets.WHITE)
        tw = self._font_l.render(str(game.control[1]), True, self._assets.WHITE)

        mid_x = self._left + self._width / 2
        tuppr = (mid_x, self._top + self._height * 0.1)
        tdown = (mid_x, self._top + self._height * 0.9)
        self._screen.blit(tb, tb.get_rect(center=tuppr if orient else tdown))
        self._screen.blit(tw, tw.get_rect(center=tdown if orient else tuppr))

        btns = self._tempo_btns if self._select_tempo else self._newgame_btns
        for btn in btns + self._main_btns:
            btn.draw(self._screen)

    def _trigger_tempo(self, color: chess.Color) -> None:
        self._color = color
        self._select_tempo = True

    def _trigger_new_game(self, tempo: Tempo) -> None:
        if self._color is not None:
            self.on_new_game(self._color, tempo)
            self._select_tempo = False

    def relayout(self, top: float, left: float, width: float, height: float) -> None:
        self._top = top
        self._left = left
        self._width = width
        self._height = height

        s = min(width / 3, height / 9)
        self._font_l = pygame.font.SysFont(None, int(0.9 * s))
        self._font_s = pygame.font.SysFont(None, int(0.35 * s))

        x, y = (self._left + self._width / 2, self._top + self._height / 2)

        fen_txt = self._font_s.render("Copy FEN", True, self._assets.WHITE)
        fen_btn = Button(fen_txt, self.on_copy_fen, x, y + 1.5 * s, 2 * s, 0.5 * s, bg=self._assets.GRAY)
        pgn_txt = self._font_s.render("Copy PGN", True, self._assets.WHITE)
        pgn_btn = Button(pgn_txt, self.on_copy_pgn, x, y + 2.1 * s, 2 * s, 0.5 * s, bg=self._assets.GRAY)
        self._main_btns = [fen_btn, pgn_btn]

        wk_img = self._assets.piece_img(Piece(chess.WHITE, chess.KING), s)
        wk_newgame_btn = Button(wk_img, partial(self._trigger_tempo, color=chess.WHITE), x - s / 2, y)

        bk_img = self._assets.piece_img(Piece(chess.BLACK, chess.KING), s)
        bk_newgame_btn = Button(bk_img, partial(self._trigger_tempo, color=chess.BLACK), x + s / 2, y)

        self._newgame_btns = [wk_newgame_btn, bk_newgame_btn]
        self._tempo_btns =  [
            Button(
                self._font_s.render(str(tempo), True, self._assets.WHITE),
                partial(self._trigger_new_game, tempo=tempo),
                x, y + 0.5 * s * (i - 1), 2 * s, 0.4 * s,
                bg=self._assets.GRAY
            )
            for i, tempo in enumerate(Tempo)
        ]

class App:
    players: tuple[Player, Player]

    def __init__(
        self,
        assets_dir: Path,
        height: float,
        panel_frac: float,
        fen: str,
        local_color: int,
        tempo: Tempo,
        local_player: Player,
        opponent: Player
    ) -> None:
        pygame.init()
        self.panel_frac = panel_frac

        # height = board_width = width * (1 - 2 * panel_frac)
        self.height = height
        self.width = height / (1 - 2 * self.panel_frac)

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("sq64 GUI")

        assets = Assets(assets_dir)

        self.fen = fen
        self.local_color = local_color
        self.tempo = tempo

        self.local_player = local_player
        self.opponent = opponent

        self.clock = pygame.time.Clock()
        self.board_view = BoardView(self.screen, assets)
        self.menu = Menu(
            self.screen,
            assets,
            on_new_game=self.handle_new_game,
            on_copy_fen=self.handle_fen_copy,
            on_copy_pgn=self.handle_pgn_copy
        )

    def handle_new_game(self, color: int, tempo: Tempo) -> None:
        self.start_game(color, tempo)

    def handle_fen_copy(self) -> None:
        pygame.scrap.put_text(self.game.fen())

    def handle_pgn_copy(self) -> None:
        pygame.scrap.put_text(self.game.pgn())

    def start_game(self, local_color: int, tempo: Tempo) -> None:
        self.local_color = local_color
        self.tempo = tempo

        self.game = Game(self.fen, [tempo.time_fn(), tempo.time_fn()])

        # this is heavy so we don't want to keep it in the hot loop
        self.ended = bool(self.game.outcome)

        self.players = (
            (self.opponent, self.local_player) if local_color else
            (self.local_player, self.opponent)
        )
        consume(p.reset() for p in self.players)

        player = self.players[self.game.color]
        player.begin(self.game)
        self.current_player = player

        self.board_view.update_callbacks(
            on_select=self.current_player.update_sq,
            on_promo=self.current_player.update_promo
        )
        self.board_view.set_orientation(self.local_color)
        self.relayout(self.width, self.height)

    def run(self) -> None:
        running = True
        self.start_game(self.local_color, self.tempo)

        try:
            while running:
                dt = self.clock.tick(60)
                ended = self.ended or self.game.is_time_over()

                if not ended:
                    self.game.tick(dt)

                for event in pygame.event.get():
                    match event.type:
                        case pygame.QUIT:
                            running = False
                        case pygame.VIDEORESIZE:
                            self.relayout(*event.size)
                        case pygame.MOUSEBUTTONDOWN if event.button == 1:
                            if not ended:
                                self.board_view.handle_click(event)
                            self.menu.handle_click(event.pos)

                move = self.current_player.getmove()

                if move and move in self.game.legal_moves():
                    self.game.play(move)
                    self.ended = bool(self.game.outcome)
                    self.board_view.clear()

                    # switch player and begin next turn
                    self.current_player = self.players[self.game.color]
                    self.current_player.begin(self.game)
                    self.board_view.update_callbacks(
                        on_select=self.current_player.update_sq,
                        on_promo=self.current_player.update_promo
                    )

                self.board_view.draw(
                    self.game,
                    selected_sq=self.current_player.selected_sq,
                    draw_promo=self.current_player.wants_promo
                )
                self.menu.draw(self.game, orient=self.local_color)
                pygame.display.flip()

        finally:
            consume(p.quit() for p in self.players)
            pygame.quit()

    def relayout(self, w: float, h: float) -> None:
        self.height = h
        self.width  = w
        bs = min(w * (1 - 2 * self.panel_frac), h)
        pw = (w - bs) / 2
        top = (h - bs) / 2

        self.board_view.relayout(top, pw, bs)
        self.menu.relayout(top, bs + pw, pw, bs)


@dataclass(slots=True)
class Config:
    engine_path: str  = "./sq64.sh"
    assets_dir:  Path = Path("assets")
    panel_frac: float = 0.2
    height: float     = 800.0

    fen:         str   = Board.STARTING_FEN
    tempo:       Tempo = Tempo.BLITZ
    local_color: int   = chess.WHITE
    response_speed: Movetime = Movetime.FAST


if __name__ == "__main__":
    cfg = Config()
    App(
        assets_dir=cfg.assets_dir,
        height=cfg.height,
        panel_frac=cfg.panel_frac,
        fen=cfg.fen,
        local_color=cfg.local_color,
        tempo=cfg.tempo,
        local_player=Human(),
        opponent=Computer(cfg.engine_path, cfg.response_speed)
    ).run()
