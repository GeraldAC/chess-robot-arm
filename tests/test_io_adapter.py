"""Pruebas de Entrada/Salida (io_adapter.py) e integración M4 -> Salida."""

from __future__ import annotations

import chess
import pytest

from chess_brain.io_adapter import build_move_result, parse_vision_input
from chess_brain.types import IllegalStateError
from chess_brain.vision_stub import vision_input_from_matrix, vision_input_from_move
from tests.fixtures.boards import (
    board_en_passant_ready,
    board_fools_mate_setup,
    board_kingside_castle_ready,
    board_promotion_ready,
    initial_board,
)


def test_parse_vision_input_simple_move():
    board = initial_board()
    move = chess.Move.from_uci("e2e4")
    vision_input = vision_input_from_move(board, move)

    applied = parse_vision_input(vision_input, board)

    assert applied == move
    assert board.piece_at(chess.E4) is not None


def test_parse_vision_input_invalid_matrix_raises():
    board = initial_board()
    empty_matrix = [[None] * 8 for _ in range(8)]
    vision_input = vision_input_from_matrix(empty_matrix, "w")

    with pytest.raises(IllegalStateError):
        parse_vision_input(vision_input, board)


def test_build_move_result_normal_move():
    board = initial_board()
    board_before = board.copy()
    move = chess.Move.from_uci("e2e4")
    board.push(move)

    result = build_move_result(board, move, board_before)

    assert result.move_uci == "e2e4"
    assert result.piece == "P"
    assert result.is_capture is False
    assert result.captured_piece is None
    assert result.is_castle is False
    assert result.is_promotion is False
    assert result.game_status == "ongoing"


def test_build_move_result_capture():
    board = chess.Board()
    board.push_san("e4")
    board.push_san("d5")
    board_before = board.copy()
    move = chess.Move.from_uci("e4d5")
    board.push(move)

    result = build_move_result(board, move, board_before)

    assert result.is_capture is True
    assert result.captured_piece == "P"


def test_build_move_result_castle():
    board = board_kingside_castle_ready()
    board_before = board.copy()
    move = chess.Move.from_uci("e1g1")
    board.push(move)

    result = build_move_result(board, move, board_before)

    assert result.is_castle is True
    assert result.castle_side == "kingside"


def test_build_move_result_en_passant():
    board = board_en_passant_ready()
    board_before = board.copy()
    move = chess.Move.from_uci("e5d6")
    board.push(move)

    result = build_move_result(board, move, board_before)

    assert result.is_capture is True
    assert result.is_en_passant is True
    assert result.captured_piece == "P"


def test_build_move_result_promotion():
    board = board_promotion_ready()
    board_before = board.copy()
    move = chess.Move.from_uci("a7a8q")
    board.push(move)

    result = build_move_result(board, move, board_before)

    assert result.is_promotion is True
    assert result.promotion_piece == "Q"


def test_build_move_result_checkmate():
    board = board_fools_mate_setup()
    board_before = board.copy()
    move = chess.Move.from_uci("d8h4")
    board.push(move)

    result = build_move_result(board, move, board_before)

    assert result.game_status == "checkmate"


def test_end_to_end_vision_to_move_result():
    """Integración completa: VisionInput (matriz) -> M4 -> MoveResult (Salida)."""
    board = initial_board()
    move = chess.Move.from_uci("g1f3")
    vision_input = vision_input_from_move(board, move)

    board_before = board.copy()
    applied = parse_vision_input(vision_input, board)
    result = build_move_result(board, applied, board_before)

    assert result.move_uci == "g1f3"
    assert result.piece == "N"
    assert result.resulting_fen == board.fen()
