from time import perf_counter

from sq64.game import Game

STARTING_POSITION = [
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 1, 20),
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 2, 400),
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 3, 8902),
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 4, 197281),
]

KIWIPETE_POSITION = [
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 1, 48),
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 2, 2039),
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 3, 97862),
]

POSITION_3 = [
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 1, 14),
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 2, 191),
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 3, 2812),
]


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