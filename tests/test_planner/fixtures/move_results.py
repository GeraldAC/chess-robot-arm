"""Fixtures de MoveResult + board_before para test_movement_planner.py.

Cada fixture es una tupla (board_before, move_result) construida a mano
para representar exactamente una categoría del plan de pruebas de
M6_SPEC.md §6.1. No dependen de chess_brain.io_adapter real: se
construyen directamente para poder probar chess_planner de forma
aislada, igual que fixtures/boards.py en M4-5.
"""

from __future__ import annotations

import chess

from chess_brain.brain_types import MoveResult


def normal_move() -> tuple[chess.Board, MoveResult]:
    """1. e4 — movimiento normal de peón, sin captura."""
    board_before = chess.Board()  # posición inicial, blancas a mover
    move_result = MoveResult(
        move_uci="e2e4",
        from_square="e2",
        to_square="e4",
        piece="P",
        is_capture=False,
        captured_piece=None,
        is_castle=False,
        castle_side=None,
        is_en_passant=False,
        is_promotion=False,
        promotion_piece=None,
        resulting_fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        game_status="ongoing",
    )
    return board_before, move_result


def simple_capture() -> tuple[chess.Board, MoveResult]:
    """Después de 1. e4 d5 — blancas juegan exd5 (captura simple)."""
    board_before = chess.Board(
        "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
    )
    move_result = MoveResult(
        move_uci="e4d5",
        from_square="e4",
        to_square="d5",
        piece="P",
        is_capture=True,
        captured_piece="P",
        is_castle=False,
        castle_side=None,
        is_en_passant=False,
        is_promotion=False,
        promotion_piece=None,
        resulting_fen="rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2",
        game_status="ongoing",
    )
    return board_before, move_result


def en_passant_capture() -> tuple[chess.Board, MoveResult]:
    """Después de 1. e4 a6 2. e5 f5 — blancas juegan exf6 al paso."""
    board_before = chess.Board(
        "rnbqkbnr/1ppppp1p/p7/4Pp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"
    )
    move_result = MoveResult(
        move_uci="e5f6",
        from_square="e5",
        to_square="f6",
        piece="P",
        is_capture=True,
        captured_piece="P",
        is_castle=False,
        castle_side=None,
        is_en_passant=True,
        is_promotion=False,
        promotion_piece=None,
        resulting_fen="rnbqkbnr/1ppppp1p/p4P2/8/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 3",
        game_status="ongoing",
    )
    return board_before, move_result


def castle_kingside_white() -> tuple[chess.Board, MoveResult]:
    """Blancas enrocan corto (O-O)."""
    board_before = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move_result = MoveResult(
        move_uci="e1g1",
        from_square="e1",
        to_square="g1",
        piece="K",
        is_capture=False,
        captured_piece=None,
        is_castle=True,
        castle_side="kingside",
        is_en_passant=False,
        is_promotion=False,
        promotion_piece=None,
        resulting_fen="r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1",
        game_status="ongoing",
    )
    return board_before, move_result


def castle_queenside_black() -> tuple[chess.Board, MoveResult]:
    """Negras enrocan largo (O-O-O)."""
    board_before = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
    move_result = MoveResult(
        move_uci="e8c8",
        from_square="e8",
        to_square="c8",
        piece="K",
        is_capture=False,
        captured_piece=None,
        is_castle=True,
        castle_side="queenside",
        is_en_passant=False,
        is_promotion=False,
        promotion_piece=None,
        resulting_fen="2kr3r/8/8/8/8/8/8/R3K2R w KQ - 1 2",
        game_status="ongoing",
    )
    return board_before, move_result


def promotion_no_capture() -> tuple[chess.Board, MoveResult]:
    """Peón blanco corona a Dama sin capturar."""
    board_before = chess.Board("6k1/4P3/8/8/8/8/8/6K1 w - - 0 1")
    move_result = MoveResult(
        move_uci="e7e8q",
        from_square="e7",
        to_square="e8",
        piece="P",
        is_capture=False,
        captured_piece=None,
        is_castle=False,
        castle_side=None,
        is_en_passant=False,
        is_promotion=True,
        promotion_piece="Q",
        resulting_fen="4Q1k1/8/8/8/8/8/8/6K1 b - - 0 1",
        game_status="ongoing",
    )
    return board_before, move_result


def promotion_with_capture() -> tuple[chess.Board, MoveResult]:
    """Peón blanco captura torre en d8 y corona a Dama."""
    board_before = chess.Board("3r2k1/4P3/8/8/8/8/8/6K1 w - - 0 1")
    move_result = MoveResult(
        move_uci="e7d8q",
        from_square="e7",
        to_square="d8",
        piece="P",
        is_capture=True,
        captured_piece="R",
        is_castle=False,
        castle_side=None,
        is_en_passant=False,
        is_promotion=True,
        promotion_piece="Q",
        resulting_fen="3Q2k1/8/8/8/8/8/8/6K1 b - - 0 1",
        game_status="ongoing",
    )
    return board_before, move_result


def underpromotion_unsupported() -> tuple[chess.Board, MoveResult]:
    """Peón blanco corona a Caballo — no soportado en v1."""
    board_before = chess.Board("6k1/4P3/8/8/8/8/8/6K1 w - - 0 1")
    move_result = MoveResult(
        move_uci="e7e8n",
        from_square="e7",
        to_square="e8",
        piece="P",
        is_capture=False,
        captured_piece=None,
        is_castle=False,
        castle_side=None,
        is_en_passant=False,
        is_promotion=True,
        promotion_piece="N",
        resulting_fen="4N1k1/8/8/8/8/8/8/6K1 b - - 0 1",
        game_status="ongoing",
    )
    return board_before, move_result
