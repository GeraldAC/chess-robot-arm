from pathlib import Path

import pytest
import yaml

from chess_calibration.calibration_io import (
    build_calibration_map,
    load_calibration_input,
    load_calibration_session,
    save_calibration_session,
)
from chess_calibration.calibration_types import (
    ArmPoint,
    BoardCornersArm,
    CalibrationSessionNotFoundError,
    IncompleteCalibrationInputError,
    InvalidBoardGeometryError,
)
from chess_planner.movement_types import Zone

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURES_DIR / "sample_calibration.yaml"
SQUARE_SIZE_MM = 40.0


class TestLoadCalibrationInput:
    def test_loads_valid_fixture(self):
        corners, zones = load_calibration_input(str(SAMPLE_YAML))

        assert isinstance(corners, BoardCornersArm)
        assert corners.a1 == ArmPoint(0.0, 0.0, 10.0)
        assert corners.h8 == ArmPoint(280.0, 280.0, 10.0)

        assert set(zones.keys()) == set(Zone)
        assert zones[Zone.DISCARD_WHITE] == ArmPoint(330.0, -50.0, 40.0)
        assert zones[Zone.SPARE_BLACK] == ArmPoint(-50.0, -50.0, 40.0)
        assert zones[Zone.SPARE_WHITE] == ArmPoint(330.0, 330.0, 40.0)
        assert zones[Zone.DISCARD_BLACK] == ArmPoint(-50.0, 330.0, 40.0)

    def test_missing_file_raises(self):
        with pytest.raises(IncompleteCalibrationInputError):
            load_calibration_input(str(FIXTURES_DIR / "no_existe.yaml"))

    def test_missing_corner_raises(self, tmp_path):
        data = yaml.safe_load(SAMPLE_YAML.read_text())
        del data["square_corners"]["h8"]
        broken = tmp_path / "broken.yaml"
        broken.write_text(yaml.safe_dump(data))

        with pytest.raises(IncompleteCalibrationInputError, match="h8"):
            load_calibration_input(str(broken))

    def test_missing_zone_raises(self, tmp_path):
        data = yaml.safe_load(SAMPLE_YAML.read_text())
        del data["zones"]["SPARE_BLACK"]
        broken = tmp_path / "broken.yaml"
        broken.write_text(yaml.safe_dump(data))

        with pytest.raises(IncompleteCalibrationInputError, match="SPARE_BLACK"):
            load_calibration_input(str(broken))

    def test_malformed_point_raises(self, tmp_path):
        data = yaml.safe_load(SAMPLE_YAML.read_text())
        data["square_corners"]["a1"] = {"x_mm": 0.0, "y_mm": 0.0}  # falta z_mm
        broken = tmp_path / "broken.yaml"
        broken.write_text(yaml.safe_dump(data))

        with pytest.raises(IncompleteCalibrationInputError):
            load_calibration_input(str(broken))

    def test_invalid_yaml_raises(self, tmp_path):
        broken = tmp_path / "broken.yaml"
        broken.write_text("square_corners: [this is not: a valid: mapping")

        with pytest.raises(IncompleteCalibrationInputError):
            load_calibration_input(str(broken))


class TestBuildCalibrationMap:
    def test_success_produces_68_entries(self):
        corners, zones = load_calibration_input(str(SAMPLE_YAML))
        calibration_map = build_calibration_map(corners, zones, SQUARE_SIZE_MM)

        assert len(calibration_map) == 68
        for zone in Zone:
            assert zone.value in calibration_map
        assert calibration_map["a1"] == corners.a1
        assert calibration_map[Zone.DISCARD_WHITE.value] == zones[Zone.DISCARD_WHITE]

    def test_invalid_geometry_propagates(self):
        corners, zones = load_calibration_input(str(SAMPLE_YAML))
        with pytest.raises(InvalidBoardGeometryError):
            build_calibration_map(corners, zones, expected_square_size_mm=100.0)


class TestCalibrationSessionRoundtrip:
    def test_save_then_load_roundtrip(self, tmp_path):
        corners, zones = load_calibration_input(str(SAMPLE_YAML))
        calibration_map = build_calibration_map(corners, zones, SQUARE_SIZE_MM)

        session_path = tmp_path / "session.json"
        save_calibration_session(calibration_map, str(session_path))
        loaded = load_calibration_session(str(session_path))

        assert loaded == calibration_map

    def test_load_missing_session_raises(self, tmp_path):
        with pytest.raises(CalibrationSessionNotFoundError):
            load_calibration_session(str(tmp_path / "no_existe.json"))

    def test_load_incomplete_session_raises(self, tmp_path):
        session_path = tmp_path / "incomplete.json"
        session_path.write_text('{"a1": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0}}')

        with pytest.raises(CalibrationSessionNotFoundError):
            load_calibration_session(str(session_path))

    def test_load_corrupt_json_raises(self, tmp_path):
        session_path = tmp_path / "corrupt.json"
        session_path.write_text("{not valid json")

        with pytest.raises(CalibrationSessionNotFoundError):
            load_calibration_session(str(session_path))
