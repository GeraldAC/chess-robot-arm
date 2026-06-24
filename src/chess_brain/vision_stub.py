"""Stub de Vision: simula la entrada que en el sistema final vendría de la
ESP32-CAM + clasificador de piezas (modulo 3).

Util para probar el contrato VisionInput de punta a punta sin depender de
hardware. Dos modos:

    - Desde un movimiento UCI conocido (rápido, para jugar normal).
    - Matriz manual (para simular errores de Vision o probar IllegalStateError).
"""

from __future__ import annotations

import chess

from chess_brain.game_state import board_to_matrix
from chess_brain.types import BoardMatrix, VisionInput


def vision_input_from_move(board: chess.Board, move: chess.Move) -> VisionInput:
    """Simula lo que Vision 'fotografiaría' DESPUÉS de que el humano juegue `move`.

    No muta `board`: aplica el movimiento sobre una copia, y reporta la matriz
    resultante -- exactamente el contrato que produciría una cámara real.
    """
    trial = board.copy()
    trial.push(move)
    matrix = board_to_matrix(trial)
    side_to_move = "w" if trial.turn == chess.WHITE else "b"
    return VisionInput(board_matrix=matrix, side_to_move=side_to_move)


def vision_input_from_matrix(matrix: BoardMatrix, side_to_move: str) -> VisionInput:
    """Construye un VisionInput directamente desde una matriz dada a mano.

    Pensado para probar el caso de matriz invalida (simula un error de
    clasificación de Vision) o para inyectar posiciones de prueba arbitrarias.
    """
    return VisionInput(board_matrix=matrix, side_to_move=side_to_move)  # type: ignore[arg-type]
