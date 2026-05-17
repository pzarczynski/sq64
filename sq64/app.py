import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pygame

from sq64.core import BLACK, WHITE, Color, Move, Piece, Square
from sq64.engine import get_best_move
from sq64.game import Game

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


class Player(ABC):
    @abstractmethod
    def handle_event(self, event: pygame.Event, game: Game, view: "GameView") -> Move | None: ...


class Human(Player):
    def __init__(self) -> None:
        self.selected_sq:  Square | None = None
        self.promotion_move: Move | None = None

    def handle_event(self, event: pygame.Event, game: Game, view: "GameView") -> Move | None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None

        pos = event.pos

        if self.promotion_move:
            piece_type = view.get_promotion_choice(pos)
            if piece_type:
                move = Move(self.promotion_move.frm, self.promotion_move.to, piece_type)
                self._reset_state()
                return move
            return None

        clicked_sq = view.square_at(pos)
        if clicked_sq is None: return None

        clicked_piece = next((Piece(p) for sq, p in game if sq == clicked_sq), Piece.NONE)

        if clicked_piece != Piece.NONE and clicked_piece.color == game.color:
            self.selected_sq = clicked_sq
            return None

        if self.selected_sq is not None:
            move = Move(self.selected_sq, clicked_sq)
            moving_piece = next((Piece(p) for sq, p in game if sq == self.selected_sq), Piece.NONE)
            
            if moving_piece and moving_piece.can_promote(clicked_sq):
                self.promotion_move = move
            else:
                self._reset_state()
                return move

        return None

    def _reset_state(self):
        self.selected_sq = None
        self.promotion_move = None


class Computer(Player):
    def __init__(self, depth: int = 10, time_limit: float = 0.5):
        self.depth = depth
        self.time_limit = time_limit
        self.is_thinking = False
        self.best_move = None
        self.thread = None

    def handle_event(self, event: pygame.Event, game: 'Game', view: 'GameView') -> Move | None:
        if self.best_move:
            move = self.best_move
            self.best_move = None
            self.is_thinking = False
            return move

        if not self.is_thinking:
            self.is_thinking = True
            
            def think():
                info = get_best_move(game.copy(), self.depth, self.time_limit)
                s = f'best_move={info['best_move']}'
                if 'depth' in info: s += f'; depth={info['depth']}'
                if 'nps'   in info: s += f'; nps={info['nps']}'
                if 'nodes' in info: s += f'; nodes={info['nodes']}'
                logger.info(s)
                pygame.event.post(pygame.event.Event(pygame.USEREVENT))
                self.best_move = info['best_move']

            self.thread = threading.Thread(target=think, daemon=True)
            self.thread.start()

        return None


@dataclass(slots=True, frozen=True)
class Config:
    fen: str = Game.STARTING_FEN
    caption: str = "Chess"
    assets_dir: Path = Path("assets")
    default_view: Color = WHITE
    window_size: tuple[int, int] = (1100, 800)
    players: tuple[Player, Player] = (Computer(depth=10, time_limit=2.0), Human())
    time: int = 10 * 60 * 1000


