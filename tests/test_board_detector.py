"""Pruebas de chess_vision.board_detector (M2)."""

import numpy as np
import pytest
from fixtures.fake_yolo import FakeYOLOModel

from chess_vision.board_detector import (
    compute_homography,
    detect_board_corners,
    warp_to_topdown,
)
from chess_vision.types import BoardNotFoundError

FRAME = np.zeros((600, 600, 3), dtype=np.uint8)

_FOUR_CORNERS = [
    (0.9, 0, (95, 95, 105, 105)),  # top-left
    (0.9, 0, (495, 95, 505, 105)),  # top-right
    (0.9, 0, (495, 495, 505, 505)),  # bottom-right
    (0.9, 0, (95, 495, 105, 505)),  # bottom-left
]


def test_detect_board_corners_happy_path():
    model = FakeYOLOModel(_FOUR_CORNERS)

    corners = detect_board_corners(FRAME, model)

    assert len(corners.points_px) == 4
    assert len(corners.confidences) == 4
    # El primer punto debe ser el de (x+y) mínima (top-left)
    assert corners.points_px[0] == pytest.approx((100.0, 100.0))


def test_detect_board_corners_not_found_insufficient_detections():
    model = FakeYOLOModel([(0.9, 0, (100, 100, 110, 110))])  # solo 1 esquina

    with pytest.raises(BoardNotFoundError):
        detect_board_corners(FRAME, model)


def test_detect_board_corners_filters_low_confidence():
    detections = _FOUR_CORNERS[:3] + [
        (0.2, 0, (95, 495, 105, 505))
    ]  # 1 por debajo del umbral
    model = FakeYOLOModel(detections)

    with pytest.raises(BoardNotFoundError):
        detect_board_corners(FRAME, model, conf_threshold=0.5)


def test_homography_and_warp_produce_square_image():
    model = FakeYOLOModel(_FOUR_CORNERS)
    corners = detect_board_corners(FRAME, model)

    homography = compute_homography(corners, output_size=400)
    topdown = warp_to_topdown(FRAME, homography, output_size=400)

    assert topdown.shape[:2] == (400, 400)
