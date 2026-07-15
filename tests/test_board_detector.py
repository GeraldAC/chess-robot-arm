"""Pruebas de chess_vision.board_detector (M2, v2 — detección clásica)."""

import cv2
import pytest

from chess_vision.board_detector import compute_square_grid, detect_board_corners
from chess_vision.types import BoardNotFoundError

# Imagen real de tablero, tomada del proyecto comunitario de referencia
# (siromermer/Dynamic-Chess-Board-Piece-Extraction), usada aquí solo
# para validar que la detección funciona con una foto real.
REAL_BOARD_IMAGE_PATH = "tests/fixtures/sample_board.jpeg"


def test_detect_board_corners_on_real_image():
    frame = cv2.imread(REAL_BOARD_IMAGE_PATH)
    assert frame is not None, "No se pudo leer la imagen de prueba"

    corners = detect_board_corners(frame)

    # Las 4 esquinas deben formar un cuadrilátero de tamaño razonable
    # dentro de los límites de la imagen
    h, w = frame.shape[:2]
    for point in (
        corners.top_left,
        corners.top_right,
        corners.bottom_left,
        corners.bottom_right,
    ):
        assert 0 <= point[0] <= w
        assert 0 <= point[1] <= h

    # top_left debe estar arriba-izquierda de bottom_right
    assert corners.top_left[0] < corners.bottom_right[0]
    assert corners.top_left[1] < corners.bottom_right[1]


def test_detect_board_corners_raises_on_blank_image():
    import numpy as np

    blank = np.full((600, 600, 3), 200, dtype=np.uint8)  # imagen lisa, sin tablero

    with pytest.raises(BoardNotFoundError):
        detect_board_corners(blank)


def test_compute_square_grid_shape_and_containment():
    frame = cv2.imread(REAL_BOARD_IMAGE_PATH)
    corners = detect_board_corners(frame)

    grid = compute_square_grid(corners, grid_size=8)

    assert len(grid) == 8
    assert all(len(row) == 8 for row in grid)
    # cada celda es un cuadrilátero de 4 puntos
    assert all(len(cell) == 4 for row in grid for cell in row)


def test_compute_square_grid_cells_are_roughly_contiguous():
    """La esquina inferior-derecha de la celda (0,0) debería estar
    cerca de la esquina superior-izquierda de la celda vecina (0,1)."""
    frame = cv2.imread(REAL_BOARD_IMAGE_PATH)
    corners = detect_board_corners(frame)
    grid = compute_square_grid(corners, grid_size=8)

    cell_00_top_right = grid[0][0][1]
    cell_01_top_left = grid[0][1][0]

    distance = (
        (cell_00_top_right[0] - cell_01_top_left[0]) ** 2
        + (cell_00_top_right[1] - cell_01_top_left[1]) ** 2
    ) ** 0.5
    assert distance < 5.0  # deberían coincidir casi exactamente
