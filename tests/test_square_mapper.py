"""Pruebas de chess_vision.square_mapper (v2 — point-in-polygon)."""

import pytest

from chess_vision.square_mapper import assign_pieces_to_grid, check_confidence
from chess_vision.types import LowConfidenceDetectionError, PieceDetection

CELL = 100  # px, grilla simple sin perspectiva para pruebas (8x8, celdas de 100px)


def _flat_grid(grid_size: int = 8, cell: int = CELL):
    """Grilla sintética SIN perspectiva (cuadrados alineados a los
    ejes) — suficiente para probar la lógica de asignación sin
    depender de board_detector."""
    grid = []
    for row in range(grid_size):
        grid_row = []
        for col in range(grid_size):
            top_left = (col * cell, row * cell)
            top_right = ((col + 1) * cell, row * cell)
            bottom_right = ((col + 1) * cell, (row + 1) * cell)
            bottom_left = (col * cell, (row + 1) * cell)
            grid_row.append((top_left, top_right, bottom_right, bottom_left))
        grid.append(grid_row)
    return grid


def test_piece_assigned_to_correct_cell_by_bottom_anchor():
    grid = _flat_grid()
    # bbox cuya base (y2) cae en la fila 7, columna 0
    det = PieceDetection(piece_code="wK", bbox_px=(20, 620, 80, 750), confidence=0.9)

    matrix, confidences = assign_pieces_to_grid([det], grid)

    assert matrix[7][0] == "wK"
    assert confidences[7][0] == 0.9


def test_piece_outside_board_is_discarded():
    grid = _flat_grid()
    det = PieceDetection(
        piece_code="wP", bbox_px=(-100, -100, -80, -80), confidence=0.9
    )

    matrix, _ = assign_pieces_to_grid([det], grid)

    assert all(cell is None for row in matrix for cell in row)


def test_collision_keeps_highest_confidence():
    grid = _flat_grid()
    det_low = PieceDetection(piece_code="wP", bbox_px=(10, 10, 90, 90), confidence=0.4)
    det_high = PieceDetection(piece_code="bP", bbox_px=(15, 15, 85, 85), confidence=0.8)

    matrix, confidences = assign_pieces_to_grid([det_low, det_high], grid)

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
