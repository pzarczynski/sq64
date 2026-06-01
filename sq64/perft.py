from time import perf_counter

from sq64.core import Board


def perft(board: Board, depth: int) -> int:
    if depth == 0:
        return 1

    nodes = 0
    side = board.color

    for move in board.gen_moves():
        state = board.push(move)

        if not board.is_check(side):
            nodes += perft(board, depth - 1) if depth > 1 else 1

        board.unpush(state)

    return nodes


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="run perft test")
    parser.add_argument("-d", "--depth", type=int, default=5)
    args = parser.parse_args()

    t0 = perf_counter()
    nodes = perft(Board(), args.depth)
    t = perf_counter() - t0
    print(f"Time taken: {t:.2f} seconds; NPS: {nodes / t:.0f}")
