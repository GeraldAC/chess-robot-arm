"""CLI de producto de chess_actuators (M8).

Ver M8_SPEC.md §5.5 para la tabla de argumentos. Sin --trajectory, se
conecta (PING/PONG), reporta el resultado y queda disponible en modo
diagnóstico (--test-pulse) para el protocolo de calibración manual de
servos (M8_SPEC.md §6).
"""

from __future__ import annotations

import argparse
import json
import sys

from chess_actuators.actuator_calibration import load_actuator_calibration
from chess_actuators.actuator_driver import (
    ActuatorDriver,
    SerialActuatorDriver,
    SimulatedActuatorDriver,
)
from chess_actuators.actuator_executor import execute_trajectory
from chess_actuators.actuator_protocol import format_set
from chess_actuators.actuator_types import (
    ActuatorCalibrationNotFoundError,
    ActuatorConfig,
    ActuatorConnectionError,
    TrajectoryExecutionError,
)
from chess_kinematics import ArmWaypoint, GripperAction, JointAngles, WaypointKind


def load_trajectory_json(path: str) -> list[ArmWaypoint]:
    """Carga una ArmTrajectory serializada como JSON para pruebas
    end-to-end sin depender de chess_kinematics en tiempo de
    ejecución del CLI. Formato esperado: lista de objetos con
    location, joint_angles (q1_deg..q5_deg), gripper, kind."""
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    trajectory: list[ArmWaypoint] = []
    for item in raw:
        angles = item["joint_angles"]
        trajectory.append(
            ArmWaypoint(
                location=item["location"],
                joint_angles=JointAngles(
                    q1_deg=float(angles["q1_deg"]),
                    q2_deg=float(angles["q2_deg"]),
                    q3_deg=float(angles["q3_deg"]),
                    q4_deg=float(angles["q4_deg"]),
                    q5_deg=float(angles["q5_deg"]),
                ),
                gripper=GripperAction(item["gripper"]),
                kind=WaypointKind(item["kind"]),
            )
        )
    return trajectory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chess-actuators",
        description="Control de actuadores (M8): ejecuta una ArmTrajectory sobre el brazo físico o simulado.",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Puerto Serial (p. ej. COM3). No requerido con --simulate.",
    )
    parser.add_argument(
        "--calibration",
        default=None,
        help="Ruta al YAML de ActuatorCalibration (M8_SPEC.md §6).",
    )
    parser.add_argument(
        "--trajectory",
        default=None,
        help="Ruta a una ArmTrajectory serializada en JSON, para ejecutar end-to-end.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Usa SimulatedActuatorDriver en vez de hardware real.",
    )
    parser.add_argument(
        "--test-pulse",
        nargs=2,
        metavar=("CANAL", "PULSO_US"),
        default=None,
        help="Modo diagnóstico: envía un único canal a un pulso dado, para el protocolo de calibración manual.",
    )
    parser.add_argument("--baudrate", type=int, default=115200)
    return parser


def build_driver(args: argparse.Namespace, config: ActuatorConfig) -> ActuatorDriver:
    if args.simulate:
        return SimulatedActuatorDriver()
    if not args.port:
        raise SystemExit("--port es requerido salvo que se use --simulate")
    return SerialActuatorDriver(config)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.calibration:
        print("Error: --calibration es requerido", file=sys.stderr)
        return 1

    try:
        calibration = load_actuator_calibration(args.calibration)
    except ActuatorCalibrationNotFoundError as exc:
        print(f"Error de calibración: {exc}", file=sys.stderr)
        return 1

    config = ActuatorConfig(serial_port=args.port or "", baudrate=args.baudrate)

    try:
        driver = build_driver(args, config)
        driver.connect()
    except ActuatorConnectionError as exc:
        print(f"Error de conexión: {exc}", file=sys.stderr)
        return 1

    try:
        if args.test_pulse is not None:
            channel_str, pulse_str = args.test_pulse
            pulses = {int(channel_str): int(pulse_str)}
            driver.send_set(pulses)
            print(f"Enviado: {format_set(pulses).strip()}")
            return 0

        if args.trajectory is not None:
            trajectory = load_trajectory_json(args.trajectory)
            try:
                report = execute_trajectory(trajectory, driver, calibration, config)
            except TrajectoryExecutionError as exc:
                print(
                    f"Trayectoria abortada en el waypoint #{exc.partial_report.failed_at_index}",
                    file=sys.stderr,
                )
                return 1
            print(
                f"Ejecución exitosa: {len(report.waypoint_results)} waypoints, status={report.trajectory_status.value}"
            )
            return 0

        print(
            "Conexión establecida (PING/PONG exitoso). Nada más que hacer sin --trajectory ni --test-pulse."
        )
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
