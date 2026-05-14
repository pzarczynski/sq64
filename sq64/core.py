from dataclasses import dataclass
from enum import IntEnum, IntFlag
from functools import reduce
from operator import or_

Color = int   # 0 = BLACK, 1 = WHITE
COLORS = [BLACK, WHITE] = range(2)

Square = int  # square in 0x88 representation
def sq_file(sq: Square)     -> int:    return sq & 7
def sq_rank(sq: Square)     -> int:    return sq >> 4
def sq_to_idx(sq: Square)   -> int:    return (sq & 7) | ((sq >> 4) << 3)
def sq_to_str(sq: Square)   -> str:    return f"{chr(sq_file(sq) + ord('a'))}{sq_rank(sq) + 1}"
def sq_from_str(s: str)     -> Square: return ((int(s[1]) - 1) << 4) | (ord(s[0]) - ord('a'))
def sq_from_idx(i: int)     -> Square: return (i & 7) | ((i >> 3) << 4)
def sq_mirror(sq: Square)   -> Square: return sq ^ 0x70
def sq_make(f: int, r: int) -> Square: return (r << 4) | f

KING_TO_ROOK_SQ = {
    0x02: (0x00, 0x03),
    0x06: (0x07, 0x05), 
    0x76: (0x77, 0x75),
    0x72: (0x70, 0x73)
}

PieceType = int
PieceInt  = int
def piece_make(color: Color, pt: PieceType) -> PieceInt:
    return (pt << 1) | (color & 1)

PIECE_TYPES = (PIECE_NONE, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING) = range(7)
PIECE_NAMES = ("none", "pawn", "knight", "bishop", "rook", "queen", "king")
PIECE_CHARS = (".", "p", "n", "b", "r", "q", "k")

STEPPING_PIECES = (KNIGHT, KING)
SLIDING_PIECES  = (BISHOP, ROOK, QUEEN)
PROMOTIONS      = (QUEEN,  ROOK, BISHOP, KNIGHT)

DELTAS = (
    (),                                        # NONE
    (),                                        # PAWN
    (-33, -31, -18, -14, 14, 18, 31, 33),      # KNIGHT
    (-17, -15,  15,  17),                      # BISHOP
    (-16, -1,   1,   16),                      # ROOK
    (-17, -16, -15, -1,  1,  15, 16, 17),      # QUEEN
    (-17, -16, -15, -1,  1,  15, 16, 17)       # KING
)
    
class Piece(IntEnum):
    NONE = 0

    BLACK_PAWN   = piece_make(BLACK, PAWN)
    BLACK_KNIGHT = piece_make(BLACK, KNIGHT)
    BLACK_BISHOP = piece_make(BLACK, BISHOP)
    BLACK_ROOK   = piece_make(BLACK, ROOK)
    BLACK_QUEEN  = piece_make(BLACK, QUEEN)
    BLACK_KING   = piece_make(BLACK, KING)

    WHITE_PAWN   = piece_make(WHITE, PAWN)
    WHITE_KNIGHT = piece_make(WHITE, KNIGHT)
    WHITE_BISHOP = piece_make(WHITE, BISHOP)
    WHITE_ROOK   = piece_make(WHITE, ROOK)
    WHITE_QUEEN  = piece_make(WHITE, QUEEN)
    WHITE_KING   = piece_make(WHITE, KING)

    @property
    def color(self) -> Color: return self.value & 1

    @property
    def type(self) -> PieceType: return self.value >> 1
    
    @property
    def type_name(self) -> str: return PIECE_NAMES[self.type]
    
    def can_promote(self, to: Square) -> bool:
        return self.type == PAWN and (sq_rank(to) == 0 or sq_rank(to) == 7)
    
    @classmethod
    def make(cls, color: Color, pt: PieceType) -> "Piece":
        return cls(piece_make(color, pt))

    @classmethod
    def from_char(cls, char: str) -> "Piece":
        pt = PIECE_CHARS.index(char.lower())
        return cls(piece_make(1 if char.isupper() else 0, int(pt)))
    
    def __str__(self) -> str:
        c = PIECE_CHARS[self.type]
        return c.upper() if self.color else c.lower()

