"""Interpolación y validación geométrica para chess_calibration (M0).

`compute_square_centers` es el análogo, en espacio real (mm), de
`board_detector.compute_square_grid` (M2) en espacio de píxeles: ambos
resuelven una grilla 8x8 a partir de 4 esquinas conocidas. Aquí no hay
homografía de perspectiva porque la medición física ya es plana por
definición del método (regla/calibre), a diferencia de una foto de cámara
donde sí hay que corregir perspectiva.
"""

from __future__ import annotations

import math

from chess_calibration.calibration_types import (
    ArmPoint,
    BoardCornersArm,
    InvalidBoardGeometryError,
)

FILES = "abcdefgh"
RANKS = "12345678"


def _lerp_point(p0: ArmPoint, p1: ArmPoint, t: float) -> ArmPoint:
    return ArmPoint(
        x_mm=p0.x_mm + (p1.x_mm - p0.x_mm) * t,
        y_mm=p0.y_mm + (p1.y_mm - p0.y_mm) * t,
        z_mm=p0.z_mm + (p1.z_mm - p0.z_mm) * t,
    )


def _distance(p0: ArmPoint, p1: ArmPoint) -> float:
    return math.sqrt(
        (p1.x_mm - p0.x_mm) ** 2 + (p1.y_mm - p0.y_mm) ** 2 + (p1.z_mm - p0.z_mm) ** 2
    )


def compute_square_centers(
    corners: BoardCornersArm,
    grid_size: int = 8,
) -> dict[str, ArmPoint]:
    """Interpolación bilineal en (x, y, z) de los 4 centros medidos ->
    centro de cada una de las 64 casillas, en coordenadas del brazo.

    Convención de índices:
        a1 = corners.a1  (file_index=0, rank_index=0)
        h1 = corners.h1  (file_index=grid_size-1, rank_index=0)
        a8 = corners.a8  (file_index=0, rank_index=grid_size-1)
        h8 = corners.h8  (file_index=grid_size-1, rank_index=grid_size-1)

    "file" recorre a..h (columna, eje corto a1->h1); "rank" recorre 1..8
    (fila, eje largo a1->a8).
    """
    if grid_size < 2:
        raise ValueError("grid_size debe ser >= 2 para poder interpolar")
    if grid_size > len(FILES) or grid_size > len(RANKS):
        raise ValueError(
            f"grid_size no puede superar {len(FILES)} (alfabeto de ajedrez)"
        )

    centers: dict[str, ArmPoint] = {}
    for rank_index in range(grid_size):
        v = rank_index / (grid_size - 1)
        left = _lerp_point(corners.a1, corners.a8, v)  # borde file=0 (a1->a8)
        right = _lerp_point(
            corners.h1, corners.h8, v
        )  # borde file=grid_size-1 (h1->h8)
        for file_index in range(grid_size):
            u = file_index / (grid_size - 1)
            point = _lerp_point(left, right, u)
            square = f"{FILES[file_index]}{RANKS[rank_index]}"
            centers[square] = point
    return centers


def validate_board_geometry(
    corners: BoardCornersArm,
    expected_square_size_mm: float,
    tolerance_mm: float = 5.0,
) -> None:
    """Verifica, dentro de `tolerance_mm`, que las distancias entre los 4
    centros medidos sean consistentes con un tablero de
    `expected_square_size_mm` por casilla. No exige perfección
    geométrica: solo atrapa errores gruesos de medición o de tipeo antes
    de que lleguen a un `PhysicalPlan` real (M6).

    Lanza InvalidBoardGeometryError si alguna distancia se sale de
    tolerancia.
    """
    if expected_square_size_mm <= 0:
        raise ValueError("expected_square_size_mm debe ser > 0")
    if tolerance_mm < 0:
        raise ValueError("tolerance_mm no puede ser negativo")

    span = 7 * expected_square_size_mm  # centro a1 -> centro h1/a8 son 7 casillas
    diag = span * math.sqrt(2)

    measured = {
        "a1_h1": _distance(corners.a1, corners.h1),
        "a8_h8": _distance(corners.a8, corners.h8),
        "a1_a8": _distance(corners.a1, corners.a8),
        "h1_h8": _distance(corners.h1, corners.h8),
        "a1_h8": _distance(corners.a1, corners.h8),
        "a8_h1": _distance(corners.a8, corners.h1),
    }
    expected = {
        "a1_h1": span,
        "a8_h8": span,
        "a1_a8": span,
        "h1_h8": span,
        "a1_h8": diag,
        "a8_h1": diag,
    }

    offending = {
        key: measured[key]
        for key in measured
        if abs(measured[key] - expected[key]) > tolerance_mm
    }
    if offending:
        detail = ", ".join(
            f"{key}: medido={measured[key]:.1f}mm esperado={expected[key]:.1f}mm"
            for key in offending
        )
        raise InvalidBoardGeometryError(
            f"Geometría del tablero fuera de tolerancia ({tolerance_mm}mm): {detail}",
            measured=measured,
            expected=expected,
        )
