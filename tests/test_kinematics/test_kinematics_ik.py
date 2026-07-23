import numpy as np
import pytest

from chess_calibration.calibration_types import ArmPoint
from chess_kinematics.kinematics_ik import (
    build_target_pose,
    differential_evolution_ik,
    forward_kinematics,
    mm_to_m,
    orientation_error_roll_invariant,
    solve_ik,
)
from chess_kinematics.kinematics_types import DEConfig


def test_mm_to_m_converts_units():
    point = ArmPoint(x_mm=100.0, y_mm=200.0, z_mm=300.0)
    result = mm_to_m(point)
    assert result == pytest.approx([0.1, 0.2, 0.3])


def test_orientation_error_ignores_roll():
    """Dos poses con el mismo eje Z (aproximación) pero distinto giro
    alrededor de ese eje deben tener error ~0 (invariancia de roll)."""
    T_a = np.eye(4)
    T_a[:3, :3] = np.array(
        [[0, 1, 0], [1, 0, 0], [0, 0, -1]], dtype=float
    )  # Z apunta hacia abajo

    # Girar 90° alrededor del propio eje Z (roll puro)
    roll_90 = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    T_b = np.eye(4)
    T_b[:3, :3] = T_a[:3, :3] @ roll_90

    error = orientation_error_roll_invariant(T_a, T_b)
    assert error == pytest.approx(0.0, abs=1e-9)


def test_orientation_error_detects_real_tilt():
    T_down = np.eye(4)
    T_down[:3, :3] = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=float)

    T_horizontal = np.eye(4)
    T_horizontal[:3, :3] = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], dtype=float)

    error = orientation_error_roll_invariant(T_down, T_horizontal)
    assert error == pytest.approx(np.pi / 2, abs=1e-6)


def test_build_target_pose_position_matches_point():
    point = ArmPoint(x_mm=150.0, y_mm=-80.0, z_mm=40.0)
    T_des = build_target_pose(point, tilt_deg=0.0)
    assert T_des[:3, 3] == pytest.approx([0.150, -0.080, 0.040])


def test_build_target_pose_zero_tilt_points_straight_down():
    point = ArmPoint(x_mm=150.0, y_mm=80.0, z_mm=40.0)
    T_des = build_target_pose(point, tilt_deg=0.0)
    z_axis = T_des[:3, 2]
    assert z_axis == pytest.approx([0.0, 0.0, -1.0], abs=1e-9)


def test_fk_ik_round_trip_known_configuration():
    """Reproduce el ejemplo del notebook: q_fk = [0, 45, -45, 0, 0]."""
    q_fk = [0.0, 45.0, -45.0, 0.0, 0.0]
    T_fk, _ = forward_kinematics(q_fk)
    p = T_fk[:3, 3] * 1000.0  # a mm

    target_point = ArmPoint(x_mm=p[0], y_mm=p[1], z_mm=p[2])

    de_config = DEConfig(NP=60, G_max=300, tol=1e-4, seed=42)
    joint_angles, position_error_mm = solve_ik(target_point, tilt_deg=0.0, de_config=de_config)

    assert position_error_mm < 5.0  # mm, tolerancia razonable con presupuesto de DE reducido


def test_solve_ik_unreachable_point_has_large_error():
    """Punto muy fuera del alcance (~1 m, contra ~355 mm de BOM.md)."""
    far_point = ArmPoint(x_mm=1000.0, y_mm=0.0, z_mm=200.0)
    de_config = DEConfig(NP=30, G_max=100, tol=1e-4, seed=1)

    _joint_angles, position_error_mm = solve_ik(far_point, tilt_deg=0.0, de_config=de_config)

    assert position_error_mm > 50.0


def test_differential_evolution_ik_is_deterministic_with_seed():
    """Misma semilla -> mismo resultado (requisito de M7_SPEC.md §2.1:
    ejecución determinística dentro de una sesión)."""
    point = ArmPoint(x_mm=200.0, y_mm=0.0, z_mm=100.0)
    T_des = build_target_pose(point, tilt_deg=0.0)
    de_config = DEConfig(NP=20, G_max=50, tol=1e-4, seed=7)

    best_1, cost_1, _ = differential_evolution_ik(T_des, de_config)
    best_2, cost_2, _ = differential_evolution_ik(T_des, de_config)

    assert best_1 == pytest.approx(best_2)
    assert cost_1 == pytest.approx(cost_2)
