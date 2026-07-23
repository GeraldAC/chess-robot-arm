import os

import pytest

from chess_actuators.actuator_calibration import (
    gripper_pulse,
    load_actuator_calibration,
    pulses_from_joint_angles,
    save_actuator_calibration,
)
from chess_actuators.actuator_types import (
    ActuatorCalibrationNotFoundError,
    ServoAngleOutOfRangeError,
)
from chess_kinematics import GripperAction, JointAngles
from test_actuators.fixtures.sample_trajectory import build_sample_calibration

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_calibration.yaml"
)


def test_pulses_from_joint_angles_within_range():
    calibration = build_sample_calibration()
    angles = JointAngles(
        q1_deg=0.0, q2_deg=90.0, q3_deg=-90.0, q4_deg=45.0, q5_deg=-45.0
    )

    pulses = pulses_from_joint_angles(angles, calibration)

    # q1: 0° -> punto medio del rango [-90, 90] -> pulso medio
    assert pulses[0] == pytest.approx(1500, abs=1)
    # q2: 90° -> extremo superior -> pulso máximo
    assert pulses[1] == pytest.approx(2500, abs=1)
    # q4: 45° -> 3/4 del rango -> pulso 3/4
    assert pulses[3] == pytest.approx(2000, abs=1)


def test_pulses_from_joint_angles_reversed_channel():
    calibration = build_sample_calibration()  # q3 está marcado reversed=True
    angles = JointAngles(q1_deg=0.0, q2_deg=0.0, q3_deg=90.0, q4_deg=0.0, q5_deg=0.0)

    pulses = pulses_from_joint_angles(angles, calibration)

    # Sin inversión, 90° (extremo superior) mapearía a pulse_max_us (2500).
    # Con reversed=True, el extremo superior debe mapear a pulse_min_us (500).
    assert pulses[2] == pytest.approx(500, abs=1)


def test_pulses_from_joint_angles_out_of_range():
    calibration = build_sample_calibration()
    angles = JointAngles(q1_deg=0.0, q2_deg=999.0, q3_deg=0.0, q4_deg=0.0, q5_deg=0.0)

    with pytest.raises(ServoAngleOutOfRangeError):
        pulses_from_joint_angles(angles, calibration)


def test_gripper_pulse_open_close_hold():
    calibration = build_sample_calibration()
    current = 1234

    assert gripper_pulse(GripperAction.OPEN, calibration.gripper, current) == 1500
    assert gripper_pulse(GripperAction.CLOSE, calibration.gripper, current) == 900
    assert gripper_pulse(GripperAction.HOLD, calibration.gripper, current) == current


def test_load_actuator_calibration_valid_yaml():
    calibration = load_actuator_calibration(FIXTURE_PATH)

    assert set(calibration.joints) == {"q1", "q2", "q3", "q4", "q5"}
    assert calibration.gripper.channel == 5
    assert calibration.joints["q3"].reversed is True
    assert calibration.pwm_frequency_hz == 50.0


def test_load_actuator_calibration_missing_file():
    with pytest.raises(ActuatorCalibrationNotFoundError):
        load_actuator_calibration("/no/existe/archivo.yaml")


def test_load_actuator_calibration_missing_joint(tmp_path):
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text("""
joints:
  q1: { channel: 0, pulse_min_us: 500, pulse_max_us: 2500, angle_min_deg: -90.0, angle_max_deg: 90.0 }
gripper:
  channel: 5
  pulse_open_us: 1500
  pulse_closed_us: 900
""")
    with pytest.raises(ActuatorCalibrationNotFoundError):
        load_actuator_calibration(str(incomplete))


def test_save_and_load_round_trip(tmp_path):
    original = build_sample_calibration()
    path = str(tmp_path / "roundtrip.yaml")

    save_actuator_calibration(original, path)
    loaded = load_actuator_calibration(path)

    assert loaded == original
