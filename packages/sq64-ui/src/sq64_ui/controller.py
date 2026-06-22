import pygame
from sq64_chess import WHITE, Color, PieceType, Square
from sq64_chess.game import Game, Tempo

from .player import Player
from .views import BoardViewer, Menu, OutcomeOverlay, PromotionOverlay


class Controller:
    """Controller class that manages the game state, handles user interactions, and synchronizes the views accordingly."""
    _board: BoardViewer | None
    _menu: Menu | None
    _promo: PromotionOverlay | None
    _outcome: OutcomeOverlay | None

    _fen: str
    _local: Player
    _opponent: Player
    _needs_promo: bool
    _game: Game
    _ended: bool
    _players: tuple[Player, Player]
    _curr_player: Player

    def __init__(
        self,
        local: Player,
        opponent: Player,
        fen: str,
        local_color: Color,
        tempo: Tempo,
    ) -> None:
        self._board = None
        self._menu = None
        self._promo = None
        self._outcome = None

        self._fen = fen
        self._local = local
        self._opponent = opponent
        self._needs_promo = False

        self.start_game(local_color, tempo)

    def set_views(
        self, board: BoardViewer, menu: Menu, promo: PromotionOverlay, outcome: OutcomeOverlay,
    ) -> None:
        """Sets the view components for the controller and synchronizes them with the current game state."""
        self._board = board
        self._menu = menu
        self._promo = promo
        self._outcome = outcome
        self.sync_views()

    @property
    def ended(self) -> bool: return self._ended
    @property
    def orient(self) -> Color: return self._players[WHITE] == self._local
    @property
    def needs_promo(self) -> bool: return self._needs_promo

    def start_game(self, local_color: Color, tempo: Tempo) -> None:
        """Starts a new game with the given local color and time control."""
        self._game = Game(self._fen, (tempo(), tempo()))

        # this is heavy operatiion so we need to be careful
        self._ended = self._game.outcome is not None

        self._players = (
            (self._opponent, self._local) if local_color
            else (self._local, self._opponent)
        )
        for p in self._players: p.reset()

        self._curr_player = self._players[self._game.color]
        self._curr_player.begin(self._game)

    def handle_sq_click(self, sq: Square) -> None:
        if self._curr_player and not self.ended:
            self._curr_player.update_sq(sq)
            self.sync_views()

    def handle_promo_select(self, pt: PieceType) -> None:
        if self._curr_player and not self.ended:
            self._curr_player.update_promo(pt)
            self._needs_promo = False
            self.sync_views()

    def handle_new_game(self, local_color: Color, tempo: Tempo) -> None:
        self.start_game(local_color, tempo)
        self.sync_views()

    def handle_copy_fen(self) -> None:
        if self._game: pygame.scrap.put_text(self._game.fen())

    def handle_copy_pgn(self) -> None:
        if self._game: pygame.scrap.put_text(self._game.pgn())

    def update(self, dt: int) -> None:
        """Updates the game state based on the current player's move and synchronizes the views accordingly."""
        if self.ended: return

        if self._game.is_time_over():
            self._ended = True
            self.sync_views()
            return

        self._game.tick(dt)
        move = self._curr_player.getmove()

        if move and move in self._game.legal_moves():
            self._game.play(move)
            self._ended = self._game.outcome is not None
            self._curr_player = self._players[self._game.color]
            self._curr_player.begin(self._game)
            self.sync_views()

        self._sync_clocks()

    def sync_views(self) -> None:
        """Synchronizes the board, promotion overlay, and outcome overlay views with the current game state."""
        if not self._board or not self._menu: raise RuntimeError("Views not set")

        self._needs_promo = self._curr_player.wants_promo

        last_move = (
            self._game.history[-1].move.to
            if self._game.history and self._game.history[-1].move
            else None
        )
        check_sq = self._game.king_square(self._game.color) if self._game.is_check() else None
        sel_sq = self._curr_player.selected_sq

        self._board.sync(iter(self._game), self.orient, check_sq, last_move, sel_sq)

        if self._promo and self._needs_promo:
            self._promo.sync(self._game.color)

        if self._outcome:
            msg = None
            if self.ended and self._game.outcome:
                msg = self._game.outcome.pretty(not self._game.color)
            self._outcome.sync(msg)

    def _sync_clocks(self) -> None:
        if not self._menu: raise RuntimeError("Menu view not set")
        self._menu.sync_clocks(
            str(self._game.control[not self.orient]),
            str(self._game.control[self.orient]),
        )
