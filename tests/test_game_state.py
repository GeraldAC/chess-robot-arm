"""Pruebas del módulo 4 - Estado del Juego (game_state.py)."""

from __future__ import annotations

import chess
import pytest

from chess_brain.brain_types import IllegalStateError
from chess_brain.game_state import (
    apply_human_move,
    board_to_matrix,
    get_game_status,
    infer_human_move,
)
from tests.fixtures.boards import (
    board_en_passant_ready,
    board_fools_mate_setup,
    board_kingside_castle_ready,
    board_promotion_ready,
    initial_board,
    matrix_after_e2e4,
)


def test_infer_simple_pawn_move():
    board = initial_board()
    move = infer_human_move(board, matrix_after_e2e4())
    assert move == chess.Move.from_uci("e2e4")


def test_infer_human_move_does_not_mutate_board():
    board = initial_board()
    fen_before = board.fen()
    infer_human_move(board, matrix_after_e2e4())
    assert board.fen() == fen_before


def test_apply_human_move_mutates_board():
    board = initial_board()
    apply_human_move(board, matrix_after_e2e4())
    assert board.fen() != chess.Board().fen()
    assert board.piece_at(chess.E4) is not None


def test_infer_capture():
    # board = board_fools_mate_setup()
    # Negras dan mate con Qh4#, no es captura, probamos una captura real distinta:
    # usamos un escenario simple de captura de peon.
    board2 = chess.Board()
    board2.push_san("e4")
    board2.push_san("d5")
    matrix_after_capture = board_to_matrix_after(board2, "e4d5")
    move = infer_human_move(board2, matrix_after_capture)
    assert move == chess.Move.from_uci("e4d5")


def board_to_matrix_after(board: chess.Board, uci: str):
    trial = board.copy()
    trial.push(chess.Move.from_uci(uci))
    return board_to_matrix(trial)


def test_infer_castle_kingside():
    board = board_kingside_castle_ready()
    matrix = board_to_matrix_after(board, "e1g1")
    move = infer_human_move(board, matrix)
    assert move == chess.Move.from_uci("e1g1")
    assert board.is_kingside_castling(move)


def test_infer_en_passant():
    board = board_en_passant_ready()
    matrix = board_to_matrix_after(board, "e5d6")
    move = infer_human_move(board, matrix)
    assert move == chess.Move.from_uci("e5d6")
    assert board.is_en_passant(move)


def test_infer_promotion():
    board = board_promotion_ready()
    matrix = board_to_matrix_after(board, "a7a8q")
    move = infer_human_move(board, matrix)
    assert move.promotion == chess.QUEEN


def test_infer_illegal_state_raises():
    board = initial_board()
    # Matriz absurda: tablero completamente vacío, ningún movimiento legal produce esto.
    empty_matrix = [[None] * 8 for _ in range(8)]
    with pytest.raises(IllegalStateError):
        infer_human_move(board, empty_matrix)


def test_game_status_ongoing():
    board = initial_board()
    assert get_game_status(board) == "ongoing"


def test_game_status_checkmate_fools_mate():
    board = board_fools_mate_setup()
    board.push_san("Qh4+")
    assert board.is_checkmate()
    assert get_game_status(board) == "checkmate"
