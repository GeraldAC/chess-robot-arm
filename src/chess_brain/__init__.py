"""chess_brain - Módulos 4 (Estado del Juego) y 5 (Motor de Decision) del
proyecto de brazo robótico para ajedrez.

API publica pensada para que el Orquestador del sistema completo importe
solo lo necesario, sin conocer los detalles internos de cada modulo.
"""

from chess_brain.decision_engine import get_best_move, init_engine
from chess_brain.io_adapter import build_move_result, parse_vision_input
from chess_brain.types import EngineError, IllegalStateError, MoveResult, VisionInput

__all__ = [
    "get_best_move",
    "init_engine",
    "build_move_result",
    "parse_vision_input",
    "EngineError",
    "IllegalStateError",
    "MoveResult",
    "VisionInput",
]