@dataclass(slots=True)
class Move:        
    frm: Square
    to: Square
    promotion: PieceType = PIECE_NONE
    
    def is_castling(self, board: "Board") -> bool:
        moving_piece = board._board[self.frm]
        return (moving_piece >> 1) == KING and abs(self.to - self.frm) == 2
    
    def is_en_passant(self, board: "Board") -> bool:
        moving_piece = board._board[self.frm]
        return (moving_piece >> 1) == PAWN and self.to == board.ep_square
    
    def is_promotion(self) -> bool:
        return self.promotion != PIECE_NONE
    
    def is_capture(self, board: "Board") -> bool:
        if self.is_en_passant(board):
            return True
        target_piece = board._board[self.to]
        return target_piece != 0 and (target_piece & 1) != (board.color)

    def __str__(self) -> str:
        frm_file = chr(sq_file(self.frm) + ord('a'))
        frm_rank = str(sq_rank(self.frm) + 1)
        to_file  = chr(sq_file(self.to) + ord('a'))
        to_rank  = str(sq_rank(self.to) + 1)
        promo_str = f"{PIECE_CHARS[self.promotion].lower()}" if self.promotion else ""
        return f"{frm_file}{frm_rank}{to_file}{to_rank}{promo_str}"
        
    def __repr__(self) -> str:
        return f"Move({self})"
        
    def to_int(self) -> int:
        return (self.frm << 10) | (self.to << 3) | self.promotion
    

class CastlingRights(IntFlag):
    NONE            = 0
    WHITE_KINGSIDE  = 1 << 0
    WHITE_QUEENSIDE = 1 << 1
    BLACK_KINGSIDE  = 1 << 2
    BLACK_QUEENSIDE = 1 << 3
    
    WHITE_BOTH      = WHITE_KINGSIDE | WHITE_QUEENSIDE
    BLACK_BOTH      = BLACK_KINGSIDE | BLACK_QUEENSIDE
    ALL             = WHITE_BOTH     | BLACK_BOTH

    @classmethod
    def from_fen(cls, fen: str) -> "CastlingRights":
        mapping = {'K': cls.WHITE_KINGSIDE, 'Q': cls.WHITE_QUEENSIDE,
                   'k': cls.BLACK_KINGSIDE, 'q': cls.BLACK_QUEENSIDE}
        return reduce(or_, (mapping[c] for c in fen if c in mapping), cls.NONE)
    
    def __str__(self) -> str:
        if self == self.NONE:
            return "-"
        s = ""
        if self & self.WHITE_KINGSIDE:  s += "K"
        if self & self.WHITE_QUEENSIDE: s += "Q"
        if self & self.BLACK_KINGSIDE:  s += "k"
        if self & self.BLACK_QUEENSIDE: s += "q"
        return s

CASTLING_SPOILERS_SQ = {0, 4, 7, 112, 116, 119}  # a1, e1, h1, a8, e8, h8
CASTLING_SPOILERS = {
    0:   ~CastlingRights.WHITE_QUEENSIDE, 
    7:   ~CastlingRights.WHITE_KINGSIDE, 
    4:   ~CastlingRights.WHITE_BOTH,    
    112: ~CastlingRights.BLACK_QUEENSIDE,  
    119: ~CastlingRights.BLACK_KINGSIDE, 
    116: ~CastlingRights.BLACK_BOTH
}


@dataclass(slots=True)
class State:
    move: Move
    captured_val: int
    ep_square: Square | None
    castling_rights: CastlingRights
    is_en_passant: bool


