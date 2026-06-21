def main() -> None:
    import argparse
    from time import perf_counter

    from sq64_chess.board import Board

    parser = argparse.ArgumentParser()
    parser.add_argument("depth", type=int)
    parser.add_argument("--fen", type=str, default=Board.STARTING_FEN)
    args = parser.parse_args()

    b = Board(fen=args.fen)
    t0 = perf_counter()
    nodes = b.perft(depth=args.depth)
    t = perf_counter() - t0

    print(f"{nodes} nodes ({nodes / t:.0f} nps)")


if __name__ == "__main__":
    main()
