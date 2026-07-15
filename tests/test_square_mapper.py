"""Pruebas de chess_vision.square_mapper."""

import pytest

from chess_vision.square_mapper import build_camera_matrix, check_confidence
from chess_vision.types import LowConfidenceDetectionError, PieceDetection

BOARD_PX = 800  # 8 casillas de 100px


def test_tall_piece_assigned_by_bottom_anchor():
    # bbox que "se extiende" hacia arriba por perspectiva, pero cuya
    # base real (borde inferior) está en la fila 7
    det = PieceDetection(piece_code="wK", bbox_px=(20, 620, 80, 750), confidence=0.9)

    matrix, confidences = build_camera_matrix([det], board_px=BOARD_PX)

    assert matrix[7][0] == "wK"
    assert confidences[7][0] == 0.9


def test_collision_keeps_highest_confidence():
    det_low = PieceDetection(piece_code="wP", bbox_px=(10, 10, 90, 90), confidence=0.4)
    det_high = PieceDetection(piece_code="bP", bbox_px=(15, 15, 85, 85), confidence=0.8)

    matrix, confidences = build_camera_matrix([det_low, det_high], board_px=BOARD_PX)

    assert matrix[0][0] == "bP"
    assert confidences[0][0] == 0.8


def test_check_confidence_raises_with_correct_cells():
    confidences = [[1.0] * 8 for _ in range(8)]
    confidences[3][4] = 0.2

    with pytest.raises(LowConfidenceDetectionError) as exc_info:
        check_confidence(confidences, threshold=0.5)

    assert exc_info.value.uncertain_cells == [(3, 4)]


def test_check_confidence_passes_when_all_above_threshold():
    confidences = [[0.9] * 8 for _ in range(8)]
    check_confidence(confidences, threshold=0.5)  # no debe lanzar
