import pytest

from chess_actuators.actuator_types import (
    ActuatorCalibration,
    ActuatorCalibrationNotFoundError,
    ActuatorConfig,
    ExecutionReport,
    ExecutionStatus,
    GripperCalibration,
    ServoChannelCalibration,
    TrajectoryExecutionError,
    WaypointExecutionResult,
)
from chess_kinematics import WaypointKind


def _valid_servo(channel: int = 0) -> ServoChannelCalibration:
    return ServoChannelCalibration(
        channel=channel,
        pulse_min_us=500,
        pulse_max_us=2500,
        angle_min_deg=-90.0,
        angle_max_deg=90.0,
    )


def test_servo_channel_calibration_rejects_out_of_range_channel():
    with pytest.raises(ValueError):
        ServoChannelCalibration(
            channel=16,
            pulse_min_us=500,
            pulse_max_us=2500,
            angle_min_deg=-90.0,
            angle_max_deg=90.0,
        )


def test_servo_channel_calibration_rejects_inverted_pulse_bounds():
    with pytest.raises(ValueError):
        ServoChannelCalibration(
            channel=0,
            pulse_min_us=2500,
            pulse_max_us=500,
            angle_min_deg=-90.0,
            angle_max_deg=90.0,
        )


def test_servo_channel_calibration_rejects_inverted_angle_bounds():
    with pytest.raises(ValueError):
        ServoChannelCalibration(
            channel=0,
            pulse_min_us=500,
            pulse_max_us=2500,
            angle_min_deg=90.0,
            angle_max_deg=-90.0,
        )


def test_gripper_calibration_rejects_out_of_range_channel():
    with pytest.raises(ValueError):
        GripperCalibration(channel=99, pulse_open_us=1500, pulse_closed_us=900)


def test_actuator_calibration_rejects_missing_joint():
    joints = {
        key: _valid_servo(i) for i, key in enumerate(("q1", "q2", "q3", "q4"))
    }  # falta q5
    with pytest.raises(ActuatorCalibrationNotFoundError):
        ActuatorCalibration(joints=joints, gripper=GripperCalibration(5, 1500, 900))


def test_actuator_calibration_rejects_duplicate_channels():
    joints = {
        key: _valid_servo(0) for key in ("q1", "q2", "q3", "q4", "q5")
    }  # todos en canal 0
    with pytest.raises(ValueError):
        ActuatorCalibration(joints=joints, gripper=GripperCalibration(5, 1500, 900))


def test_actuator_config_rejects_zero_retries():
    with pytest.raises(ValueError):
        ActuatorConfig(serial_port="COM3", max_retries=0)


def test_actuator_config_rejects_non_positive_speed():
    with pytest.raises(ValueError):
        ActuatorConfig(serial_port="COM3", max_joint_speed_deg_s=0.0)


def test_trajectory_execution_error_carries_partial_report():
    partial_report = ExecutionReport(
        trajectory_status=ExecutionStatus.FAILED,
        waypoint_results=[
            WaypointExecutionResult(
                location="e2",
                kind=WaypointKind.GRASP,
                attempts=3,
                status=ExecutionStatus.FAILED,
            )
        ],
        failed_at_index=0,
    )

    error = TrajectoryExecutionError(partial_report)

    assert error.partial_report is partial_report
    assert "0" in str(error)
