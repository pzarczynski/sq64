import pytest

from sq64.chess import Board

POSITIONS = [
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 4, 197281),  # starting
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 3, 97862),  # kiwipete
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 3, 2812),  # endgame
]


@pytest.mark.parametrize("fen, depth, expected", POSITIONS)
def test_perft(fen: str, depth: int, expected: int) -> None:
    assert Board(fen).perft(depth) == expected

