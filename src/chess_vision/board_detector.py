"""chess_vision.board_detector — M2: detección de las 4 esquinas del
tablero y rectificación a vista cenital.

Se ejecuta en cada frame (no hay homografía estática ni marcadores
físicos — decisión de producto: la cámara puede reposicionarse entre
partidas).
"""

from __future__ import annotations

import cv2
import numpy as np

from chess_vision.types import BoardCorners, BoardNotFoundError, Point2D, RawFrame


def detect_board_corners(
    frame: RawFrame,
    model,  # ultralytics.YOLO cargado (modelo de esquinas, 1 clase)
    conf_threshold: float = 0.5,
) -> BoardCorners:
    """Corre el modelo de esquinas sobre `frame`, ordena los 4 puntos
    en sentido horario desde el de coordenada (x+y) mínima.

    Lanza BoardNotFoundError si no se detectan exactamente 4 puntos
    con confianza >= conf_threshold.
    """
    results = model.predict(frame, verbose=False)[0]

    points: list[Point2D] = []
    confidences: list[float] = []

    for box in results.boxes:
        conf = float(box.conf[0])
        if conf < conf_threshold:
            continue
        x1, y1, x2, y2 = box.xyxy[0]
        points.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
        confidences.append(conf)

    if len(points) != 4:
        raise BoardNotFoundError(
            f"Se esperaban 4 esquinas con confianza >= {conf_threshold}, "
            f"se detectaron {len(points)}."
        )

    ordered_points, ordered_confidences = _order_corners_clockwise(points, confidences)

    return BoardCorners(
        points_px=tuple(ordered_points),  # type: ignore[arg-type]
        confidences=tuple(ordered_confidences),  # type: ignore[arg-type]
    )


def _order_corners_clockwise(
    points: list[Point2D],
    confidences: list[float],
) -> tuple[list[Point2D], list[float]]:
    """Ordena 4 puntos en sentido horario, empezando por el de
    coordenada (x+y) mínima. Es geometría pura de cámara — no asume
    nada sobre a1/h8 (eso lo resuelve orientation.py)."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)

    indexed = list(enumerate(points))
    indexed.sort(key=lambda item: np.arctan2(item[1][1] - cy, item[1][0] - cx))

    start_idx = min(
        range(len(indexed)), key=lambda i: indexed[i][1][0] + indexed[i][1][1]
    )
    indexed = indexed[start_idx:] + indexed[:start_idx]

    ordered_points = [p for _, p in indexed]
    ordered_confidences = [confidences[i] for i, _ in indexed]
    return ordered_points, ordered_confidences


def compute_homography(corners: BoardCorners, output_size: int = 800) -> np.ndarray:
    """Matriz 3x3 (cv2.getPerspectiveTransform) que mapea
    corners.points_px a las esquinas de un lienzo cuadrado de
    output_size x output_size, respetando el mismo orden cíclico."""
    src = np.array(corners.points_px, dtype=np.float32)
    dst = np.array(
        [
            [0, 0],
            [output_size - 1, 0],
            [output_size - 1, output_size - 1],
            [0, output_size - 1],
        ],
        dtype=np.float32,
    )
    return cv2.getPerspectiveTransform(src, dst)


def warp_to_topdown(
    frame: RawFrame,
    homography: np.ndarray,
    output_size: int = 800,
) -> np.ndarray:
    """cv2.warpPerspective: aplica la homografía y retorna la imagen
    rectificada (vista cenital del tablero)."""
    return cv2.warpPerspective(frame, homography, (output_size, output_size))
