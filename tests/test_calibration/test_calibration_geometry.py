import pytest

from chess_calibration.calibration_geometry import (
    compute_square_centers,
    validate_board_geometry,
)
from chess_calibration.calibration_types import (
    ArmPoint,
    BoardCornersArm,
    InvalidBoardGeometryError,
)

SQUARE_SIZE_MM = 40.0


@pytest.fixture
def square_corners() -> BoardCornersArm:
    """Tablero cuadrado, alineado a ejes, sin inclinación."""
    return BoardCornersArm(
        a1=ArmPoint(0.0, 0.0, 10.0),
        a8=ArmPoint(0.0, 280.0, 10.0),
        h1=ArmPoint(280.0, 0.0, 10.0),
        h8=ArmPoint(280.0, 280.0, 10.0),
    )


class TestComputeSquareCenters:
    def test_returns_64_squares(self, square_corners):
        centers = compute_square_centers(square_corners)
        assert len(centers) == 64
        expected_keys = {f"{f}{r}" for f in "abcdefgh" for r in "12345678"}
        assert set(centers.keys()) == expected_keys

    def test_corners_match_measured_input_exactly(self, square_corners):
        centers = compute_square_centers(square_corners)
        assert centers["a1"] == square_corners.a1
        assert centers["a8"] == square_corners.a8
        assert centers["h1"] == square_corners.h1
        assert centers["h8"] == square_corners.h8

    def test_interior_square_interpolated_correctly(self, square_corners):
        # d4: file_index=3 (d), rank_index=3 (4) -> step de 40mm por casilla
        centers = compute_square_centers(square_corners)
        d4 = centers["d4"]
        assert d4.x_mm == pytest.approx(120.0)
        assert d4.y_mm == pytest.approx(120.0)
        assert d4.z_mm == pytest.approx(10.0)

    def test_tolerates_tilted_board(self):
        # z distinto por esquina: la interpolación también debe cubrir z
        tilted = BoardCornersArm(
            a1=ArmPoint(0.0, 0.0, 0.0),
            a8=ArmPoint(0.0, 280.0, 14.0),
            h1=ArmPoint(280.0, 0.0, 0.0),
            h8=ArmPoint(280.0, 280.0, 14.0),
        )
        centers = compute_square_centers(tilted)
        # a4/h4 (rank_index=3, v=3/7) deberían tener z intermedio proporcional
        expected_z = 14.0 * (3 / 7)
        assert centers["a4"].z_mm == pytest.approx(expected_z)
        assert centers["h4"].z_mm == pytest.approx(expected_z)

    def test_invalid_grid_size_raises(self, square_corners):
        with pytest.raises(ValueError):
            compute_square_centers(square_corners, grid_size=1)


class TestValidateBoardGeometry:
    def test_valid_geometry_does_not_raise(self, square_corners):
        validate_board_geometry(square_corners, expected_square_size_mm=SQUARE_SIZE_MM)

    def test_geometry_outside_tolerance_raises(self, square_corners):
        distorted = BoardCornersArm(
            a1=square_corners.a1,
            a8=square_corners.a8,
            h1=ArmPoint(320.0, 0.0, 10.0),  # +40mm de error grosero
            h8=square_corners.h8,
        )
        with pytest.raises(InvalidBoardGeometryError):
            validate_board_geometry(distorted, expected_square_size_mm=SQUARE_SIZE_MM)

    def test_small_error_within_tolerance_does_not_raise(self, square_corners):
        slightly_off = BoardCornersArm(
            a1=square_corners.a1,
            a8=square_corners.a8,
            h1=ArmPoint(282.0, 0.0, 10.0),  # +2mm, dentro de tolerancia default (5mm)
            h8=square_corners.h8,
        )
        validate_board_geometry(slightly_off, expected_square_size_mm=SQUARE_SIZE_MM)

    def test_wrong_expected_square_size_raises(self, square_corners):
        # El tablero mide 40mm/casilla pero se declara 50mm/casilla
        with pytest.raises(InvalidBoardGeometryError):
            validate_board_geometry(square_corners, expected_square_size_mm=50.0)

    def test_diagonal_check_catches_non_rectangular_board(self):
        # Lados correctos pero board "trapezoide" (esquina h8 desplazada
        # en diagonal): los lados podrían pasar, la diagonal no.
        skewed = BoardCornersArm(
            a1=ArmPoint(0.0, 0.0, 10.0),
            a8=ArmPoint(0.0, 280.0, 10.0),
            h1=ArmPoint(280.0, 0.0, 10.0),
            h8=ArmPoint(280.0 + 30, 280.0 + 30, 10.0),
        )
        with pytest.raises(InvalidBoardGeometryError):
            validate_board_geometry(skewed, expected_square_size_mm=SQUARE_SIZE_MM)

    def test_invalid_square_size_raises_value_error(self, square_corners):
        with pytest.raises(ValueError):
            validate_board_geometry(square_corners, expected_square_size_mm=0)

    def test_negative_tolerance_raises_value_error(self, square_corners):
        with pytest.raises(ValueError):
            validate_board_geometry(
                square_corners, expected_square_size_mm=SQUARE_SIZE_MM, tolerance_mm=-1
            )

    def test_error_carries_measured_and_expected_details(self, square_corners):
        distorted = BoardCornersArm(
            a1=square_corners.a1,
            a8=square_corners.a8,
            h1=ArmPoint(320.0, 0.0, 10.0),
            h8=square_corners.h8,
        )
        with pytest.raises(InvalidBoardGeometryError) as exc_info:
            validate_board_geometry(distorted, expected_square_size_mm=SQUARE_SIZE_MM)
        assert "a1_h1" in exc_info.value.measured
        assert "a1_h1" in exc_info.value.expected
