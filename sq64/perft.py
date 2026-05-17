from time import perf_counter

from sq64.game import Game


def perft(game: Game, depth: int) -> int:
    if depth == 0:
        return 1
        
    nodes = 0
    for move in game.legal_moves():
        game.play(move)
        nodes += perft(game, depth - 1)
        game.pop()
        
    return nodes


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="run perft test")
    parser.add_argument("-d", "--depth", type=int, default=4)
    args = parser.parse_args()
    
    t0 = perf_counter()
    nodes = perft(Game(), args.depth)
    t = perf_counter() - t0
    print(f"Time taken: {t:.2f} seconds; NPS: {nodes / t:.0f}")