"""Pruebas del modulo 5 - Motor de Decision (decision_engine.py).

Requiere un binario de Stockfish instalado. La ruta se inyecta vía la
variable de entorno STOCKFISH_PATH (ver README para configuración local).
"""

from __future__ import annotations

import os

import pytest

from chess_brain.decision_engine import EngineError, get_best_move, init_engine
from tests.fixtures.boards import board_fools_mate_setup, initial_board

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
_SKIP_REASON = (
    f"Stockfish no encontrado en '{STOCKFISH_PATH}'. "
    "Define la variable de entorno STOCKFISH_PATH apuntando al binario."
)


@pytest.fixture
def engine():
    if not os.path.exists(STOCKFISH_PATH):
        pytest.skip(_SKIP_REASON)
    eng = init_engine(STOCKFISH_PATH)
    yield eng
    eng.quit()


def test_init_engine_invalid_path_raises():
    with pytest.raises(EngineError):
        init_engine("/ruta/que/no/existe/stockfish")


def test_get_best_move_initial_position_is_legal(engine):
    board = initial_board()
    move = get_best_move(board, engine, think_time=0.2)
    assert move in board.legal_moves


def test_get_best_move_finds_mate_in_one(engine):
    """Negras tienen mate en 1 (Qh4#) tras 1.f3 e5 2.g4 -- el motor debe encontrarlo."""
    board = board_fools_mate_setup()
    move = get_best_move(board, engine, think_time=0.5)
    board.push(move)
    assert board.is_checkmate()


def test_get_best_move_does_not_mutate_board(engine):
    board = initial_board()
    fen_before = board.fen()
    get_best_move(board, engine, think_time=0.2)
    assert board.fen() == fen_before
