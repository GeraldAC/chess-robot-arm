"""chess_vision.types — contratos internos de M2 (Detección del
tablero) y M3 (Clasificación de piezas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

RawFrame = (
    np.ndarray
)  # imagen BGR cruda (H, W, 3), tal como la entrega camera_capture.py
Point2D = tuple[float, float]

CameraOrientedMatrix = list[list[str | None]]
# 8x8, fila 0 = fila superior de la imagen rectificada.
# Orientación de CÁMARA, aún no resuelta a orientación de ajedrez
# (ver chess_vision.orientation).

Orientation = Literal["identity", "rotated_180"]


@dataclass(frozen=True)
class BoardCorners:
    """4 esquinas del tablero en la imagen cruda, en orden cíclico
    horario, empezando por la de coordenada (x+y) mínima. Representan
    geometría de cámara, NO todavía a1/h8 — esa resolución ocurre en
    orientation.py."""

    points_px: tuple[Point2D, Point2D, Point2D, Point2D]
    confidences: tuple[float, float, float, float]


@dataclass(frozen=True)
class PieceDetection:
    """Una detección cruda de pieza sobre la imagen ya rectificada
    por M2."""

    piece_code: str  # "wP", "bN", "bK", ... — mismo alfabeto que BoardMatrix
    bbox_px: tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float


class VisionError(Exception):
    """Clase base de errores de contrato de chess_vision."""


class BoardNotFoundError(VisionError):
    """No se detectaron las 4 esquinas del tablero con confianza
    suficiente en el frame recibido."""


class LowConfidenceDetectionError(VisionError):
    """Una o más casillas quedaron por debajo del umbral de confianza
    configurado. Se lanza en vez de inferir en silencio — el
    llamador decide qué hacer (reintentar captura, pedir
    confirmación, etc.)."""

    def __init__(self, uncertain_cells: list[tuple[int, int]]):
        self.uncertain_cells = uncertain_cells
        cells_str = ", ".join(f"({r},{c})" for r, c in uncertain_cells)
        super().__init__(f"Casillas con confianza insuficiente: {cells_str}")


class OrientationAmbiguousError(VisionError):
    """La matriz cruda no coincide con la posición inicial estándar en
    ninguna orientación evaluada (identity / rotated_180)."""
