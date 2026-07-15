"""chess_vision.square_mapper — asigna detecciones de pieza (bboxes)
a casillas de la grilla 8x8, y decide si la confianza resultante es
suficiente para confiar en la lectura.
"""

from __future__ import annotations

import logging

from chess_vision.types import (
    CameraOrientedMatrix,
    LowConfidenceDetectionError,
    PieceDetection,
)

logger = logging.getLogger(__name__)


def build_camera_matrix(
    detections: list[PieceDetection],
    board_px: int,
    grid_size: int = 8,
) -> tuple[CameraOrientedMatrix, list[list[float]]]:
    """Asigna cada detección a una celda usando el punto medio-inferior
    (bottom-center) del bbox como ancla — corrige el error de
    paralaje de piezas altas (rey/dama) vistas en ángulo, que de otro
    modo "invadirían" visualmente la casilla de atrás.

    Retorna (matriz cruda en orientación de cámara, matriz paralela de
    confidence). Las celdas vacías tienen confidence 1.0 (ausencia de
    detección se trata como cierta, no incierta — ver limitación
    conocida en la guía de tareas: no distingue "vacía" de "pieza no
    detectada"). Si dos detecciones caen en la misma celda, se
    conserva la de mayor confidence y se registra la colisión.
    """
    cell_size = board_px / grid_size

    matrix: CameraOrientedMatrix = [[None] * grid_size for _ in range(grid_size)]
    confidences: list[list[float]] = [[1.0] * grid_size for _ in range(grid_size)]

    for det in detections:
        x1, y1, x2, y2 = det.bbox_px
        anchor_x = (x1 + x2) / 2.0
        anchor_y = y2  # borde inferior del bbox = base de la pieza sobre el tablero

        col = int(anchor_x // cell_size)
        row = int(anchor_y // cell_size)

        if not (0 <= row < grid_size and 0 <= col < grid_size):
            logger.warning(
                "Detección de %s fuera del área del tablero (ancla=%s,%s), se descarta",
                det.piece_code,
                anchor_x,
                anchor_y,
            )
            continue

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


def check_confidence(confidences: list[list[float]], threshold: float) -> None:
    """Lanza LowConfidenceDetectionError si alguna celda está por
    debajo de `threshold`. Este es el punto de decisión real de
    "¿confío en esta lectura?" — deliberadamente separado de los
    umbrales internos de detect_pieces (ver nota en piece_classifier.py).
    """
    uncertain = [
        (r, c)
        for r, row in enumerate(confidences)
        for c, conf in enumerate(row)
        if conf < threshold
    ]
    if uncertain:
        raise LowConfidenceDetectionError(uncertain)
