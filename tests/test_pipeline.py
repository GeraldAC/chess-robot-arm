"""Pruebas de integración de chess_vision.pipeline (M2 + M3 -> VisionInput)."""

import numpy as np
import pytest
from fixtures.fake_yolo import FakeYOLOModel

from chess_vision.orientation import STANDARD_START_MATRIX
from chess_vision.pipeline import calibrate_orientation, process_frame
from chess_vision.types import LowConfidenceDetectionError

FRAME = np.zeros((900, 900, 3), dtype=np.uint8)
BOARD_PX = 800  # 8 casillas de 100px

CORNER_DETECTIONS = [
    (0.9, 0, (95, 95, 105, 105)),
    (0.9, 0, (795, 95, 805, 105)),
    (0.9, 0, (795, 795, 805, 805)),
    (0.9, 0, (95, 795, 105, 805)),
]


def _piece_detections_for_standard_start():
    """Genera detecciones cuyo ancla bottom-center cae en cada celda
    ocupada de STANDARD_START_MATRIX, sobre un lienzo de
    BOARD_PX x BOARD_PX (8 casillas de 100px)."""
    detections = []
    class_ids: dict[str, int] = {}
    next_id = 0
    for row in range(8):
        for col in range(8):
            code = STANDARD_START_MATRIX[row][col]
            if code is None:
                continue
            if code not in class_ids:
                class_ids[code] = next_id
                next_id += 1
            cx = col * 100 + 50
            base_y = row * 100 + 90  # base cerca del borde inferior de la celda
            bbox = (cx - 20, base_y - 60, cx + 20, base_y)
            detections.append((0.9, class_ids[code], bbox))
    names = {idx: code for code, idx in class_ids.items()}
    return detections, names


def test_calibrate_orientation_identity():
    piece_dets, names = _piece_detections_for_standard_start()
    board_model = FakeYOLOModel(CORNER_DETECTIONS)
    piece_model = FakeYOLOModel(piece_dets, names=names)

    orientation = calibrate_orientation(
        FRAME, board_model, piece_model, board_px=BOARD_PX
    )

    assert orientation == "identity"


def test_process_frame_returns_valid_vision_input():
    piece_dets, names = _piece_detections_for_standard_start()
    board_model = FakeYOLOModel(CORNER_DETECTIONS)
    piece_model = FakeYOLOModel(piece_dets, names=names)

    vision_input = process_frame(
        FRAME,
        board_model,
        piece_model,
        orientation="identity",
        side_to_move="w",
        board_px=BOARD_PX,
    )

    assert vision_input.board_matrix == STANDARD_START_MATRIX
    assert vision_input.side_to_move == "w"


def test_process_frame_raises_on_low_confidence():
    piece_dets, names = _piece_detections_for_standard_start()
    # Una detección con confianza por debajo del umbral de negocio
    # (0.5) pero por encima del piso de ruido interno (0.1), para que
    # SÍ llegue a check_confidence en vez de ser filtrada antes.
    conf, cls_id, bbox = piece_dets[0]
    piece_dets[0] = (0.2, cls_id, bbox)

    board_model = FakeYOLOModel(CORNER_DETECTIONS)
    piece_model = FakeYOLOModel(piece_dets, names=names)

    with pytest.raises(LowConfidenceDetectionError):
        process_frame(
            FRAME,
            board_model,
            piece_model,
            orientation="identity",
            side_to_move="w",
            board_px=BOARD_PX,
        )
