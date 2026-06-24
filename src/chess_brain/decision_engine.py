"""Módulo 5 - Motor de Decision.

Responsabilidades:
    1. Inicializar y mantener el proceso de Stockfish (chess.engine).
    2. Dado un chess.Board, solicitar la mejor jugada para el lado en turno.

Decidir y ejecutar son responsabilidades separadas: esta función NO aplica
el movimiento sobre el board. Quien la llama decide cuando hacer board.push().
"""

from __future__ import annotations

import chess
import chess.engine

from chess_brain.types import EngineError


def init_engine(stockfish_path: str) -> chess.engine.SimpleEngine:
    """Abre el proceso de Stockfish.

    Debe cerrarse explícitamente con engine.quit() (o usarse como context
    manager externo) al finalizar, para no dejar procesos huérfanos.
    """
    try:
        return chess.engine.SimpleEngine.popen_uci(stockfish_path)
    except FileNotFoundError as exc:
        raise EngineError(
            f"No se encontró el binario de Stockfish en '{stockfish_path}'. "
            "Verifica la ruta configurada."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de arranque del motor
        raise EngineError(f"No se pudo iniciar Stockfish: {exc}") from exc


def get_best_move(
    board: chess.Board,
    engine: chess.engine.SimpleEngine,
    think_time: float = 1.0,
) -> chess.Move:
    """Solicita a Stockfish la mejor jugada para board.turn.

    No aplica el movimiento. Lanza EngineError si el motor falla o no
    devuelve una jugada.
    """
    try:
        result = engine.play(board, chess.engine.Limit(time=think_time))
    except Exception as exc:  # noqa: BLE001 - fallo de comunicación UCI
        raise EngineError(f"Stockfish fallo al calcular la jugada: {exc}") from exc

    if result.move is None:
        raise EngineError(
            "Stockfish no devolvió una jugada (posición sin movimientos legales?)."
        )

    return result.move
