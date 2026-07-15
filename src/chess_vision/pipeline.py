"""chess_vision.pipeline — orquesta M2 (board_detector, clásico) + M3
(piece_classifier, modelo pretrained) y produce un VisionInput listo
para chess_brain.parse_vision_input.

Dependencia unidireccional: chess_vision -> chess_brain (chess_brain
no conoce a chess_vision).
"""

from __future__ import annotations

from typing import Literal

from chess_brain.types import VisionInput
from chess_vision.board_detector import compute_square_grid, detect_board_corners
from chess_vision.orientation import apply_orientation, resolve_orientation
from chess_vision.piece_classifier import detect_pieces
from chess_vision.square_mapper import assign_pieces_to_grid, check_confidence
from chess_vision.types import BoardCorners, CameraOrientedGrid, Orientation, RawFrame

# Piso de ruido interno para detect_pieces dentro del pipeline:
# deliberadamente bajo (no es el umbral de decisión de negocio). Ver
# la nota de diseño en piece_classifier.detect_pieces.
_DETECTION_NOISE_FLOOR = 0.1


def locate_board(
    frame: RawFrame,
    corner_detection_kwargs: dict | None = None,
    grid_size: int = 8,
) -> tuple[BoardCorners, CameraOrientedGrid]:
    """Paso de M2 aislado: ubica el tablero y calcula la grilla de
    64 casillas (en coordenadas de la imagen original). Se expone por
    separado porque es el paso más costoso de depurar visualmente."""
    corners = detect_board_corners(frame, **(corner_detection_kwargs or {}))
    grid = compute_square_grid(corners, grid_size=grid_size)
    return corners, grid


def calibrate_orientation(
    frame: RawFrame,
    piece_model,
    corner_detection_kwargs: dict | None = None,
) -> Orientation:
    """Se llama una única vez al inicio de cada partida, con el
    tablero en posición inicial. El resultado debe cachearse por el
    llamador para el resto de la partida."""
    _, grid = locate_board(frame, corner_detection_kwargs)
    detections = detect_pieces(
        frame, piece_model, conf_threshold=_DETECTION_NOISE_FLOOR
    )
    camera_matrix, _ = assign_pieces_to_grid(detections, grid)
    return resolve_orientation(camera_matrix)


def process_frame(
    frame: RawFrame,
    piece_model,
    orientation: Orientation,
    side_to_move: Literal["w", "b"],
    confidence_threshold: float = 0.5,
    corner_detection_kwargs: dict | None = None,
) -> VisionInput:
    """Punto de entrada único del subsistema.

    Lanza BoardNotFoundError o LowConfidenceDetectionError según
    corresponda; nunca retorna una matriz con casillas inciertas
    silenciadas.
    """
    _, grid = locate_board(frame, corner_detection_kwargs)
    detections = detect_pieces(
        frame, piece_model, conf_threshold=_DETECTION_NOISE_FLOOR
    )
    camera_matrix, confidences = assign_pieces_to_grid(detections, grid)

    check_confidence(confidences, confidence_threshold)

    board_matrix = apply_orientation(camera_matrix, orientation)

    return VisionInput(board_matrix=board_matrix, side_to_move=side_to_move)
