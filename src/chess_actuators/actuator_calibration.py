"""Calibración física de servos: carga/persistencia y conversión
ángulo (convención DH de M7) <-> pulso PWM (µs) por canal físico.

Ver M8_SPEC.md §2.4 (por qué existe este tercer nivel de calibración),
§5.1 (diseño) y §6 (formato del archivo YAML).
"""

from __future__ import annotations

import yaml

from chess_actuators.actuator_types import (
    REQUIRED_JOINT_KEYS,
    ActuatorCalibration,
    ActuatorCalibrationNotFoundError,
    GripperCalibration,
    ServoAngleOutOfRangeError,
    ServoChannelCalibration,
)
from chess_kinematics import GripperAction, JointAngles


def load_actuator_calibration(path: str) -> ActuatorCalibration:
    """Carga la calibración de servos desde YAML (formato M8_SPEC.md §6).

    Lanza ActuatorCalibrationNotFoundError si el archivo no existe, no es
    YAML válido, o le faltan canales requeridos (q1..q5 o gripper).
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ActuatorCalibrationNotFoundError(
            f"No existe el archivo de calibración: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ActuatorCalibrationNotFoundError(
            f"YAML inválido en {path}: {exc}"
        ) from exc

    if not raw or "joints" not in raw or "gripper" not in raw:
        raise ActuatorCalibrationNotFoundError(
            f"{path} no tiene la forma esperada (faltan 'joints' o 'gripper')"
        )

    missing = [k for k in REQUIRED_JOINT_KEYS if k not in raw["joints"]]
    if missing:
        raise ActuatorCalibrationNotFoundError(
            f"Faltan canales de articulación en {path}: {missing}"
        )

    try:
        joints = {
            key: ServoChannelCalibration(
                channel=int(value["channel"]),
                pulse_min_us=float(value["pulse_min_us"]),
                pulse_max_us=float(value["pulse_max_us"]),
                angle_min_deg=float(value["angle_min_deg"]),
                angle_max_deg=float(value["angle_max_deg"]),
                reversed=bool(value.get("reversed", False)),
            )
            for key, value in raw["joints"].items()
        }
        gripper_raw = raw["gripper"]
        gripper = GripperCalibration(
            channel=int(gripper_raw["channel"]),
            pulse_open_us=float(gripper_raw["pulse_open_us"]),
            pulse_closed_us=float(gripper_raw["pulse_closed_us"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ActuatorCalibrationNotFoundError(
            f"Campo faltante o malformado en {path}: {exc}"
        ) from exc

    pwm_frequency_hz = float(raw.get("pwm_frequency_hz", 50.0))

    return ActuatorCalibration(
        joints=joints, gripper=gripper, pwm_frequency_hz=pwm_frequency_hz
    )


def save_actuator_calibration(calibration: ActuatorCalibration, path: str) -> None:
    """Persiste la calibración a YAML.

    A diferencia de save_calibration_session (M0) / save_joint_map_session
    (M7), esto NO es un archivo de sesión: se re-guarda solo cuando
    cambia el hardware físico (servo reemplazado/remontado), no una vez
    por partida — ver M8_SPEC.md §2.4.
    """
    raw = {
        "joints": {
            key: {
                "channel": servo.channel,
                "pulse_min_us": servo.pulse_min_us,
                "pulse_max_us": servo.pulse_max_us,
                "angle_min_deg": servo.angle_min_deg,
                "angle_max_deg": servo.angle_max_deg,
                "reversed": servo.reversed,
            }
            for key, servo in calibration.joints.items()
        },
        "gripper": {
            "channel": calibration.gripper.channel,
            "pulse_open_us": calibration.gripper.pulse_open_us,
            "pulse_closed_us": calibration.gripper.pulse_closed_us,
        },
        "pwm_frequency_hz": calibration.pwm_frequency_hz,
    }
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(raw, handle, sort_keys=False)


def pulses_from_joint_angles(
    joint_angles: JointAngles, calibration: ActuatorCalibration
) -> dict[int, int]:
    """Convierte JointAngles (grados, convención DH de M7) a pulsos PWM
    (µs) por canal físico: interpolación lineal dentro de
    [angle_min_deg, angle_max_deg] -> [pulse_min_us, pulse_max_us] de
    cada ServoChannelCalibration, invirtiendo el sentido si reversed=True.

    Lanza ServoAngleOutOfRangeError si algún ángulo cae fuera del rango
    calibrado de su canal (defensa en profundidad adicional a la de M7).
    """
    pulses: dict[int, int] = {}
    for key in REQUIRED_JOINT_KEYS:
        servo = calibration.joints[key]
        angle_deg = getattr(joint_angles, f"{key}_deg")

        if not (servo.angle_min_deg <= angle_deg <= servo.angle_max_deg):
            raise ServoAngleOutOfRangeError(
                f"{key}: {angle_deg}° fuera del rango calibrado "
                f"[{servo.angle_min_deg}°, {servo.angle_max_deg}°] del canal {servo.channel}"
            )

        span_deg = servo.angle_max_deg - servo.angle_min_deg
        fraction = (angle_deg - servo.angle_min_deg) / span_deg
        if servo.reversed:
            fraction = 1.0 - fraction

        pulse_us = servo.pulse_min_us + fraction * (
            servo.pulse_max_us - servo.pulse_min_us
        )
        pulses[servo.channel] = round(pulse_us)

    return pulses


def gripper_pulse(
    action: GripperAction, calibration: GripperCalibration, current_pulse_us: int
) -> int:
    """OPEN -> pulse_open_us, CLOSE -> pulse_closed_us, HOLD -> sin cambio."""
    if action == GripperAction.OPEN:
        return round(calibration.pulse_open_us)
    if action == GripperAction.CLOSE:
        return round(calibration.pulse_closed_us)
    return current_pulse_us
