"""Ejecución de trayectorias: ArmTrajectory (M7) -> ExecutionReport.

Ver M8_SPEC.md §2.2 (por qué no hay interpolación fina, solo
temporización a nivel de waypoint), §2.3 (reintentos + congelar en
sitio) y §5.4 (diseño).

Nota de diseño: connect()/close() del driver son responsabilidad del
llamador (p. ej. actuator_main.py o el futuro Orquestador M10), NO de
execute_trajectory. Mantener la conexión abierta entre jugadas evita
reconexiones innecesarias, relevante porque el Arduino UNO se resetea
al reabrir el puerto Serial (ver M8_SPEC.md §3, advertencia de
hardware).
"""

from __future__ import annotations

import time

from chess_actuators.actuator_calibration import gripper_pulse, pulses_from_joint_angles
from chess_actuators.actuator_driver import ActuatorDriver
from chess_actuators.actuator_types import (
    ActuatorCalibration,
    ActuatorConfig,
    ActuatorConnectionError,
    ExecutionReport,
    ExecutionStatus,
    TrajectoryExecutionError,
    WaypointExecutionResult,
)
from chess_kinematics import ArmWaypoint, GripperAction, JointAngles

# Estado inicial asumido del gripper al comenzar una sesión: no hay
# forma de conocerlo sin feedback físico (ver M8_SPEC.md §1), así que se
# asume abierto. Si el supuesto es incorrecto, el primer waypoint con
# gripper=HOLD simplemente reenviará el pulso "open" asumido -- no hay
# riesgo de soltar una pieza que en realidad no se estaba sosteniendo.
_ASSUMED_INITIAL_GRIPPER_STATE = GripperAction.OPEN


def compute_settle_time_s(
    previous: JointAngles | None,
    target: JointAngles,
    gripper_changed: bool,
    config: ActuatorConfig,
) -> float:
    """Tiempo de espera antes de considerar alcanzado el waypoint.

    Si `previous` es None (primer waypoint de la sesión, posición real
    del brazo desconocida), retorna config.first_move_settle_s. En caso
    contrario, retorna el mayor delta angular entre articulaciones
    dividido por config.max_joint_speed_deg_s, sumando
    config.gripper_settle_s si gripper_changed.
    """
    if previous is None:
        return config.first_move_settle_s

    deltas = (
        abs(target.q1_deg - previous.q1_deg),
        abs(target.q2_deg - previous.q2_deg),
        abs(target.q3_deg - previous.q3_deg),
        abs(target.q4_deg - previous.q4_deg),
        abs(target.q5_deg - previous.q5_deg),
    )
    settle = max(deltas) / config.max_joint_speed_deg_s
    if gripper_changed:
        settle += config.gripper_settle_s
    return settle


def execute_waypoint(
    waypoint: ArmWaypoint,
    driver: ActuatorDriver,
    calibration: ActuatorCalibration,
    config: ActuatorConfig,
    previous_angles: JointAngles | None,
    current_gripper_pulse_us: int,
) -> tuple[WaypointExecutionResult, JointAngles, int]:
    """Ejecuta un único ArmWaypoint: lo convierte a pulsos, lo envía con
    reintentos acotados y, si tiene éxito, espera el tiempo de settle
    calculado.

    Retorna (resultado, nuevo_estado_angulos, nuevo_pulso_gripper) para
    encadenar el siguiente waypoint. En caso de fallo tras agotar los
    reintentos, retorna un resultado con status=FAILED y el estado sin
    cambios (el brazo queda congelado en la última posición confirmada).
    """
    joint_pulses = pulses_from_joint_angles(waypoint.joint_angles, calibration)
    gripper_changed = waypoint.gripper != GripperAction.HOLD
    new_gripper_pulse = gripper_pulse(
        waypoint.gripper, calibration.gripper, current_gripper_pulse_us
    )

    pulses = dict(joint_pulses)
    pulses[calibration.gripper.channel] = new_gripper_pulse

    last_error: Exception | None = None
    for attempt in range(1, config.max_retries + 1):
        try:
            driver.send_set(pulses)
        except (ActuatorConnectionError, ValueError) as exc:
            last_error = exc
            if attempt < config.max_retries:
                time.sleep(config.retry_backoff_s)
            continue
        else:
            settle_s = compute_settle_time_s(
                previous_angles, waypoint.joint_angles, gripper_changed, config
            )
            time.sleep(settle_s)
            result = WaypointExecutionResult(
                location=waypoint.location,
                kind=waypoint.kind,
                attempts=attempt,
                status=ExecutionStatus.SUCCESS,
            )
            return result, waypoint.joint_angles, new_gripper_pulse

    result = WaypointExecutionResult(
        location=waypoint.location,
        kind=waypoint.kind,
        attempts=config.max_retries,
        status=ExecutionStatus.FAILED,
    )
    # El brazo queda congelado: no se propaga el nuevo estado (ni
    # ángulos ni pulso de gripper), reflejando que el comando NUNCA fue
    # confirmado por el microcontrolador -- ver M8_SPEC.md §2.3.
    del last_error  # ya reflejado en el status del resultado
    return result, previous_angles, current_gripper_pulse_us


def execute_trajectory(
    trajectory: list[ArmWaypoint],
    driver: ActuatorDriver,
    calibration: ActuatorCalibration,
    config: ActuatorConfig,
) -> ExecutionReport:
    """Punto de entrada único de chess_actuators para el ciclo de
    partida. Ejecuta cada ArmWaypoint en orden.

    Si un waypoint agota sus reintentos, aborta de inmediato (no
    ejecuta los waypoints restantes) y lanza TrajectoryExecutionError
    con el ExecutionReport parcial -- señal de flujo explícita para el
    Orquestador (M10), mismo patrón que UnreachableLocationError (M7).
    """
    results: list[WaypointExecutionResult] = []
    previous_angles: JointAngles | None = None
    current_gripper_pulse_us = round(
        calibration.gripper.pulse_open_us
    )  # ver _ASSUMED_INITIAL_GRIPPER_STATE

    for index, waypoint in enumerate(trajectory):
        result, previous_angles, current_gripper_pulse_us = execute_waypoint(
            waypoint,
            driver,
            calibration,
            config,
            previous_angles,
            current_gripper_pulse_us,
        )
        results.append(result)

        if result.status == ExecutionStatus.FAILED:
            partial_report = ExecutionReport(
                trajectory_status=ExecutionStatus.FAILED,
                waypoint_results=results,
                failed_at_index=index,
            )
            raise TrajectoryExecutionError(partial_report)

    return ExecutionReport(
        trajectory_status=ExecutionStatus.SUCCESS,
        waypoint_results=results,
        failed_at_index=None,
    )
