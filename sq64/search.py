import argparse

from sq64.engine import get_best_move
from sq64.game import Game

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--time", "-t", type=float, default=5.0)
    args = parser.parse_args()
    move = get_best_move(Game(), time_limit=args.time)