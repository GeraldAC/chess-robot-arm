"""chess_vision.board_detector — M2: detección del tablero SIN
machine learning — solo OpenCV clásico (umbral OTSU, Canny,
HoughLinesP, contornos geométricos).

v2: técnica adaptada de la detección de tablero usada en el proyecto
comunitario "Dynamic-Chess-Board-Piece-Extraction" (siromermer,
https://github.com/siromermer/Dynamic-Chess-Board-Piece-Extraction),
publicado como base de la app Chesspector. No requiere entrenar nada
— es geometría, no un modelo. Ver M2_M3_SPEC.md
para el porqué de este cambio de enfoque.

A diferencia de v1, este módulo NO deforma la imagen para detectar
piezas — solo calcula, para cada una de las 64 casillas, su
cuadrilátero en coordenadas de la imagen ORIGINAL (ver
compute_square_grid). La deformación (warp) queda disponible como
utilidad de diagnóstico/visualización, no como parte del pipeline de
detección.
"""

from __future__ import annotations

import cv2
import numpy as np

from chess_vision.vision_types import (
    BoardCorners,
    BoardNotFoundError,
    CameraOrientedGrid,
    RawFrame,
)


def detect_board_corners(
    frame: RawFrame,
    contour_area_range: tuple[int, int] = (2000, 20000),
    side_length_tolerance: float = 35.0,
    hough_threshold: int = 500,
    hough_min_line_length: int = 150,
    hough_max_line_gap: int = 100,
) -> BoardCorners:
    """Ubica las 4 esquinas extremas del tablero mediante geometría
    clásica: umbral OTSU + Canny + HoughLinesP para las líneas de las
    casillas, filtrado de contornos "geométricamente cuadrados"
    (4 lados de longitud similar), y extracción de las esquinas
    extremas del contorno combinado más grande.

    Los parámetros por defecto están calibrados para fotos de
    resolución similar a un smartphone moderno con el tablero
    ocupando gran parte del encuadre, luz estándar. Pueden requerir
    ajuste según la cámara/distancia real — no son un valor
    universal, son un punto de partida ya validado por la comunidad.

    Lanza BoardNotFoundError si no se encuentra un contorno de
    tablero válido con estos parámetros.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(otsu, 20, 255)
    edges = cv2.dilate(edges, np.ones((7, 7), np.uint8), iterations=1)

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=hough_threshold,
        minLineLength=hough_min_line_length,
        maxLineGap=hough_max_line_gap,
    )
    if lines is None:
        raise BoardNotFoundError(
            "No se detectaron líneas suficientes para ubicar el tablero. "
            "¿La imagen tiene buen contraste y el tablero está bien enfocado?"
        )

    lines_image = np.zeros(gray.shape, dtype=np.uint8)

    # AJUSTE DE ROBUSTEZ: Redimensionamos la matriz de líneas a (N, 4) para evitar
    # problemas de desempaquetado si OpenCV la devuelve con dimensiones extra.
    for line in lines.reshape(-1, 4):
        x1, y1, x2, y2 = line
        cv2.line(lines_image, (x1, y1), (x2, y2), 255, 2)

    lines_image = cv2.dilate(lines_image, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(lines_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    valid_squares_image = np.zeros(gray.shape, dtype=np.uint8)
    min_area, max_area = contour_area_range
    found_valid_square = False

    for contour in contours:
        area = cv2.contourArea(contour)
        if not (min_area < area < max_area):
            continue

        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) != 4:
            continue

        pts = _order_quad_points(approx.reshape(4, 2))
        side_lengths = [
            float(np.linalg.norm(np.array(pts[i]) - np.array(pts[(i + 1) % 4])))
            for i in range(4)
        ]
        if max(side_lengths) - min(side_lengths) > side_length_tolerance:
            continue

        found_valid_square = True
        for i in range(4):
            cv2.line(valid_squares_image, pts[i], pts[(i + 1) % 4], 255, 7)

    if not found_valid_square:
        raise BoardNotFoundError(
            "No se encontraron cuadrados geométricamente válidos (posibles "
            "casillas) en la imagen. Prueba ajustando contour_area_range "
            "según la resolución/distancia real de tu cámara."
        )

    dilated = cv2.dilate(valid_squares_image, np.ones((7, 7), np.uint8), iterations=1)
    board_contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not board_contours:
        raise BoardNotFoundError(
            "No se pudo determinar el contorno combinado del tablero."
        )

    largest = max(board_contours, key=cv2.contourArea)
    return _extreme_corners(largest)


def _order_quad_points(pts: np.ndarray) -> list[tuple[int, int]]:
    """Ordena 4 puntos de un cuadrilátero en: bottomright, topright,
    topleft, bottomleft (mismo criterio que el proyecto de referencia)."""
    pts_list = [tuple(int(v) for v in p) for p in pts.tolist()]
    index_sorted = sorted(pts_list, key=lambda p: p[0], reverse=True)
    if index_sorted[0][1] < index_sorted[1][1]:
        index_sorted[0], index_sorted[1] = index_sorted[1], index_sorted[0]
    if index_sorted[2][1] > index_sorted[3][1]:
        index_sorted[2], index_sorted[3] = index_sorted[3], index_sorted[2]
    return index_sorted


def _extreme_corners(contour: np.ndarray) -> BoardCorners:
    """Encuentra las 4 esquinas extremas (top_left, top_right,
    bottom_left, bottom_right) de un contorno, usando el mismo truco
    geométrico que board_detector usa para ordenar puntos: (x+y)
    mínima/máxima y (x-y) mínima/máxima."""
    top_left = top_right = bottom_left = bottom_right = None
    for point in contour[:, 0]:
        x, y = int(point[0]), int(point[1])
        if top_left is None or (x + y < top_left[0] + top_left[1]):
            top_left = (x, y)
        if top_right is None or (x - y > top_right[0] - top_right[1]):
            top_right = (x, y)
        if bottom_left is None or (x - y < bottom_left[0] - bottom_left[1]):
            bottom_left = (x, y)
        if bottom_right is None or (x + y > bottom_right[0] + bottom_right[1]):
            bottom_right = (x, y)
    return BoardCorners(
        top_left=top_left,
        top_right=top_right,
        bottom_left=bottom_left,
        bottom_right=bottom_right,
    )


def compute_square_grid(
    corners: BoardCorners,
    grid_size: int = 8,
    canvas_size: int = 1200,
) -> CameraOrientedGrid:
    """Calcula el cuadrilátero, EN COORDENADAS DE LA IMAGEN ORIGINAL,
    de cada una de las grid_size x grid_size casillas — sin deformar
    la imagen real.

    Estrategia: se calcula la homografía hacia un lienzo cuadrado
    plano de canvas_size x canvas_size, se genera ahí una grilla
    uniforme (trivial en espacio plano), y se retro-proyectan las
    esquinas de cada celda al espacio original con la homografía
    inversa (cv2.perspectiveTransform). Esto preserva la perspectiva
    real de cada casilla, lo cual importa porque las piezas se
    detectan sobre la imagen original (ver piece_classifier.py) —
    deformar la imagen distorsiona la apariencia 3D de las piezas
    altas de forma poco natural.
    """
    src = np.array(
        [
            corners.top_left,
            corners.top_right,
            corners.bottom_left,
            corners.bottom_right,
        ],
        dtype=np.float32,
    )
    dst = np.array(
        [[0, 0], [canvas_size, 0], [0, canvas_size], [canvas_size, canvas_size]],
        dtype=np.float32,
    )
    homography = cv2.getPerspectiveTransform(src, dst)
    inverse_homography = np.linalg.inv(homography)

    cell_size = canvas_size / grid_size
    grid: CameraOrientedGrid = []

    for row in range(grid_size):
        grid_row = []
        for col in range(grid_size):
            warped_quad = np.array(
                [
                    [col * cell_size, row * cell_size],
                    [(col + 1) * cell_size, row * cell_size],
                    [(col + 1) * cell_size, (row + 1) * cell_size],
                    [col * cell_size, (row + 1) * cell_size],
                ],
                dtype=np.float32,
            ).reshape(-1, 1, 2)
            original_quad = cv2.perspectiveTransform(warped_quad, inverse_homography)
            grid_row.append(
                tuple((float(pt[0][0]), float(pt[0][1])) for pt in original_quad)
            )
        grid.append(grid_row)

    return grid


def compute_homography(corners: BoardCorners, canvas_size: int = 1200) -> np.ndarray:
    """Utilidad de DIAGNÓSTICO/VISUALIZACIÓN — no forma parte del
    camino de detección (ver docstring del módulo). Útil para mostrar
    una vista cenital rectificada al usuario, p.ej. en el CLI."""
    src = np.array(
        [
            corners.top_left,
            corners.top_right,
            corners.bottom_left,
            corners.bottom_right,
        ],
        dtype=np.float32,
    )
    dst = np.array(
        [[0, 0], [canvas_size, 0], [0, canvas_size], [canvas_size, canvas_size]],
        dtype=np.float32,
    )
    return cv2.getPerspectiveTransform(src, dst)


def warp_to_topdown(
    frame: RawFrame, homography: np.ndarray, canvas_size: int = 1200
) -> np.ndarray:
    """Utilidad de DIAGNÓSTICO/VISUALIZACIÓN — ver compute_homography."""
    return cv2.warpPerspective(frame, homography, (canvas_size, canvas_size))
