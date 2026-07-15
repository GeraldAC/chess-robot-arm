"""chess_vision — Detección del Tablero (M2) + Clasificación de Piezas (M3)."""

from chess_vision.pipeline import calibrate_orientation, process_frame
from chess_vision.types import (
    BoardNotFoundError,
    LowConfidenceDetectionError,
    OrientationAmbiguousError,
    VisionError,
)

__all__ = [
    "process_frame",
    "calibrate_orientation",
    "VisionError",
    "BoardNotFoundError",
    "LowConfidenceDetectionError",
    "OrientationAmbiguousError",
]
