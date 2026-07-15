"""chess_vision — Detección del Tablero (M2) + Clasificación de Piezas (M3).

v2: usa detección clásica de tablero (sin ML) y un modelo YOLO
pretrained por la comunidad para piezas — sin entrenamiento propio.
Ver M2_M3_SPEC.md.
"""

from chess_vision.pipeline import calibrate_orientation, locate_board, process_frame
from chess_vision.types import (
    BoardNotFoundError,
    LowConfidenceDetectionError,
    OrientationAmbiguousError,
    VisionError,
)

__all__ = [
    "process_frame",
    "calibrate_orientation",
    "locate_board",
    "VisionError",
    "BoardNotFoundError",
    "LowConfidenceDetectionError",
    "OrientationAmbiguousError",
]
