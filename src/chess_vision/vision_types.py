"""chess_vision.vision_types — contratos internos de M2 (Detección del
tablero) y M3 (Clasificación de piezas).

v2: estrategia "usar soluciones existentes" — sin entrenamiento
propio. Ver M2_M3_SPEC.md para el porqué del cambio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

RawFrame = (
    np.ndarray
)  # imagen BGR cruda (H, W, 3), tal como la entrega camera_capture.py o cv2.imread
Point2D = tuple[float, float]

CameraOrientedMatrix = list[list[str | None]]
# 8x8, fila 0 = fila superior de la imagen (borde top_left-top_right).
# Orientación de CÁMARA, aún no resuelta a orientación de ajedrez
# (ver chess_vision.orientation).

CameraOrientedGrid = list[list[tuple[Point2D, Point2D, Point2D, Point2D]]]
# 8x8, grid[row][col] = las 4 esquinas de esa casilla EN COORDENADAS
# DE LA IMAGEN ORIGINAL (no de una imagen deformada) — preserva la
# perspectiva real de cada casilla. Cada tupla: (top_left, top_right,
# bottom_right, bottom_left) de la celda.

Orientation = Literal["identity", "rotated_180"]


@dataclass(frozen=True)
class BoardCorners:
    """4 esquinas extremas del tablero en la imagen cruda, en
    coordenadas de píxel. Representan geometría de cámara, NO
    todavía a1/h8 — esa resolución ocurre en orientation.py."""

    top_left: Point2D
    top_right: Point2D
    bottom_left: Point2D
    bottom_right: Point2D


@dataclass(frozen=True)
class PieceDetection:
    """Una detección cruda de pieza, en coordenadas de la imagen
    ORIGINAL (la detección de piezas ya NO corre sobre una imagen
    deformada — ver nota de diseño en piece_classifier.py)."""

    piece_code: str  # "wP", "bN", "bK", ... — mismo alfabeto que BoardMatrix
    bbox_px: tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float


class VisionError(Exception):
    """Clase base de errores de contrato de chess_vision."""


class BoardNotFoundError(VisionError):
    """No se pudo ubicar el tablero (ni sus 4 esquinas extremas) en el
    frame recibido con los parámetros de detección dados."""


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
