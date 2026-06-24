"""Módulo 4 - Estado del Juego.

Responsabilidades:

    1.  Mantener el chess.Board autoritativo (historial completo de la partida).
    2.  Recibir una BoardMatrix (lo que Vision reporto) e inferir que movimiento
        legal del humano la produjo.
    3.  Aplicar ese movimiento sobre el Board interno.
    4.  Exponer el estado resultante (jaque, mate, tablas, etc.) via helpers.

Este módulo NO decide jugadas (eso es responsabilidad del modulo 5) y NO sabe
nada de Visión ni de Stockfish: solo de reglas de ajedrez.
"""

from __future__ import annotations

import chess

from chess_brain.types import BoardMatrix, IllegalStateError

# Mapeo entre el código de pieza usado en BoardMatrix ("wP", "bK", ...)
# y los tipos/colores de python-chess.
_PIECE_TYPE_FROM_CHAR = {
    "P": chess.PAWN,
    "N": chess.KNIGHT,
    "B": chess.BISHOP,
    "R": chess.ROOK,
    "Q": chess.QUEEN,
    "K": chess.KING,
}
_CHAR_FROM_PIECE_TYPE = {v: k for k, v in _PIECE_TYPE_FROM_CHAR.items()}


def board_to_matrix(board: chess.Board) -> BoardMatrix:
    """Convierte un chess.Board a BoardMatrix (formato que Vision produciría).

    Fila 0 = rank 8, columna 0 = columna 'a'. Util para comparar contra
    lo que Vision reporta, y para generar matrices de prueba en CLI/tests.
    """
    matrix: BoardMatrix = []
    for rank in range(7, -1, -1):  # 7=rank8 ... 0=rank1
        row: list[str | None] = []
        for file in range(8):  # 0=a ... 7=h
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece is None:
                row.append(None)
            else:
                color_char = "w" if piece.color == chess.WHITE else "b"
                type_char = _CHAR_FROM_PIECE_TYPE[piece.piece_type]
                row.append(f"{color_char}{type_char}")
        matrix.append(row)
    return matrix


def matrices_equal(a: BoardMatrix, b: BoardMatrix) -> bool:
    """Comparación estricta de dos matrices 8x8."""
    if len(a) != 8 or len(b) != 8:
        return False
    return all(a[r][c] == b[r][c] for r in range(8) for c in range(8))


def infer_human_move(board: chess.Board, new_matrix: BoardMatrix) -> chess.Move:
    """Encuentra que movimiento legal, aplicado a `board`, produce `new_matrix`.

    Recorre board.legal_moves (máximo ~40 en posiciones típicas), simula cada
    uno sobre una copia del tablero, y compara la matriz resultante contra
    `new_matrix`. No muta `board`.

    Lanza IllegalStateError si ningún movimiento legal coincide -- señal de que
    Vision probablemente reporto un estado erróneo.
    """
    for candidate in board.legal_moves:
        trial = board.copy()
        trial.push(candidate)
        if matrices_equal(board_to_matrix(trial), new_matrix):
            return candidate

    raise IllegalStateError(
        "Ninguna jugada legal desde la posición actual coincide con la matriz "
        "recibida. Posible error de Vision (oclusión, clasificación errónea, "
        "o desincronización del estado)."
    )


def apply_human_move(board: chess.Board, new_matrix: BoardMatrix) -> chess.Move:
    """Infiere el movimiento humano y lo aplica (muta `board`). Retorna el Move aplicado."""
    move = infer_human_move(board, new_matrix)
    board.push(move)
    return move


def get_game_status(board: chess.Board) -> str:
    """Estado de la partida DESPUÉS de aplicar un movimiento."""
    if board.is_checkmate():
        return "checkmate"
    if (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.can_claim_draw()
    ):
        return "stalemate" if board.is_stalemate() else "draw"
    if board.is_check():
        return "check"
    return "ongoing"
