import pytest

from sq64.game import Game
from sq64.perft import KIWIPETE_POSITION, POSITION_3, STARTING_POSITION, perft


@pytest.mark.parametrize("fen, depth, expected", STARTING_POSITION)
def test_perft_starting_position(fen: str, depth: int, expected: int):
    assert perft(Game(fen), depth) == expected


@pytest.mark.parametrize("fen, depth, expected", KIWIPETE_POSITION)
def test_perft_kiwipete(fen: str, depth: int, expected: int):
    assert perft(Game(fen), depth) == expected


@pytest.mark.parametrize("fen, depth, expected", POSITION_3)
def test_perft_position_3(fen: str, depth: int, expected: int):
    assert perft(Game(fen), depth) == expected