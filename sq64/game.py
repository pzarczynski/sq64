from sq64.core import Board, CastlingRights, Move, State, sq_from_str


class Game(Board):
    STARTING_FEN: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    history: list[State]

    def __init__(self, fen: str | None = None) -> None:
        self.from_fen(fen or self.STARTING_FEN)
        self.history = []

    def from_fen(self, fen: str) -> None:       
        board_fen, color, cr, ep, hc, fn = fen.split()
        
        castling_rights = CastlingRights.from_fen(cr)
        ep_sq = sq_from_str(ep) if ep != "-" else None
        color = 1 if color == 'w' else 0
        super().__init__(board_fen, castling_rights, ep_sq, color)
        
        self.halfmove_clock = int(hc)
        self.fullmove_number = int(fn)

    def play(self, move: Move) -> State:
        state = super().push(move)
        self.history.append(state)
        return state
    
    def pop(self) -> State:
        state = self.history.pop()
        return super().unpush(state)
        
    def fen(self) -> str:
        return super().fen() + f" {self.halfmove_clock} {self.fullmove_number}"