class Board:
    _board: bytearray
    king_squares: list[Square]
    ep_square: Square | None
    castling_rights: CastlingRights
    color: Color

    def __init__(
        self, 
        board_fen: str, 
        castling_rights: CastlingRights, 
        ep_square: Square | None, 
        color: Color
    ) -> None:
        self._board = bytearray(128)
        idx = 0
        for c in board_fen:
            if c == '/': continue
            if c.isdigit():
                idx += int(c)
            else:
                sq = sq_mirror(sq_from_idx(idx))
                self._board[sq] = int(Piece.from_char(c))
                idx += 1
                
        self.king_squares = [0, 0]
        for sq, val in (
            (sq, val) for sq, val 
            in enumerate(self._board) 
            if val and (val >> 1) == KING
        ):
            self.king_squares[val & 1] = sq
                    
        self.castling_rights = castling_rights
        self.ep_square = ep_square
        self.color = color

    def push(self, move: Move) -> State:
        frm   = move.frm
        to    = move.to
        promo = move.promotion
        board = self._board
        
        moving_val   = board[frm]
        captured_val = board[to]
        
        pt  = moving_val >> 1
        col = moving_val & 1
        
        is_ep = False
        
        board[to]  = moving_val
        board[frm] = 0
        
        if pt == PAWN:
            if to == self.ep_square:
                is_ep = True
                ep_capture_sq = to - 16 if col else to + 16
                captured_val = board[ep_capture_sq]
                board[ep_capture_sq] = 0
                
        if promo:
            board[to] = piece_make(col, promo)
        
        if pt == KING:
            self.king_squares[self.color] = move.to
            if abs(to - frm) == 2:
                if to > frm:
                    board[frm + 1] = board[frm + 3]
                    board[frm + 3] = 0
                else:
                    board[frm - 1] = board[frm - 4]
                    board[frm - 4] = 0
        
        state = State(move, captured_val, self.ep_square, self.castling_rights, is_ep)
        self.ep_square = (frm + to) >> 1 if (pt == PAWN and abs(to - frm) == 32) else None
            
        if self.castling_rights:
            if move.frm in CASTLING_SPOILERS_SQ: self.castling_rights &= CASTLING_SPOILERS[move.frm]
            if move.to  in CASTLING_SPOILERS_SQ: self.castling_rights &= CASTLING_SPOILERS[move.to]

        self.color ^= 1
        return state
    
    def unpush(self, state: State) -> State:
        frm   = state.move.frm
        to    = state.move.to
        promo = state.move.promotion
        board = self._board
        
        self.ep_square = state.ep_square
        self.castling_rights = state.castling_rights
        
        moving_val = board[to]

        if promo:
            moving_val = (moving_val & 1) | (PAWN << 1)
            
        board[frm] = moving_val
        
        if state.is_en_passant:
            board[to] = 0
            ep_capture_sq = to - 16 if (moving_val & 1) else to + 16
            self._board[ep_capture_sq] = state.captured_val
        else:
            self._board[to] = state.captured_val
            
        king_move = (moving_val >> 1) == KING
        
        if king_move:      
            self.king_squares[self.color ^ 1] = state.move.frm      
            if abs(to - frm) == 2:
                if to > frm:
                    board[frm + 3] = board[frm + 1]
                    board[frm + 1] = 0
                else:
                    board[frm - 4] = board[frm - 1]
                    board[frm - 1] = 0
        
        self.color ^= 1 
        return state
               
    # @profile    
    def _is_square_attacked(self, sq: Square, attacker_side: Color) -> bool:        
        board = self._board
        
        if attacker_side:
            pawn, knight, king  = Piece.WHITE_PAWN, Piece.WHITE_KNIGHT, Piece.WHITE_KING
            rook, bishop, queen = Piece.WHITE_ROOK, Piece.WHITE_BISHOP, Piece.WHITE_QUEEN
            pawn_dir = -16
        else:
            pawn, knight, king  = Piece.BLACK_PAWN, Piece.BLACK_KNIGHT, Piece.BLACK_KING
            rook, bishop, queen = Piece.BLACK_ROOK, Piece.BLACK_BISHOP, Piece.BLACK_QUEEN
            pawn_dir = 16

        p_sq1 = sq + pawn_dir - 1
        if not (p_sq1 & 0x88) and board[p_sq1] == pawn: return True
        p_sq2 = sq + pawn_dir + 1
        if not (p_sq2 & 0x88) and board[p_sq2] == pawn: return True
        
        for d in DELTAS[KNIGHT]:
            att_sq = sq + d
            if not (att_sq & 0x88) and board[att_sq] == knight: return True
                
        for d in DELTAS[KING]:
            att_sq = sq + d
            if not (att_sq & 0x88) and board[att_sq] == king: return True

        for d in DELTAS[ROOK]:
            curr_sq = sq + d
            while not (curr_sq & 0x88):
                val = board[curr_sq]
                if val:
                    if val == rook or val == queen: return True
                    break
                curr_sq += d
                    
        for d in DELTAS[BISHOP]:
            curr_sq = sq + d
            while not (curr_sq & 0x88):
                val = board[curr_sq]
                if val:
                    if val == bishop or val == queen: return True
                    break
                curr_sq += d

        return False
        
    def pseudo_legal_moves(self) -> list[Move]:
        moves = []
        board = self._board
        ep_sq = self.ep_square if self.ep_square is not None else -1

        if self.color:
            pawn_dir   = 16
            promo_rank = 7
            start_rank = 1
        else:
            pawn_dir   = -16
            promo_rank = 0
            start_rank = 6

        for frm, val in (
            (frm, val) for frm, val
            in enumerate(board) 
            if val and (val & 1) == self.color
        ):
            pt = val >> 1
            
            if pt == PAWN:
                one = frm + pawn_dir
                if not (one & 0x88) and board[one] == PIECE_NONE:
                    rank = one >> 4
                    if rank == promo_rank:
                        for promo_pt in PROMOTIONS:
                            moves.append(Move(frm, one, promo_pt))
                    else:
                        moves.append(Move(frm, one))

                        if (frm >> 4) == start_rank:
                            two = frm + 2 * pawn_dir
                            if board[two] == 0:
                                moves.append(Move(frm, two))
                
                for offset in (pawn_dir - 1, pawn_dir + 1):
                    to = frm + offset
                    if not (to & 0x88):
                        target_val = board[to]
                        if (target_val != 0 and (target_val & 1) != self.color) or to == ep_sq:
                            if (to >> 4) == promo_rank:
                                for promo_pt in PROMOTIONS:
                                    moves.append(Move(frm, to, promo_pt))
                            else:
                                moves.append(Move(frm, to))

            elif pt in SLIDING_PIECES:
                for d in DELTAS[pt]:
                    to = frm + d
                    while not (to & 0x88):
                        target_val = board[to]
                        if target_val == 0:
                            moves.append(Move(frm, to))
                        else:
                            if (target_val & 1) != self.color:
                                moves.append(Move(frm, to))
                            break
                        to += d

            elif pt in STEPPING_PIECES:
                for d in DELTAS[pt]:
                    to = frm + d
                    if not (to & 0x88):
                        target_val = board[to]
                        if target_val == 0 or (target_val & 1) != self.color:
                            moves.append(Move(frm, to))

                if pt == KING: 
                    if self.color:
                        if self.castling_rights & CastlingRights.WHITE_KINGSIDE  and board[frm + 1] == board[frm + 2] == 0:
                            moves.append(Move(frm, frm + 2))
                        if self.castling_rights & CastlingRights.WHITE_QUEENSIDE and board[frm - 1] == board[frm - 2] == board[frm - 3] == 0:
                            moves.append(Move(frm, frm - 2))
                    else:
                        if self.castling_rights & CastlingRights.BLACK_KINGSIDE  and board[frm + 1] == board[frm + 2] == 0:
                            moves.append(Move(frm, frm + 2))
                        if self.castling_rights & CastlingRights.BLACK_QUEENSIDE and board[frm - 1] == board[frm - 2] == board[frm - 3] == 0:
                            moves.append(Move(frm, frm - 2))
        return moves
    
    def legal_moves(self) -> list[Move]:
        side  = self.color
        enemy = side ^ 1
        board = self._board
        moves = []
        
        for move in self.pseudo_legal_moves():
            moving_val = board[move.frm]
            pt = moving_val >> 1
            
            if pt == KING and abs(move.to - move.frm) == 2:
                if self._is_square_attacked(move.frm, enemy):
                    continue
                passed_sq = (move.frm + move.to) >> 1
                if self._is_square_attacked(passed_sq, enemy):
                    continue
            
            state = self.push(move)
            is_in_check = self._is_square_attacked(self.king_squares[side], enemy)
            self.unpush(state)
            
            if not is_in_check:
                moves.append(move)
                
        return moves
                
    def __iter__(self):
        yield from ((sq, Piece(val)) for sq, val in enumerate(self._board) if not (sq) & 0x88)
    
    def fen(self) -> str:
        rows = []
        for r in range(7, -1, -1):
            row = ""
            empty_count = 0
            for f in range(8):
                sq = sq_make(f, r)
                val = self._board[sq]
                if val == 0:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row += str(empty_count)
                        empty_count = 0
                    row += str(Piece(val))
            if empty_count > 0:
                row += str(empty_count)
            rows.append(row)
        board_fen = "/".join(rows)
        color_fen = 'w' if self.color == WHITE else 'b'
        cr_fen = str(self.castling_rights) if self.castling_rights else "-"
        ep_fen = sq_to_str(self.ep_square) if self.ep_square is not None else "-"
        return f"{board_fen} {color_fen} {cr_fen} {ep_fen}"
    
    def __str__(self) -> str:
        return self.fen()