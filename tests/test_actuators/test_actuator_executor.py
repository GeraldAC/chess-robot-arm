import pytest

from chess_actuators.actuator_driver import SimulatedActuatorDriver
from chess_actuators.actuator_executor import compute_settle_time_s, execute_trajectory
from chess_actuators.actuator_types import (
    ActuatorConfig,
    ExecutionStatus,
    TrajectoryExecutionError,
)
from chess_kinematics import JointAngles
from test_actuators.fixtures.sample_trajectory import (
    build_sample_calibration,
    build_sample_trajectory,
)

# Config afinado para que los tests corran rápido: velocidad angular muy
# alta y settle times mínimos, sin depender de sleeps largos reales.
FAST_CONFIG = ActuatorConfig(
    serial_port="SIMULATED",
    max_retries=3,
    retry_backoff_s=0.01,
    max_joint_speed_deg_s=100_000.0,
    gripper_settle_s=0.01,
    first_move_settle_s=0.01,
)


def test_compute_settle_time_first_waypoint_uses_first_move_settle():
    target = JointAngles(0, 0, 0, 0, 0)
    settle = compute_settle_time_s(
        None, target, gripper_changed=False, config=FAST_CONFIG
    )
    assert settle == FAST_CONFIG.first_move_settle_s


def test_compute_settle_time_proportional_to_max_delta():
    previous = JointAngles(0, 0, 0, 0, 0)
    target = JointAngles(
        q1_deg=10, q2_deg=50, q3_deg=0, q4_deg=0, q5_deg=0
    )  # mayor delta: q2 = 50°
    config = ActuatorConfig(
        serial_port="X", max_joint_speed_deg_s=100.0, gripper_settle_s=0.0
    )

    settle = compute_settle_time_s(
        previous, target, gripper_changed=False, config=config
    )

    assert settle == pytest.approx(50 / 100.0)


def test_compute_settle_time_adds_gripper_settle_when_changed():
    previous = JointAngles(0, 0, 0, 0, 0)
    target = JointAngles(0, 0, 0, 0, 0)  # sin delta angular
    config = ActuatorConfig(
        serial_port="X", max_joint_speed_deg_s=100.0, gripper_settle_s=0.4
    )

    settle = compute_settle_time_s(
        previous, target, gripper_changed=True, config=config
    )

    assert settle == pytest.approx(0.4)


def test_execute_trajectory_success_end_to_end():
    driver = SimulatedActuatorDriver()
    calibration = build_sample_calibration()
    trajectory = build_sample_trajectory()

    report = execute_trajectory(trajectory, driver, calibration, FAST_CONFIG)

    assert report.trajectory_status == ExecutionStatus.SUCCESS
    assert report.failed_at_index is None
    assert len(report.waypoint_results) == len(trajectory)
    assert all(r.attempts == 1 for r in report.waypoint_results)
    assert all(r.status == ExecutionStatus.SUCCESS for r in report.waypoint_results)
    assert len(driver.sent_commands) == len(trajectory)


def test_execute_trajectory_transient_failure_retries_and_continues():
    # Falla solo en la primera llamada (índice 0) -> el waypoint 0 debe
    # reintentar y tener éxito en el 2do intento; el resto sigue normal.
    driver = SimulatedActuatorDriver(fail_at={0})
    calibration = build_sample_calibration()
    trajectory = build_sample_trajectory()

    report = execute_trajectory(trajectory, driver, calibration, FAST_CONFIG)

    assert report.trajectory_status == ExecutionStatus.SUCCESS
    assert report.waypoint_results[0].attempts == 2
    assert all(r.status == ExecutionStatus.SUCCESS for r in report.waypoint_results)


def test_execute_trajectory_persistent_failure_aborts_immediately():
    # Falla en las llamadas 2, 3 y 4 -- las 3 correspondientes a los
    # reintentos del waypoint #2 (índice de waypoint, no de llamada:
    # waypoints 0 y 1 tienen éxito en su primer intento -> llamadas 0 y
    # 1; el waypoint 2 empieza en la llamada 2 y consume 3 reintentos).
    driver = SimulatedActuatorDriver(fail_at={2, 3, 4})
    calibration = build_sample_calibration()
    trajectory = build_sample_trajectory()

    with pytest.raises(TrajectoryExecutionError) as exc_info:
        execute_trajectory(trajectory, driver, calibration, FAST_CONFIG)

    partial_report = exc_info.value.partial_report
    assert partial_report.trajectory_status == ExecutionStatus.FAILED
    assert partial_report.failed_at_index == 2
    # Solo se registraron resultados hasta el waypoint que falló, los
    # waypoints 3, 4, 5 nunca se intentaron.
    assert len(partial_report.waypoint_results) == 3
    assert partial_report.waypoint_results[-1].status == ExecutionStatus.FAILED
    assert partial_report.waypoint_results[-1].attempts == FAST_CONFIG.max_retries
    # Los comandos exitosos (waypoints 0 y 1) sí se enviaron; los
    # posteriores al fallo, no.
    assert len(driver.sent_commands) == 2
