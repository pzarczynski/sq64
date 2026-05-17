import pytest

from sq64.game import Game
from sq64.perft import perft

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


@pytest.mark.parametrize("fen, depth, expected", STARTING_POSITION)
def test_perft_starting_position(fen: str, depth: int, expected: int):
    assert perft(Game(fen), depth) == expected


@pytest.mark.parametrize("fen, depth, expected", KIWIPETE_POSITION)
def test_perft_kiwipete(fen: str, depth: int, expected: int):
    assert perft(Game(fen), depth) == expected


@pytest.mark.parametrize("fen, depth, expected", POSITION_3)
def test_perft_position_3(fen: str, depth: int, expected: int):
    assert perft(Game(fen), depth) == expected