class GameView:
    def __init__(self, screen: pygame.Surface, cfg: Config, current_view: Color = WHITE):
        self.screen = screen
        self.square_size = 0
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        color_name = "white" if current_view else "black"
        self.board_img_orig = pygame.image.load(cfg.assets_dir / color_name / "board.png").convert()
        self.piece_imgs = {piece: self.load_piece_img(piece, cfg.assets_dir) for piece in Piece}
        self.promotion_rects: list[tuple[int, pygame.Rect]] = []
        self.current_view = current_view
        
        pygame.font.init()
        self.font = pygame.font.Font(size=0)
        
        self.btn_play_white = pygame.Rect(0, 0, 0, 0)
        self.btn_play_black = pygame.Rect(0, 0, 0, 0)
        self.btn_resign     = pygame.Rect(0, 0, 0, 0)

        self.ui_w_frac     = 0.20
        self.button_w_frac = 0.25
        self.button_h_frac = 0.07
        
    def format_time(self, ms: int) -> str:
        ms = max(0, ms)
        return f"{(ms // 1000) // 60:02d}:{(ms // 1000) % 60:02d}"

    def load_piece_img(self, piece: Piece, assets_dir: Path) -> pygame.Surface:
        if piece == Piece.NONE: return pygame.Surface((1, 1), pygame.SRCALPHA)
        color_dir = "white" if piece.color else "black"
        path = assets_dir / color_dir / f"{piece.type_name}.png"
        return pygame.image.load(path).convert_alpha()

    def relayout(self, size: tuple[int, int]):
        win_w, win_h = size
        ui_space = int(win_w * self.ui_w_frac)

        board_px = int(min(win_w - ui_space, win_h))
        left = max(0, (win_w - ui_space - board_px) // 2)
        top  = max(0, (win_h - board_px) // 2)

        self.square_size = board_px / 8.0
        self.board_rect  = pygame.Rect(left, top, board_px, board_px)
        self.board_img   = pygame.transform.smoothscale(self.board_img_orig, self.board_rect.size)
        self.font = pygame.font.Font(size=max(10, int(self.square_size * 0.5)))

    def square_at(self, pos: tuple[int, int]) -> Square | None:
        if not self.board_rect.collidepoint(pos): return None
        x, y = pos
        r = int((y - self.board_rect.top)  / self.square_size)
        rank = (7 - r) if self.current_view else r
        file = int((x - self.board_rect.left) / self.square_size)
        return Square.make(file, rank)

    def get_square_rect(self, sq: Square) -> pygame.Rect:
        idx = sq.to_idx()
        x = self.board_rect.left + int((idx % 8) * self.square_size)
        y = self.board_rect.top  + int(((7 - (idx // 8)) if self.current_view else (idx // 8)) * self.square_size)
        s = int(self.square_size)
        return pygame.Rect(x, y, s, s)

    def get_promotion_choice(self, pos: tuple[int, int]):
        for piece_type, rect in self.promotion_rects:
            if rect.collidepoint(pos):
                return piece_type
        return None

    def draw(self, game: Game, current_player: Player | None, time_w: int, time_b: int, is_game_over: bool, msg: str) -> None:
        self.screen.fill((24, 24, 24))
        self.screen.blit(self.board_img, self.board_rect.topleft)

        if game.history:
            last_move_rect = self.get_square_rect(Square(game.history[-1].move.to))
            pygame.draw.rect(self.screen, (0, 255, 0), last_move_rect, width=3)

        if game.is_check():
            king_rect = self.get_square_rect(Square(game.king_squares[game.color]))
            pygame.draw.rect(self.screen, (255, 0, 0), king_rect, width=3)

        if current_player and hasattr(current_player, 'selected_sq') and current_player.selected_sq is not None:
            selected_rect = self.get_square_rect(current_player.selected_sq)
            pygame.draw.rect(self.screen, (255, 255, 0), selected_rect, width=3)

        for sq, piece in ((Square(i), Piece(p)) for i, p in game):
            if piece != Piece.NONE:
                rect = self.get_square_rect(sq)
                img = self.piece_imgs[piece]
                
                piece_size = max(1, int(rect.width * 0.9))
                scaled_img = pygame.transform.smoothscale(img, (piece_size, piece_size))
                
                self.screen.blit(scaled_img, scaled_img.get_rect(center=rect.center))

        if current_player and hasattr(current_player, 'promotion_move') and current_player.promotion_move:
            self._draw_promotion_dialog(game.color)
            
        self._draw_ui(time_w, time_b, is_game_over, msg)
        pygame.display.flip()
            
    def _draw_ui(self, time_w: int, time_b: int, is_game_over: bool, msg: str):
        b_w = self.board_rect.width
        b_h = self.board_rect.height

        ui_x = self.board_rect.right + max(6, int(b_w * 0.02))

        time_top_y = self.board_rect.top + int(b_h * 0.01)
        text_b = self.font.render(self.format_time(time_b), True, (200, 200, 200))
        self.screen.blit(text_b, (ui_x, time_top_y))

        time_bot_y = self.board_rect.bottom - int(b_h * 0.06)
        text_w = self.font.render(self.format_time(time_w), True, (255, 255, 255))
        self.screen.blit(text_w, (ui_x, time_bot_y))

        btn_w   = max(24, int(b_w * self.button_w_frac))
        btn_h   = max(20, int(b_h * self.button_h_frac))
        btn_min = min(btn_w, btn_h)
        
        mid_y = int(self.board_rect.centery)
        self.btn_play_white = pygame.Rect(ui_x, mid_y - int(b_h * 0.08), btn_min, btn_min)
        self.btn_play_black = pygame.Rect(ui_x + btn_min * 1.3, mid_y - int(b_h * 0.08), btn_min, btn_min)
        self.btn_resign     = pygame.Rect(ui_x, mid_y + int(b_h * 0.01), btn_w, btn_h)

        btn_pc = btn_min * 0.8
        pygame.draw.rect(self.screen, (50, 150, 50), self.btn_play_white, border_radius=5)
        self.screen.blit(pygame.transform.smoothscale(self.piece_imgs[Piece.WHITE_KING], (btn_pc, btn_pc)), 
                         (self.btn_play_white.x + int(btn_min * 0.1), 
                          self.btn_play_white.y + int((btn_h - self.font.get_height()) * 0.2)))
        
        pygame.draw.rect(self.screen, (50, 150, 50), self.btn_play_black, border_radius=5)
        self.screen.blit(pygame.transform.smoothscale(self.piece_imgs[Piece.BLACK_KING], (btn_pc, btn_pc)), 
                         (self.btn_play_black.x + int(btn_min * 0.1), 
                          self.btn_play_black.y + int((btn_h - self.font.get_height()) * 0.2)))

        if not is_game_over:
            pygame.draw.rect(self.screen, (150, 50, 50), self.btn_resign, border_radius=5)
            res_txt = self.font.render("Poddaj się", True, (255, 255, 255))
            self.screen.blit(res_txt, (self.btn_resign.x + int(btn_w * 0.05), 
                                       self.btn_resign.y + int((btn_h - self.font.get_height()) / 2)))
            
        if is_game_over:
            overlay = pygame.Surface((self.board_rect.width, self.board_rect.height))
            overlay.set_alpha(150)
            overlay.fill((0, 0, 0))
            self.screen.blit(overlay, self.board_rect.topleft)
            
            msg_txt = self.font.render(msg, True, (255, 215, 0))
            msg_rect = msg_txt.get_rect(center=self.board_rect.center)
            self.screen.blit(msg_txt, msg_rect)

    def _draw_promotion_dialog(self, color: Color) -> None:
        w, h = int(self.square_size * 4), int(self.square_size * 1)
        x = self.board_rect.centerx - w // 2
        y = self.board_rect.centery - h // 2
        but_width = w // 4

        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.screen.blit(overlay, (0, 0))

        self.promotion_rects.clear()

        for i, piece in enumerate(Piece.promotions(color)):
            rect = pygame.Rect(x + i * but_width, y, but_width, h)
            self.promotion_rects.append((piece.type, rect))

            pygame.draw.rect(self.screen, (100, 100, 100), rect)
            pygame.draw.rect(self.screen, (200, 200, 200), rect, width=2)

            img = self.piece_imgs[piece]
            piece_size = int(rect.width * 0.8)
            scaled_img = pygame.transform.smoothscale(img, (piece_size, piece_size))
            self.screen.blit(scaled_img, scaled_img.get_rect(center=rect.center))


class App:
    def __init__(self, cfg: Config = Config()):
        self.cfg = cfg
        
        pygame.init()
        pygame.display.set_caption(self.cfg.caption)
        
        self.screen = pygame.display.set_mode(self.cfg.window_size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        
        self.init_game(self.cfg)
    
    def init_game(self, cfg: Config, human_color: int = WHITE):
        self.game = Game()
        self.view = GameView(self.screen, self.cfg, current_view=human_color)
        self.time_white = self.time_black = cfg.time
        
        self.game_over = False
        self.result_msg = ""
        
        self.view_offset = 0 
        self.view_board = None
        
        human_player = Human()
        ai_player = Computer(depth=10, time_limit=2.0)
        self.players = [ai_player, human_player] if human_color else [human_player, ai_player]
        self.current_view = human_color
        self.view.relayout(self.screen.get_size())
            
    def handle_clicks(self, event):
        pos = event.pos
        if self.view.btn_play_white.collidepoint(pos):
            self.init_game(self.cfg, human_color=WHITE)
        elif self.view.btn_play_black.collidepoint(pos):
            self.init_game(self.cfg, human_color=BLACK)
        elif self.view.btn_resign.collidepoint(pos) and not self.game_over:
            winner = "Czarne" if self.game.color else "Białe"
            self.end_game(f"{winner} wygrywają (Poddanie)")

    def run(self):
        self.running = True
        while self.running:
            dt = self.clock.tick(60)
            current_player = self.players[self.game.color]

            if not self.game_over and self.view_offset == 0:
                if self.game.color:
                    self.time_white -= dt
                    if self.time_white <= 0:
                        self.end_game("Czarne wygrywają (Czas)")
                else:
                    self.time_black -= dt
                    if self.time_black <= 0:
                        self.end_game("Białe wygrywają (Czas)")

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.view.relayout(event.size)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if (self.view.btn_play_white.collidepoint(event.pos) or
                        self.view.btn_play_black.collidepoint(event.pos) or
                        self.view.btn_resign.collidepoint(event.pos)):
                        self.handle_clicks(event)
                        continue
                    
                if not self.game_over and self.view_offset == 0:
                    move = current_player.handle_event(event, self.game, self.view)
                    if move: self.execute_move(move)

            self.view.draw(
                self.game, 
                current_player, 
                self.time_white, 
                self.time_black, 
                self.game_over, 
                self.result_msg,
            )
            
        pygame.quit()

    def execute_move(self, move: Move):
        if move in self.game.legal_moves():
            self.game.play(move)
            if not self.game.legal_moves():
                if self.game.is_check():
                    winner = "Czarne" if self.game.color else "Białe"
                    self.end_game(f"{winner} wygrywają (Mat)")
                else:
                    self.end_game("Remis (Pat)")
            else:
                if isinstance(self.players[self.game.color], Human):
                    self.current_view = self.game.color
    
    def end_game(self, message: str):
        self.game_over = True
        self.result_msg = message