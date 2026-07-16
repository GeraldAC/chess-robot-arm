"""chess_vision.square_mapper — asigna detecciones de pieza (en
coordenadas de la imagen ORIGINAL) a casillas de la grilla 8x8, usando
el cuadrilátero real (con perspectiva) de cada casilla.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from chess_vision.vision_types import (
    CameraOrientedGrid,
    CameraOrientedMatrix,
    LowConfidenceDetectionError,
    PieceDetection,
)

logger = logging.getLogger(__name__)


def assign_pieces_to_grid(
    detections: list[PieceDetection],
    grid: CameraOrientedGrid,
) -> tuple[CameraOrientedMatrix, list[list[float]]]:
    """Asigna cada detección a la casilla cuyo cuadrilátero (con
    perspectiva real, ver board_detector.compute_square_grid) contiene
    el punto medio-inferior (bottom-center) del bbox — el ancla en la
    base de la pieza, no su centroide, para no arrastrar el error de
    paralaje de piezas altas vistas en ángulo.

    Retorna (matriz cruda en orientación de cámara, matriz paralela de
    confidence). Las celdas vacías tienen confidence 1.0 (ausencia de
    detección se trata como cierta, no incierta — limitación conocida,
    no distingue "vacía" de "pieza no detectada"). Si dos detecciones
    caen en la misma celda, se conserva la de mayor confidence.
    """
    grid_size = len(grid)
    matrix: CameraOrientedMatrix = [[None] * grid_size for _ in range(grid_size)]
    confidences: list[list[float]] = [[1.0] * grid_size for _ in range(grid_size)]

    for det in detections:
        x1, y1, x2, y2 = det.bbox_px
        anchor = ((x1 + x2) / 2.0, y2)  # bottom-center, base de la pieza

        cell = _find_containing_cell(anchor, grid)
        if cell is None:
            logger.warning(
                "Detección de %s fuera de cualquier casilla (ancla=%s), se descarta",
                det.piece_code,
                anchor,
            )
            continue

        row, col = cell
        if matrix[row][col] is not None and det.confidence <= confidences[row][col]:
            logger.warning(
                "Colisión en celda (%d,%d): se descarta %s (conf=%.2f) a favor de %s (conf=%.2f)",
                row,
                col,
                det.piece_code,
                det.confidence,
                matrix[row][col],
                confidences[row][col],
            )
            continue

        matrix[row][col] = det.piece_code
        confidences[row][col] = det.confidence

    return matrix, confidences


def _find_containing_cell(
    point: tuple[float, float],
    grid: CameraOrientedGrid,
) -> tuple[int, int] | None:
    """Busca la celda de la grilla cuyo cuadrilátero contiene `point`,
    vía cv2.pointPolygonTest. Retorna (row, col) o None si el punto no
    cae dentro de ninguna casilla (ej. pieza fuera del tablero)."""
    for row, grid_row in enumerate(grid):
        for col, quad in enumerate(grid_row):
            polygon = np.array(quad, dtype=np.float32)
            if cv2.pointPolygonTest(polygon, point, False) >= 0:
                return row, col
    return None


def check_confidence(confidences: list[list[float]], threshold: float) -> None:
    """Lanza LowConfidenceDetectionError si alguna celda está por
    debajo de `threshold`. Punto de decisión real de "¿confío en esta
    lectura?" — deliberadamente separado de los umbrales internos de
    detect_pieces (ver nota en piece_classifier.py)."""
    uncertain = [
        (r, c)
        for r, row in enumerate(confidences)
        for c, conf in enumerate(row)
        if conf < threshold
    ]
    if uncertain:
        raise LowConfidenceDetectionError(uncertain)
