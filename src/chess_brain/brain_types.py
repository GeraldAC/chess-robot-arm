"""Contratos de datos y excepciones del subsistema Estado del Juego + Motor de Decision.

Este modulo define el "contrato" formal entre:
    - Vision (modulo 3)              -> VisionInput
    - Este subsistema (módulos 4-5)
    - Planificación de Movimiento (modulo 6) <- MoveResult

Mantener estos tipos aislados (sin lógica) permite que cualquier otro modulo
importe el contrato sin arrastrar dependencias de chess/stockfish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Una casilla vacía es None. Una pieza es "{color}{tipo}", ej. "wP", "bK".
Square = str | None
BoardMatrix = list[list[Square]]
"""Matriz 8x8. Fila 0 = rank 8 (fila de las negras en la disposición inicial).
Columna 0 = columna 'a'. Es decir, board_matrix[0][0] es la casilla a8.
"""

Color = Literal["w", "b"]
PieceType = Literal["P", "N", "B", "R", "Q", "K"]
CastleSide = Literal["kingside", "queenside"]
GameStatus = Literal["ongoing", "check", "checkmate", "stalemate", "draw"]


@dataclass(frozen=True)
class VisionInput:
    """Lo que el subsistema espera recibir desde Vision (modulo 3) en cada turno humano."""

    board_matrix: BoardMatrix
    side_to_move: Color  # Conocido por el sistema (historial), no por la cámara.


@dataclass(frozen=True)
class MoveResult:
    """Lo que este subsistema entrega a Planificación de Movimiento (modulo 6)."""

    move_uci: str
    from_square: str
    to_square: str
    piece: PieceType
    is_capture: bool
    captured_piece: PieceType | None
    is_castle: bool
    castle_side: CastleSide | None
    is_en_passant: bool
    is_promotion: bool
    promotion_piece: PieceType | None
    resulting_fen: str
    game_status: GameStatus


class IllegalStateError(Exception):
    """La matriz recibida no corresponde a ningún movimiento legal desde el estado anterior.

    Señal de que Vision probablemente fallo (oclusión, clasificación errónea, etc.)
    El Orquestador debería pedir una nueva captura, no continuar el flujo.
    """


class EngineError(Exception):
    """Stockfish no respondió, no esta disponible, o no devolvió una jugada valida."""
