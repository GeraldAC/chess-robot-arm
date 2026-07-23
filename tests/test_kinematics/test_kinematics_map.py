import pytest

from chess_calibration.calibration_types import ArmPoint
from chess_kinematics import kinematics_map
from chess_kinematics.kinematics_map import (
    build_joint_map,
    load_joint_map_session,
    save_joint_map_session,
    solve_location,
)
from chess_kinematics.kinematics_types import (
    DEConfig,
    JointAngles,
    JointMapSessionNotFoundError,
    LocationSolution,
    UnreachableLocationError,
)


def test_solve_location_converges_vertical_strict():
    point = ArmPoint(x_mm=200.0, y_mm=0.0, z_mm=100.0)
    de_config = DEConfig(NP=60, G_max=300, tol=1e-4, seed=42)

    solution = solve_location(
        "e4", point, safe_travel_height_mm=50.0, de_config=de_config,
        position_tolerance_mm=5.0, tilt_steps_deg=(0.0, 10.0, 20.0),
    )

    assert solution.orientation_relaxed is False


def test_solve_location_requires_tilt(monkeypatch):
    """Simula (vía monkeypatch) que la vertical estricta no converge pero
    una inclinación sí — para probar la lógica de reintento en sí misma,
    independiente del comportamiento numérico real de DE."""

    call_log = []

    def fake_solve_ik(point, tilt_deg, de_config):
        call_log.append(tilt_deg)
        if tilt_deg == 0.0:
            return JointAngles(0, 0, 0, 0, 0), 999.0  # no converge
        return JointAngles(1, 2, 3, 4, 5), 0.5  # converge con inclinación

    monkeypatch.setattr(kinematics_map, "solve_ik", fake_solve_ik)

    point = ArmPoint(x_mm=200.0, y_mm=0.0, z_mm=100.0)
    solution = solve_location(
        "h1", point, safe_travel_height_mm=50.0,
        position_tolerance_mm=2.0, tilt_steps_deg=(0.0, 10.0, 20.0),
    )

    assert solution.orientation_relaxed is True
    assert 0.0 in call_log and 10.0 in call_log


def test_solve_location_unreachable_raises(monkeypatch):
    def fake_solve_ik(point, tilt_deg, de_config):
        return JointAngles(0, 0, 0, 0, 0), 999.0  # nunca converge

    monkeypatch.setattr(kinematics_map, "solve_ik", fake_solve_ik)

    point = ArmPoint(x_mm=1000.0, y_mm=0.0, z_mm=100.0)
    with pytest.raises(UnreachableLocationError):
        solve_location(
            "a1", point, safe_travel_height_mm=50.0,
            position_tolerance_mm=2.0, tilt_steps_deg=(0.0, 10.0),
        )


def test_build_joint_map_produces_expected_entries():
    calibration_map = {
        "a1": ArmPoint(x_mm=150.0, y_mm=-100.0, z_mm=20.0),
        "h8": ArmPoint(x_mm=300.0, y_mm=100.0, z_mm=20.0),
    }
    de_config = DEConfig(NP=40, G_max=150, tol=1e-3, seed=1)

    joint_map = build_joint_map(
        calibration_map, safe_travel_height_mm=50.0, de_config=de_config,
        position_tolerance_mm=10.0, tilt_steps_deg=(0.0, 15.0, 30.0),
    )

    assert set(joint_map.keys()) == {"a1", "h8"}
    for solution in joint_map.values():
        assert isinstance(solution, LocationSolution)


def test_save_and_load_joint_map_round_trip(tmp_path):
    joint_map = {
        "a1": LocationSolution(
            grasp=JointAngles(1.0, 2.0, 3.0, 4.0, 5.0),
            transit=JointAngles(1.0, 2.0, 3.0, 24.0, 5.0),
            orientation_relaxed=False,
        ),
        "h8": LocationSolution(
            grasp=JointAngles(-10.0, 20.0, -30.0, 40.0, 0.0),
            transit=JointAngles(-10.0, 20.0, -30.0, 60.0, 0.0),
            orientation_relaxed=True,
        ),
    }
    path = tmp_path / "joint_session.json"
    save_joint_map_session(joint_map, str(path))

    loaded = load_joint_map_session(str(path), expected_location_count=2)

    assert loaded == joint_map


def test_load_missing_session_raises(tmp_path):
    path = tmp_path / "does_not_exist.json"
    with pytest.raises(JointMapSessionNotFoundError):
        load_joint_map_session(str(path))


def test_load_incomplete_session_raises(tmp_path):
    joint_map = {
        "a1": LocationSolution(
            grasp=JointAngles(1.0, 2.0, 3.0, 4.0, 5.0),
            transit=JointAngles(1.0, 2.0, 3.0, 24.0, 5.0),
            orientation_relaxed=False,
        ),
    }
    path = tmp_path / "incomplete_session.json"
    save_joint_map_session(joint_map, str(path))

    with pytest.raises(JointMapSessionNotFoundError):
        load_joint_map_session(str(path), expected_location_count=68)
