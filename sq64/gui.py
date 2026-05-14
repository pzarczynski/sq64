import logging
from dataclasses import dataclass
from pathlib import Path

import pygame

from sq64.core import (
    KING_TO_ROOK_SQ,
    PIECE_NONE,
    QUEEN,
    Color,
    Move,
    Piece,
    Square,
    sq_from_idx,
    sq_make,
    sq_to_idx,
)
from sq64.game import Game

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Config:
    fen: str = Game.STARTING_FEN
    caption: str = "Chess"
    assets_dir: Path = Path("assets")
    default_view: Color = 1
    window_size: tuple[int, int] = (800, 800)
    

class PieceSprite(pygame.sprite.Sprite):
    image: pygame.Surface
    rect: pygame.Rect
    
    def __init__(self, img_path: Path, piece: Piece, sq: Square) -> None:
        super().__init__()
        self.idx    = sq_to_idx(sq)
        self.piece  = piece
        self.image_orig = pygame.image.load(img_path).convert_alpha()

    def rescale(self, sq_rect: pygame.Rect, scale: float) -> None:
        piece_size = max(1, int(sq_rect.width * scale))
        self.image = pygame.transform.smoothscale(self.image_orig, (piece_size, piece_size))
        self.update(sq_rect)
        
    def update_topleft(self, topleft: tuple[int, int]) -> None:
        self.rect.topleft = topleft
        
    def update(self, sq_rect: pygame.Rect) -> None:
        self.rect = self.image.get_rect(center=sq_rect.center)


class GUI:
    def __init__(self, cfg: Config = Config()) -> None:
        pygame.init()

        self.game         = Game(cfg.fen)
        self.assets_dir   = cfg.assets_dir
        self.current_view = cfg.default_view

        self.screen = pygame.display.set_mode(cfg.window_size, pygame.RESIZABLE)
        self.clock  = pygame.time.Clock()
        pygame.display.set_caption(cfg.caption)

        self.board_img_orig = pygame.image.load(self.board_img_path()).convert()

        self.sprites = pygame.sprite.Group()
        self._build_piece_sprites()
        self._relayout()
        
        self.selected_sprite = None

    def square_rect(self, idx) -> pygame.Rect:
        x = self.board_rect.left + int((idx % 8)        * self.square_size)
        y = self.board_rect.top  + int((7 - (idx // 8)) * self.square_size)
        s = int(self.square_size)
        return pygame.Rect(x, y, s, s)

    def piece_img_path(self, piece) -> Path:
        color_name = "white" if piece.color else "black"
        return self.assets_dir / color_name / f"{piece.type_name}.png"

    def board_img_path(self) -> Path:
        color_name = "white" if self.current_view else "black"
        return self.assets_dir / color_name / "board.png"

    def _build_piece_sprites(self) -> None:
        self.sprites.empty()
        for sq, piece in self.game:
            if piece is not Piece.NONE:
                img_path = self.piece_img_path(piece)
                self.sprites.add(PieceSprite(img_path, piece, sq))

    def _relayout(self) -> None:
        win_w, win_h = self.screen.get_size()
        board_px     = min(win_w, win_h)
        left         = (win_w - board_px) // 2
        top          = (win_h - board_px) // 2

        self.square_size = board_px / 8
        self.board_rect  = pygame.Rect(left, top, board_px, board_px)
        self.board_img   = pygame.transform.smoothscale(self.board_img_orig, self.board_rect.size)

        for sprite in self.sprites:
            sprite.rescale(self.square_rect(sprite.idx), scale=0.9)

    def draw(self) -> None:
        self.screen.fill((24, 24, 24))
        self.screen.blit(self.board_img, self.board_rect.topleft)
        
        if self.selected_sprite is not None:
            sel_rect = self.square_rect(self.selected_sprite.idx)
            highlight = pygame.Surface((sel_rect.width, sel_rect.height), pygame.SRCALPHA)
            highlight.fill((255, 255, 0, 80))
            self.screen.blit(highlight, sel_rect.topleft)
            pygame.draw.rect(self.screen, (255, 255, 0), sel_rect, width=3)
            
        for sprite in self.sprites:
            sprite.update(self.square_rect(sprite.idx))
        
        self.sprites.draw(self.screen)
        pygame.display.flip()
        
    def sprite_at(self, pos) -> PieceSprite | None:
        for sprite in reversed(self.sprites.sprites()):
            if sprite.rect.collidepoint(pos):
                return sprite
        return None

    def nearest_square(self, pos):
        x, y = pos
        if not self.board_rect.collidepoint(pos): return None
        rank = -int((y - self.board_rect.top)  / self.square_size) + 7
        file =  int((x - self.board_rect.left) / self.square_size)
        return sq_make(file, rank)
    
    def move_sprite(self, sprite: PieceSprite, to: Square) -> bool:
        frm = sq_from_idx(sprite.idx)
        
        promo = QUEEN if sprite.piece.can_promote(to) else PIECE_NONE
        move = Move(frm, to, promo)
        
        if move in self.game.legal_moves():
            if move.is_en_passant(self.game):
                ep_capture_idx = to - 16 if self.game.color else to + 16
                for other in self.sprites:
                    if other.idx == sq_to_idx(ep_capture_idx):
                        self.sprites.remove(other)
                        break
                    
            elif move.is_capture(self.game):
                for other in self.sprites:
                    if other.idx == sq_to_idx(to):
                        self.sprites.remove(other)
                        break
            
            elif move.is_castling(self.game):
                rook_frm, rook_to = map(sq_to_idx, KING_TO_ROOK_SQ[to])
                rook_sprite = next(s for s in self.sprites if s.idx == rook_frm)
                rook_sprite.idx = rook_to
                
            if move.is_promotion():
                promoted_piece = Piece.make(sprite.piece.color, move.promotion)
                sprite.image_orig = pygame.image.load(self.piece_img_path(promoted_piece)).convert_alpha()
                sprite.piece = promoted_piece
                self._relayout()
                        
            sprite.idx = sq_to_idx(to)
            self.game.play(move)
            logger.info(f"played move '{move}' in position '{self.game}'")
            return True
        else:
            logger.info(f"invalid move '{move}' in position '{self.game}'")
        
        return False
    
    def handle_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            
        elif event.type == pygame.VIDEORESIZE:
            self._relayout()
            
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            sprite = self.sprite_at(event.pos)
            
            if self.selected_sprite is None and sprite is not None and sprite.piece.color == self.game.color:
                self.selected_sprite = sprite
            
            elif self.selected_sprite is not None and self.selected_sprite.piece.color == self.game.color:
                to = self.nearest_square(event.pos)
                if to is not None:
                    self.move_sprite(self.selected_sprite, to)
                else:
                    logger.info(f"invalid target square for move in position '{self.game}'")
                
                self.selected_sprite = None
        
    def loop(self):
        self.running = True
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()