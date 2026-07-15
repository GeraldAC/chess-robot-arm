"""Pruebas de chess_vision.orientation."""

import pytest

from chess_vision.orientation import (
    STANDARD_START_MATRIX,
    apply_orientation,
    resolve_orientation,
)
from chess_vision.types import OrientationAmbiguousError


def _rotate_180(matrix):
    return [row[::-1] for row in matrix[::-1]]


def test_resolve_orientation_identity():
    assert resolve_orientation(STANDARD_START_MATRIX) == "identity"


def test_resolve_orientation_rotated_180():
    rotated = _rotate_180(STANDARD_START_MATRIX)
    assert resolve_orientation(rotated) == "rotated_180"


def test_resolve_orientation_ambiguous_mid_game_position():
    mid_game = [row[:] for row in STANDARD_START_MATRIX]
    mid_game[1][4] = None  # se "movió" el peón de la columna 'e'
    mid_game[3][4] = "wP"

    with pytest.raises(OrientationAmbiguousError):
        resolve_orientation(mid_game)


def test_apply_orientation_identity_is_noop():
    result = apply_orientation(STANDARD_START_MATRIX, "identity")
    assert result == STANDARD_START_MATRIX


def test_apply_orientation_rotated_180_matches_manual_rotation():
    rotated = _rotate_180(STANDARD_START_MATRIX)
    result = apply_orientation(rotated, "rotated_180")
    assert result == STANDARD_START_MATRIX
