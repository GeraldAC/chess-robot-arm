"""Pruebas de chess_vision.piece_classifier (M3)."""

import numpy as np
from fixtures.fake_yolo import FakeYOLOModel

from chess_vision.piece_classifier import detect_pieces

IMAGE = np.zeros((800, 800, 3), dtype=np.uint8)
NAMES = {0: "wP", 1: "bK"}


def test_detect_pieces_returns_expected_codes():
    model = FakeYOLOModel(
        detections=[(0.8, 0, (10, 10, 50, 50)), (0.9, 1, (700, 700, 740, 740))],
        names=NAMES,
    )

    result = detect_pieces(IMAGE, model)

    assert len(result) == 2
    codes = {det.piece_code for det in result}
    assert codes == {"wP", "bK"}


def test_detect_pieces_filters_low_confidence():
    model = FakeYOLOModel(detections=[(0.1, 0, (10, 10, 50, 50))], names=NAMES)

    result = detect_pieces(IMAGE, model, conf_threshold=0.4)

    assert result == []


def test_detect_pieces_empty_board():
    model = FakeYOLOModel(detections=[], names=NAMES)

    result = detect_pieces(IMAGE, model)

    assert result == []
