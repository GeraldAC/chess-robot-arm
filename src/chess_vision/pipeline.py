"""chess_vision.pipeline — orquesta M2 (board_detector) + M3
(piece_classifier) y produce un VisionInput listo para
chess_brain.parse_vision_input.

Dependencia unidireccional: chess_vision -> chess_brain (chess_brain
no conoce a chess_vision).
"""

from __future__ import annotations

from typing import Literal

from chess_brain.types import VisionInput
from chess_vision.board_detector import (
    compute_homography,
    detect_board_corners,
    warp_to_topdown,
)
from chess_vision.orientation import apply_orientation, resolve_orientation
from chess_vision.piece_classifier import detect_pieces
from chess_vision.square_mapper import build_camera_matrix, check_confidence
from chess_vision.types import Orientation, RawFrame

# Piso de ruido interno para detect_pieces dentro del pipeline:
# deliberadamente bajo (no es el umbral de decisión de negocio). Ver
# la nota de diseño en piece_classifier.detect_pieces.
_DETECTION_NOISE_FLOOR = 0.1


def calibrate_orientation(
    frame: RawFrame,
    board_model,
    piece_model,
    board_px: int = 800,
) -> Orientation:
    """Se llama una única vez al inicio de cada partida, con el
    tablero en posición inicial. El resultado debe cachearse por el
    llamador (ej. el CLI o el futuro Orquestador) para el resto de la
    partida."""
    corners = detect_board_corners(frame, board_model)
    homography = compute_homography(corners, output_size=board_px)
    topdown = warp_to_topdown(frame, homography, output_size=board_px)
    detections = detect_pieces(
        topdown, piece_model, conf_threshold=_DETECTION_NOISE_FLOOR
    )
    camera_matrix, _ = build_camera_matrix(detections, board_px)
    return resolve_orientation(camera_matrix)


def process_frame(
    frame: RawFrame,
    board_model,
    piece_model,
    orientation: Orientation,
    side_to_move: Literal["w", "b"],
    board_px: int = 800,
    confidence_threshold: float = 0.5,
) -> VisionInput:
    """Punto de entrada único del subsistema.

    Lanza BoardNotFoundError o LowConfidenceDetectionError según
    corresponda; nunca retorna una matriz con casillas inciertas
    silenciadas.
    """
    corners = detect_board_corners(frame, board_model)
    homography = compute_homography(corners, output_size=board_px)
    topdown = warp_to_topdown(frame, homography, output_size=board_px)
    detections = detect_pieces(
        topdown, piece_model, conf_threshold=_DETECTION_NOISE_FLOOR
    )
    camera_matrix, confidences = build_camera_matrix(detections, board_px)

    check_confidence(confidences, confidence_threshold)

    board_matrix = apply_orientation(camera_matrix, orientation)

    return VisionInput(board_matrix=board_matrix, side_to_move=side_to_move)
