"""Pruebas de integración de chess_vision.pipeline (v2: detección
clásica de tablero + modelo pretrained de piezas -> VisionInput).

Usa la imagen real (tests/fixtures/sample_board.jpeg) solo para
obtener geometría de casillas realista (con perspectiva) vía
board_detector; las detecciones de pieza son sintéticas (vía
FakeYOLOModel) para poder controlar exactamente qué posición se está
probando, independientemente de qué haya realmente en esa foto.
"""

import cv2
import pytest
from fixtures.fake_yolo import FakeYOLOModel

from chess_vision.orientation import STANDARD_START_MATRIX
from chess_vision.pipeline import calibrate_orientation, locate_board, process_frame
from chess_vision.vision_types import LowConfidenceDetectionError

FRAME = cv2.imread("tests/fixtures/sample_board.jpeg")


def _centroid(quad):
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return sum(xs) / 4, sum(ys) / 4


def _piece_detections_for_standard_start(grid):
    """Genera detecciones cuyo ancla (bottom-center del bbox) cae en
    el centroide de cada celda ocupada de STANDARD_START_MATRIX,
    usando la geometría REAL de `grid` (con perspectiva)."""
    detections = []
    names: dict[int, str] = {}
    next_id = 0
    reverse_map = {  # nuestro alfabeto -> nombre "crudo" estilo modelo comunitario
        "bR": "black-rook",
        "bN": "black-knight",
        "bB": "black-bishop",
        "bQ": "black-queen",
        "bK": "black-king",
        "bP": "black-pawn",
        "wR": "white-rook",
        "wN": "white-knight",
        "wB": "white-bishop",
        "wQ": "white-queen",
        "wK": "white-king",
        "wP": "white-pawn",
    }

    for row in range(8):
        for col in range(8):
            code = STANDARD_START_MATRIX[row][col]
            if code is None:
                continue
            raw_name = reverse_map[code]
            if raw_name not in names.values():
                names[next_id] = raw_name
                class_id = next_id
                next_id += 1
            else:
                class_id = next(k for k, v in names.items() if v == raw_name)

            cx, cy = _centroid(grid[row][col])
            bbox = (cx - 15, cy - 40, cx + 15, cy)
            detections.append((0.9, class_id, bbox))

    return detections, names


def test_calibrate_orientation_identity():
    _, grid = locate_board(FRAME)
    piece_dets, names = _piece_detections_for_standard_start(grid)
    piece_model = FakeYOLOModel(piece_dets, names=names)

    orientation = calibrate_orientation(FRAME, piece_model)

    assert orientation == "identity"


def test_process_frame_returns_valid_vision_input():
    _, grid = locate_board(FRAME)
    piece_dets, names = _piece_detections_for_standard_start(grid)
    piece_model = FakeYOLOModel(piece_dets, names=names)

    vision_input = process_frame(
        FRAME,
        piece_model,
        orientation="identity",
        side_to_move="w",
    )

    assert vision_input.board_matrix == STANDARD_START_MATRIX
    assert vision_input.side_to_move == "w"


def test_process_frame_raises_on_low_confidence():
    _, grid = locate_board(FRAME)
    piece_dets, names = _piece_detections_for_standard_start(grid)
    conf, cls_id, bbox = piece_dets[0]
    piece_dets[0] = (0.2, cls_id, bbox)  # por debajo del umbral de negocio (0.5)
    piece_model = FakeYOLOModel(piece_dets, names=names)

    with pytest.raises(LowConfidenceDetectionError):
        process_frame(FRAME, piece_model, orientation="identity", side_to_move="w")
