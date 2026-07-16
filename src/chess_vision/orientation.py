"""chess_vision.orientation — resolución de orientación de ajedrez
(a1/h8) a partir de la matriz cruda en orientación de cámara.

Se usa una única vez por partida (con el tablero en posición
inicial); el resultado se cachea por el llamador para el resto de la
partida. Supuesto vigente: la cámara no queda rotada ~90° entre
remontajes — solo se contemplan 0°/180° (ver Pendiente §8 del SPEC).
"""

from __future__ import annotations

from chess_vision.vision_types import (
    CameraOrientedMatrix,
    Orientation,
    OrientationAmbiguousError,
)

# Posición inicial estándar de ajedrez, en el formato BoardMatrix de
# chess_brain: fila 0 = rank 8, col 0 = 'a'.
STANDARD_START_MATRIX: list[list[str | None]] = [
    ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
    ["bP"] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    ["wP"] * 8,
    ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
]


def _rotate_180(matrix: CameraOrientedMatrix) -> CameraOrientedMatrix:
    return [row[::-1] for row in matrix[::-1]]


def resolve_orientation(camera_matrix: CameraOrientedMatrix) -> Orientation:
    """Compara camera_matrix contra STANDARD_START_MATRIX probando
    identidad y rotación 180°. Retorna la orientación que coincide.

    Lanza OrientationAmbiguousError si ninguna coincide (ej. se llamó
    a mitad de partida en vez de con la posición inicial).
    """
    if camera_matrix == STANDARD_START_MATRIX:
        return "identity"
    if _rotate_180(camera_matrix) == STANDARD_START_MATRIX:
        return "rotated_180"
    raise OrientationAmbiguousError(
        "La matriz detectada no coincide con la posición inicial estándar "
        "en ninguna orientación evaluada (identity / rotated_180). "
        "¿Se llamó a mitad de partida, o la detección de piezas falló?"
    )


def apply_orientation(
    camera_matrix: CameraOrientedMatrix,
    orientation: Orientation,
) -> list[list[str | None]]:
    """Aplica la rotación ya resuelta. Función pura, sin estado."""
    if orientation == "identity":
        return camera_matrix
    return _rotate_180(camera_matrix)
