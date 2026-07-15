"""Pruebas de chess_vision.piece_classifier (M3, v2 — modelo pretrained comunitario)."""

import numpy as np
from fixtures.fake_yolo import FakeYOLOModel

from chess_vision.piece_classifier import COMMUNITY_YOLOV8M_CLASS_MAP, detect_pieces

IMAGE = np.zeros((1200, 900, 3), dtype=np.uint8)

# Nombres crudos tal como los produce el modelo comunitario (no
# nuestro alfabeto wP/bK/...)
COMMUNITY_NAMES = {0: "white-pawn", 1: "black-king"}


def test_detect_pieces_translates_community_names_to_our_alphabet():
    model = FakeYOLOModel(
        detections=[(0.8, 0, (10, 10, 50, 50)), (0.9, 1, (700, 700, 740, 740))],
        names=COMMUNITY_NAMES,
    )

    result = detect_pieces(IMAGE, model)

    codes = {det.piece_code for det in result}
    assert codes == {"wP", "bK"}


def test_detect_pieces_filters_low_confidence():
    model = FakeYOLOModel(
        detections=[(0.1, 0, (10, 10, 50, 50))], names=COMMUNITY_NAMES
    )

    result = detect_pieces(IMAGE, model, conf_threshold=0.4)

    assert result == []


def test_detect_pieces_empty_board():
    model = FakeYOLOModel(detections=[], names=COMMUNITY_NAMES)

    result = detect_pieces(IMAGE, model)

    assert result == []


def test_detect_pieces_bbox_values_are_plain_floats():
    """Importante: el bbox debe quedar como floats de Python, no
    tensores — necesario para que square_mapper pueda construir
    arreglos numpy sin sorpresas de tipo."""
    model = FakeYOLOModel(
        detections=[(0.8, 0, (10, 10, 50, 50))], names=COMMUNITY_NAMES
    )

    result = detect_pieces(IMAGE, model)

    assert all(isinstance(v, float) for v in result[0].bbox_px)


def test_class_map_covers_all_12_standard_pieces():
    expected_codes = {
        f"{color}{piece}"
        for color in ("w", "b")
        for piece in ("P", "N", "B", "R", "Q", "K")
    }
    assert set(COMMUNITY_YOLOV8M_CLASS_MAP.values()) == expected_codes
