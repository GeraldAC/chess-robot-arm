"""Posiciones de prueba reutilizables: Board + matrices conocidas.

Evita repetir literales de matrices 8x8 en cada archivo de test.
"""

from __future__ import annotations

import chess

from chess_brain.game_state import board_to_matrix


def initial_board() -> chess.Board:
    return chess.Board()


def matrix_after_e2e4() -> list[list[str | None]]:
    """Matriz resultante tras 1. e4, generada desde un Board real (fuente de verdad)."""
    board = chess.Board()
    board.push(chess.Move.from_uci("e2e4"))
    return board_to_matrix(board)


def board_before_scholars_capture() -> chess.Board:
    """Posición tras 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6 -- el robot puede capturar la dama con Nxh5."""
    board = chess.Board()
    for uci in ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6"]:
        board.push(chess.Move.from_uci(uci))
    return board


def board_fools_mate_setup() -> chess.Board:
    """Posición tras 1.f3 e5 2.g4 -- negras dan mate con Qh4#."""
    board = chess.Board()
    for uci in ["f2f3", "e7e5", "g2g4"]:
        board.push(chess.Move.from_uci(uci))
    return board


def board_en_passant_ready() -> chess.Board:
    """Posición donde blancas pueden capturar al paso: tras 1.e4 a6 2.e5 d5, exd6 e.p."""
    board = chess.Board()
    for uci in ["e2e4", "a7a6", "e4e5", "d7d5"]:
        board.push(chess.Move.from_uci(uci))
    return board


def board_kingside_castle_ready() -> chess.Board:
    """Posición donde blancas pueden enrocar corto inmediatamente."""
    board = chess.Board()
    for uci in ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"]:
        board.push(chess.Move.from_uci(uci))
    return board


def board_promotion_ready() -> chess.Board:
    """Posición donde un peon blanco puede promocionar por avance simple a a8 (casilla vacía)."""
    board = chess.Board(fen="8/P7/8/8/8/8/k7/7K w - - 0 1")
    return board
