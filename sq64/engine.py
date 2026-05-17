import time

from sq64.core import Board, Move

transposition_table = {}

TT_EXACT = 0
TT_LOWERBOUND = 1
TT_UPPERBOUND = 2
INF = 999999

def move_priority(board: Board, move: Move, prev_best: Move | None = None) -> int:
    if move == prev_best:       return 1000000
    if move.is_capture(board):  return 10000
    if move.is_promotion():     return 9000
    return 0

class SearchAborted(Exception):
    pass

def quiescence_search(board: Board, alpha: float, beta: float, color_sign: int, ctx: dict) -> float:
    ctx['nodes'] += 1
    if ctx['nodes'] & 1023 == 0 and time.time() - ctx['start_time'] > ctx['time_limit']:
        raise SearchAborted()
    
    stand_pat = color_sign * board.score
    if stand_pat >= beta: return beta
    if alpha < stand_pat: alpha = stand_pat
            
    for move in board.legal_quiescence():
        state = board.push(move)
        score = -quiescence_search(board, -beta, -alpha, -color_sign, ctx)
        board.unpush(state)
        
        if score >= beta: return beta
        if score > alpha: alpha = score
            
    return alpha

def negamax(board: Board, depth: int, alpha: float, beta: float, color_sign: int, ctx: dict, is_null_move: bool = False) -> float:
    ctx['nodes'] += 1
    if ctx['nodes'] & 1023 == 0 and time.time() - ctx['start_time'] > ctx['time_limit']:
        raise SearchAborted()
    
    board_hash = hash(board)
    alpha_orig = alpha
    
    tt_entry = transposition_table.get(board_hash)
    tt_move = None
    
    if tt_entry is not None:
        tt_move = tt_entry.get('best_move')
        if tt_entry['depth'] >= depth:
            tt_flag = tt_entry['flag']
            tt_score = tt_entry['score']
            
            if tt_flag == TT_EXACT: return tt_score
            elif tt_flag == TT_LOWERBOUND and tt_score >= beta: return tt_score
            elif tt_flag == TT_UPPERBOUND and tt_score <= alpha: return tt_score

    if depth <= 0: return quiescence_search(board, alpha, beta, color_sign, ctx)

    is_check = board.is_check()
    R = 2
    if not is_null_move and not is_check and depth >= 3:
        ep_sq, old_hash = board.push_null()
        null_score = -negamax(board, depth - 1 - R, -beta, -beta + 1, -color_sign, ctx, is_null_move=True)
        board.unpush_null(ep_sq, old_hash)
        if null_score >= beta: return beta
        
    moves = board.legal_moves()
    if not moves: return -99999 if is_check else 0

    moves.sort(key=lambda m: move_priority(board, m, tt_move), reverse=True)
    max_score = -INF
    cur_best_move = None
    
    for i, move in enumerate(moves):
        state = board.push(move)
        
        is_tactical = board.is_capture(move) or board.is_promotion(move)
        score = None
        
        if depth >= 3 and i >= 3 and not is_check and not is_tactical:  # LMR
            R = 1 if depth < 5 else 2
            score = -negamax(board, depth - 1 - R, -alpha - 1, -alpha, -color_sign, ctx)
            if score > alpha: score = None 
                
        if score is None:  # PVS
            if i == 0: 
                score = -negamax(board, depth - 1, -beta, -alpha, -color_sign, ctx)
            else: 
                score = -negamax(board, depth - 1, -alpha - 1, -alpha, -color_sign, ctx)
                if alpha < score < beta:
                    score = -negamax(board, depth - 1, -beta, -alpha, -color_sign, ctx)
        
        score = -negamax(board, depth - int(not board.is_check()), -beta, -alpha, -color_sign, ctx)
        board.unpush(state)
        
        if score > max_score: 
            max_score = score
            cur_best_move = move
        if max_score > alpha: alpha = max_score
        if alpha >= beta: break
    
    tt_flag = TT_EXACT
    if max_score <= alpha_orig: tt_flag = TT_UPPERBOUND
    elif max_score >= beta: tt_flag = TT_LOWERBOUND
        
    transposition_table[board_hash] = {'depth': depth, 'score': max_score, 'flag': tt_flag, 'best_move': cur_best_move}
    return max_score

def get_best_move(board: Board, max_depth: int = 10, time_limit: float = 2.0) -> dict:
    global transposition_table
    transposition_table.clear()

    best_move = None
    completed_depth = 0
    start_time = time.time()
    color_sign = 1 if board.color else -1

    ctx = {'nodes': 0, 'start_time': time.time(), 'time_limit': time_limit}

    moves = board.legal_moves()
    if not moves: return ctx | {'best_move': None}

    try:
        for depth in range(1, max_depth + 1):
            moves.sort(key=lambda m: move_priority(board, m, best_move), reverse=True)
            
            cur_best_move = moves[0]
            max_score = alpha = -INF
            beta = INF
            
            for move in moves:
                if time.time() - start_time > time_limit: raise SearchAborted()
                    
                state = board.push(move)
                score = -negamax(board, depth - 1, -beta, -alpha, -color_sign, ctx)
                board.unpush(state)
                
                if score > max_score:
                    max_score = score
                    cur_best_move = move
                    
                if max_score > alpha:
                    alpha = max_score

            best_move = cur_best_move
            completed_depth = depth

    except SearchAborted:
        pass

    total_time = time.time() - ctx['start_time']
    nps = int(ctx['nodes'] / total_time) if total_time > 0 else 0
        
    return {
        'best_move': best_move or moves[0],
        'depth': completed_depth,
        'nodes': ctx['nodes'],
        'time': total_time,
        'nps': nps,
    }