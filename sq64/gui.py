import logging
from collections import namedtuple
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pygame

from sq64 import core as sq64
from sq64.core import Board, Move, Piece, Square, State
from sq64.uci import UCI

logging.basicConfig(level=logging.INFO)


@dataclass(slots=True, frozen=True)
class RGB:
    BLACK    = (0, 0, 0)
    WHITE    = (255, 255, 255)
    GRAY     = (50, 50, 50)
    DARKGRAY = (30, 30, 30)
    YELLOW   = (255, 255, 0)
    RED      = (255, 0, 0)
    GREEN    = (0, 255, 0)
    BROWN    = (139, 69, 19)


@dataclass(slots=True)
class Time:
    time_ms: int
    incr_ms: int

    @classmethod
    def natural(cls, minutes: int, incr: int) -> "Time":
        """a natural way to specify time control (minutes + increment in seconds)"""
        return cls(minutes * 60000, incr * 1000)  # to ms

    @property
    def minutes(self) -> int: return self.time_ms // 60000
    @property
    def seconds(self) -> int: return (self.time_ms // 1000) % 60
    @property
    def increment(self) -> int: return self.incr_ms // 1000

    def __str__(self) -> str: return f"{self.minutes:02d}:{self.seconds:02d}"
    def __iter__(self) -> Iterator[int]: return iter((self.time_ms, self.incr_ms))


class Tempo(Enum):
    # factories so that the time is not shared between instances
    BULLET = ('bullet', lambda: Time.natural( 1, 0))
    BLITZ  = ('blitz',  lambda: Time.natural( 3, 2))
    RAPID  = ('rapid',  lambda: Time.natural(10, 5))

    @property
    def value(self) -> str: return self.label

    def __init__(self, label: str, time_fn: Callable[[], Time]) -> None:
        self.label = label
        self.time_fn = time_fn

    def __str__(self) -> str:
        t = self.time_fn()
        return f"{t.minutes}\" + {t.increment}\'"


class Movetime(Enum):
    FAST   = ('fast',   lambda time, inc: int(min(time / 80 + inc * 0.5, time / 4)))
    NORMAL = ('normal', lambda time, inc: int(min(time / 40 + inc * 0.7, time / 2)))
    SLOW   = ('slow',   lambda time, inc: int(min(time / 30 + inc * 0.9, time * 0.9)))

    def __init__(self, label: str, movetime_fn: Callable[[int, int], int]) -> None:
        self.label = label
        self.movetime_fn = movetime_fn

    def __call__(self, time: int, inc: int) -> int: return self.movetime_fn(time, inc)


Outcome = Enum("Outcome", "CHECKMATE TIME_OVER STALEMATE THREEFOLD FIFTY_MOVES INSUFFICIENT")

class Game(Board):
    fullmoves: int
    halfmoves: int
    history: list[State]
    control: list[Time]

    def __init__(self, fen: str, control: list[Time]) -> None:
        super().__init__(fen)
        *_, fn, hc = fen.split()
        self.fullmoves, self.halfmoves = int(fn), int(hc)
        self.history = []
        self.control = control

    def is_insufficient_material(self) -> bool:
        pieces = [p for _, p in self]
        if len(pieces) == 2: return True  # only kings
        return len(pieces) == 3 and any(p.type in (sq64.BISHOP, sq64.KNIGHT) for p in pieces)

    def is_stalemate(self) -> bool: return not self.is_check() and not self.legal_moves()
    def is_checkmate(self) -> bool: return self.is_check() and not self.legal_moves()
    def is_threefold(self) -> bool: return sum(1 for s in self.history if s.hash == self.hash) >= 2
    def is_fifty_moves(self) -> bool: return self.halfmoves >= 100
    def is_time_over(self) -> bool: return self.control[self.color].time_ms <= 0

    def is_game_over(self) -> bool:
        return (self.is_time_over() or self.is_fifty_moves() or self.is_checkmate() or
                self.is_stalemate() or self.is_insufficient_material() or self.is_threefold())

    @property
    def outcome(self) -> Outcome | None:
        if self.is_checkmate(): return Outcome.CHECKMATE
        if self.is_time_over(): return Outcome.TIME_OVER
        if self.is_stalemate(): return Outcome.STALEMATE
        if self.is_threefold(): return Outcome.THREEFOLD
        if self.is_fifty_moves(): return Outcome.FIFTY_MOVES
        if self.is_insufficient_material(): return Outcome.INSUFFICIENT
        return None

    def play(self, move: Move) -> None:
        self.history.append(super().push(move))
        self.fullmoves += self.color ^ 1  # increment after black

        if self[move.to] or self[move.frm].type == sq64.PAWN:
            self.halfmoves = 0
        else:
            self.halfmoves += 1

    def fen(self) -> str: return super().fen() + f" {self.fullmoves} {self.halfmoves}"

    def __iter__(self) -> Iterator[tuple[Square, Piece]]:
        yield from ((Square(sq), p) for sq, p in super().__iter__())


class Player:
    def begin(self, game: Game) -> None: return
    def reset(self) -> None: return
    def quit(self) -> None: return
    def update(
        self, action: "BoardAction", sq: Square | None, promo: sq64.PieceType | None
    ) -> None: return
    def getmove(self) -> Move | None: return
    @property
    def wants_promo(self) -> bool: return False


class Human(Player):
    _move: Move | None
    _wants_promo: bool
    _selected_sq: Square | None
    _game: Game | None

    def __init__(self) -> None:
        self.reset()

    def _clear(self) -> None:
        self._selected_sq = None
        self._move = None
        self._wants_promo = False

    def reset(self) -> None:
        self._game = None
        self._clear()

    def _handle_select(self, sq: Square) -> None:
        assert self._game
        piece = self._game[sq]
        if self._selected_sq and (not piece or piece.color != self._game.color):
            self._move = Move(self._selected_sq, sq)
            self._wants_promo = self._game[self._selected_sq].can_promote(sq)
        else:
            self._selected_sq = sq

    def update(
        self, action: "BoardAction", sq: Square | None, promo: sq64.PieceType | None
    ) -> None:
        assert self._game

        match action:
            case BoardAction.NONE:
                return
            case BoardAction.SELECT if sq:
                self._handle_select(sq)
            case BoardAction.PROMO if promo:
                assert self._move is not None
                self._move = Move(self._move.frm, self._move.to, promo)

    def begin(self, game: Game) -> None:
        self._game = game
        self._clear()

    @property
    def wants_promo(self) -> bool: return self._wants_promo

    def getmove(self) -> Move | None:
        return self._move if not self._wants_promo else None


class Computer(Player):
    _movetime: Movetime
    _uci: UCI

    def __init__(self, path: str, response_speed: Movetime) -> None:
        self._movetime = response_speed
        self._uci = UCI(path)

    def quit(self) -> None: self._uci.quit()
    def reset(self) -> None: self._uci.newgame()

    def begin(self, game: Game) -> None:
        if not self._uci.thinking:
            time, inc = game.control[game.color]
            movetime = self._movetime(time, inc)
            self._uci.go(game.fen(), movetime=movetime)

    def getmove(self) -> Move | None:
        return Move.parse(self._uci.bestmove) if self._uci.bestmove else None


BoardAction = Enum("BoardAction", "NONE SELECT PROMO")

class BoardView:
    _promo: sq64.PieceType | None
    _promo_rects: list[tuple[int, pygame.Rect]]

    def __init__(self, screen: pygame.Surface, assets_dir: Path) -> None:
        self._screen = screen
        self.clear()

        self._board_img_orig = [
            pygame.image.load(assets_dir / "black" / "board.png").convert(),
            pygame.image.load(assets_dir / "white" / "board.png").convert()
        ]

        self._piece_imgs_orig = {
            p: self._load_piece_img(assets_dir, p) for p
            in sq64.PIECES[0][1:] + sq64.PIECES[1][1:]
        }

    def clear(self) -> None:
        self._sq = None
        self._promo = None
        self._promo_rects = []

    @staticmethod
    def _load_piece_img(
        assets_dir: Path, piece: Piece
    ) -> pygame.Surface:
        path = assets_dir / sq64.color_name(piece.color) / f"{piece.name}.png"
        return pygame.image.load(path).convert_alpha()

    def set_orientation(self, color: sq64.Color) -> None:
        self._orient = color

    def square_at(self, pos: tuple[int, int]) -> Square | None:
        if not self._board_rect.collidepoint(pos): return None
        x_rel, y_rel = (pos[0] - self._left, pos[1] - self._top)  # relative board coords
        rank = int(y_rel / (self._size / 8))
        rel_rank = 7 - rank if self._orient else rank
        return Square.make(int(x_rel / (self._size / 8)), rel_rank)

    def handle_click(self, event: pygame.Event) -> BoardAction:
        for pt, rect in self._promo_rects:
            if rect.collidepoint(event.pos):
                self._promo = pt
                self._promo_rects.clear()
                return BoardAction.PROMO

        if sq := self.square_at(event.pos):
            self._sq = sq
            return BoardAction.SELECT
        return BoardAction.NONE

    def draw(self, game: Game, draw_promo: bool) -> None:
        self._screen.fill(RGB.DARKGRAY)
        self._screen.blit(self._board_img, (self._left, self._top))
        s = self._size / 8

        lastmove = game.history[-1].move if game.history else None

        for sq, piece in game:
            rel_rank = 7 - sq.rank if self._orient else sq.rank
            sq_rect = pygame.Rect(self._left + sq.file*s, self._top + rel_rank*s, s, s)
            img = self._piece_imgs[piece]
            self._screen.blit(img, img.get_rect(center=sq_rect.center))

            if lastmove and sq == lastmove.to:
                pygame.draw.rect(self._screen, RGB.GREEN, sq_rect, width=5)
            elif sq == self._sq:
                pygame.draw.rect(self._screen, RGB.YELLOW, sq_rect, width=5)
            elif game.is_check() and sq == game.king_square(game.color):
                pygame.draw.rect(self._screen, RGB.RED, sq_rect, width=5)

        outcome = game.outcome

        if draw_promo and not outcome:
            x = self._left + self._size / 4
            y = self._top + self._size / 2 - s / 2
            pygame.draw.rect(self._screen, RGB.GRAY, (x, y, self._size / 2, s))

            for i, p in enumerate(Piece.promotions(game.color)):
                rect = pygame.Rect(x + i*s, y, s, s)
                self._promo_rects.append((p.type, rect))
                self._screen.blit(self._piece_imgs[p], rect.topleft)

        if outcome:
            overlay = pygame.Surface((self._size, self._size), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self._screen.blit(overlay, (self._left, self._top))

            enemy_name = sq64.color_name(game.color ^ 1).capitalize()
            match outcome:
                case Outcome.CHECKMATE:
                    text = f"{enemy_name} wins by checkmate"
                case Outcome.TIME_OVER:
                    text = f"{enemy_name} wins on time"
                case Outcome.STALEMATE:
                    text = "Draw by stalemate"
                case Outcome.THREEFOLD:
                    text = "Draw by threefold repetition"
                case Outcome.FIFTY_MOVES:
                    text = "Draw by fifty-move rule"
                case Outcome.INSUFFICIENT:
                    text = "Draw by insufficient material"

            surf = self._font.render(text, True, RGB.WHITE)
            self._screen.blit(surf, surf.get_rect(center=self._board_rect.center))

    def relayout(self, top: float, left: float, size: float) -> None:
        self._top = top
        self._left = left
        self._size = size
        self._font = pygame.font.SysFont(None, int(size / 10))

        self._board_img = pygame.transform.scale(
            self._board_img_orig[self._orient], (self._size, self._size)
        )
        self._board_rect = pygame.Rect(left, top, self._size, self._size)

        ps = 0.9 * size / 8
        self._piece_imgs = {
            p: pygame.transform.smoothscale(img, (ps, ps))
            for p, img in self._piece_imgs_orig.items()
        }

    @property
    def promo(self) -> sq64.PieceType | None: return self._promo
    @property
    def square(self) -> Square | None: return self._sq


MenuAction = Enum("MenuAction", "NONE SELECT_TIME NEW_GAME")
SurfRect = namedtuple("SurfRect", "surf rect")

class Menu:
    _state: MenuAction
    _color: sq64.Color | None
    _tempo: Tempo | None

    def __init__(self, screen: pygame.Surface, assets_dir: Path) -> None:
        self._screen = screen
        self._state = MenuAction.NONE
        self._color = None
        self._tempo = None

        self._wk_img = pygame.image.load(assets_dir / "white/king.png").convert_alpha()
        self._bk_img = pygame.image.load(assets_dir / "black/king.png").convert_alpha()

    def _king_surf(
        self, x: float, y: float, img: pygame.Surface, size: float
    ) -> SurfRect:
        surf = pygame.transform.smoothscale(img, (size, size))
        rect = surf.get_rect(center=(x, y))
        return SurfRect(surf, rect)

    def _tempo_surf(
        self, tempo: Tempo, x: float, y: float, w: float, h: float
    ) -> SurfRect:
        surf = self._font_s.render(f"{tempo}", True, RGB.WHITE)
        rect = pygame.Rect(x - w / 2, y - h / 2, w, h)
        return SurfRect(surf, rect)

    def handle_click(self, pos: tuple[int, int]) -> MenuAction:
        match self._state:
            case MenuAction.NONE:
                if self.btn_wk.rect.collidepoint(pos):
                    self._color = sq64.WHITE
                    self._state = MenuAction.SELECT_TIME
                elif self.btn_bk.rect.collidepoint(pos):
                    self._color = sq64.BLACK
                    self._state = MenuAction.SELECT_TIME

            case MenuAction.SELECT_TIME:
                self._tempo = None
                self._state = MenuAction.NONE
                for tempo, btn in self.btn_tempo.items():
                    if btn.rect.collidepoint(pos): self._tempo = tempo
                if self._tempo:
                    return MenuAction.NEW_GAME

        return self._state


    def draw(self, game: Game, orient: sq64.Color) -> None:
        tb = self._font_l.render(str(game.control[0]), True, RGB.WHITE)
        tw = self._font_l.render(str(game.control[1]), True, RGB.WHITE)

        mid_x = self._left + self._width / 2
        tuppr = (mid_x, self._top + self._height * 0.1)
        tdown = (mid_x, self._top + self._height * 0.9)
        self._screen.blit(tb, tb.get_rect(center=tuppr if orient else tdown))
        self._screen.blit(tw, tw.get_rect(center=tdown if orient else tuppr))

        match self._state:
            case MenuAction.NONE:
                self._screen.blit(*self.btn_bk)
                self._screen.blit(*self.btn_wk)
            case MenuAction.SELECT_TIME:
                for _, (t_surf, btn) in self.btn_tempo.items():
                    pygame.draw.rect(self._screen, RGB.GRAY, btn, border_radius=5)
                    self._screen.blit(t_surf, t_surf.get_rect(center=btn.center))

    def relayout(self, top: float, left: float, width: float, height: float) -> None:
        self._top = top
        self._left = left
        self._width = width
        self._height = height

        ps = min(width / 3, height / 9)
        self._font_l = pygame.font.SysFont(None, int(0.9 * ps))
        self._font_s = pygame.font.SysFont(None, int(0.5 * ps))

        mid_x, mid_y = (self._left + self._width / 2, self._top + self._height / 2)
        self.btn_bk = self._king_surf(mid_x + ps / 2, mid_y, self._bk_img, ps)
        self.btn_wk = self._king_surf(mid_x - ps / 2, mid_y, self._wk_img, ps)

        self.btn_tempo = {
            tempo: self._tempo_surf(tempo, mid_x, mid_y + ps * 0.7 * (i - 1), 2 * ps, 0.6 * ps)
            for i, tempo in enumerate([Tempo.BULLET, Tempo.BLITZ, Tempo.RAPID])
        }

    @property
    def color(self) -> sq64.Color | None: return self._color
    @property
    def tempo(self) -> Tempo | None: return self._tempo


@dataclass(slots=True)
class Config:
    engine_path: str  = "./sq64.sh"
    assets_dir:  Path = Path("assets")
    panel_frac: float = 0.2
    height: float     = 800.0

    fen:         str   = Board.STARTING_FEN
    tempo:       Tempo = Tempo.BLITZ
    local_color: int   = sq64.WHITE
    response_speed: Movetime = Movetime.FAST


class App:
    players: tuple[Player, Player]

    def __init__(
        self,
        height: float,
        panel_frac: float,
        assets_dir: Path,
        fen: str,
        local_color: int,
        tempo: Tempo,
        local_player: Player,
        opponent: Player
    ) -> None:
        pygame.init()
        self.panel_frac = panel_frac

        # height = board_width = width * (1 - 2 * panel_frac)
        width = height / (1 - 2 * self.panel_frac)

        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption("sq64 GUI")

        self.fen = fen
        self.local_color = local_color
        self.tempo = tempo

        self.local_player = local_player
        self.opponent = opponent

        self.board_view = BoardView(self.screen, assets_dir)

        self.menu = Menu(self.screen, assets_dir)
        self.clock = pygame.time.Clock()

        self.board_view.set_orientation(local_color)
        self.relayout(width, height)

    def start_game(self, local_color: int, tempo: Tempo) -> Player:
        self.local_color = local_color
        self.tempo = tempo

        self.players = ((self.opponent, self.local_player) if local_color else
                        (self.local_player, self.opponent))

        self.game = Game(self.fen, [tempo.time_fn(), tempo.time_fn()])
        for p in self.players: p.reset()

        self.board_view.set_orientation(self.local_color)
        self.relayout(self.width, self.height)

        player = self.players[self.game.color]
        player.begin(self.game)
        return player

    def run(self) -> None:
        running = True
        player = self.start_game(self.local_color, self.tempo)

        try:
            while running:
                outcome = self.game.outcome
                ended = bool(outcome)

                c = self.game.color

                if not ended:
                    self.game.control[c].time_ms -= self.clock.tick(60)

                for event in pygame.event.get():
                    match event.type:
                        case pygame.QUIT:
                            running = False
                        case pygame.VIDEORESIZE:
                            self.relayout(*event.size)
                        case pygame.MOUSEBUTTONDOWN if event.button == 1:
                            if not ended:
                                action = self.board_view.handle_click(event)
                                if action != BoardAction.NONE:
                                    player.update(action, self.board_view.square, self.board_view.promo)

                            if self.menu.handle_click(event.pos) == MenuAction.NEW_GAME:
                                player = self.start_game(self.menu.color, self.menu.tempo)

                move = player.getmove()

                if not ended and move and move in self.game.legal_moves():
                    self.game.play(move)
                    self.game.control[c].time_ms += self.game.control[c].incr_ms
                    self.board_view.clear()

                    # switch player and begin turn
                    player = self.players[self.game.color]
                    player.begin(self.game)

                self.board_view.draw(self.game, draw_promo=player.wants_promo)
                self.menu.draw(self.game, orient=self.local_color)
                pygame.display.flip()

        finally:
            for p in self.players: p.quit()
            pygame.quit()

    def relayout(self, w: float, h: float) -> None:
        self.height = h
        self.width  = w
        bs = min(w * (1 - 2 * self.panel_frac), h)
        pw = (w - bs) / 2
        top = (h - bs) / 2

        self.board_view.relayout(top, pw, bs)
        self.menu.relayout(top, bs + pw, pw, bs)

if __name__ == "__main__":
    cfg = Config()
    App(
        height=cfg.height,
        panel_frac=cfg.panel_frac,
        assets_dir=cfg.assets_dir,
        fen=cfg.fen,
        local_color=cfg.local_color,
        tempo=cfg.tempo,
        local_player=Human(),
        opponent=Computer(cfg.engine_path, cfg.response_speed)
    ).run()
