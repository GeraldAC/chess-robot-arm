"""Contratos internos de chess_actuators (M8).

Ver M8_SPEC.md §4 para el detalle de cada tipo y §2.4 para por qué la
calibración de servos es un tercer nivel de calibración, distinto de
CalibrationMap (M0) y JointMap (M7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from chess_kinematics import WaypointKind

# --------------------------------------------------------------------------
# Calibración física de servos (§2.4, §4.1, §6)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ServoChannelCalibration:
    """Calibración física de un canal servo del PCA9685.

    angle_min_deg / angle_max_deg están en la convención DH de M7 (los
    mismos ángulos que produce chess_kinematics.JointAngles), no en la
    convención de datasheet del servo.
    """

    channel: int
    pulse_min_us: float
    pulse_max_us: float
    angle_min_deg: float
    angle_max_deg: float
    reversed: bool = False

    def __post_init__(self) -> None:
        if not (0 <= self.channel <= 15):
            raise ValueError(
                f"channel debe estar en [0, 15] (PCA9685 tiene 16 canales), recibido: {self.channel}"
            )
        if self.pulse_min_us >= self.pulse_max_us:
            raise ValueError("pulse_min_us debe ser < pulse_max_us")
        if self.angle_min_deg >= self.angle_max_deg:
            raise ValueError("angle_min_deg debe ser < angle_max_deg")


@dataclass(frozen=True)
class GripperCalibration:
    """La pinza no recibe un ángulo: solo dos estados discretos,
    resueltos por GripperAction (ver actuator_calibration.gripper_pulse)."""

    channel: int
    pulse_open_us: float
    pulse_closed_us: float

    def __post_init__(self) -> None:
        if not (0 <= self.channel <= 15):
            raise ValueError(
                f"channel debe estar en [0, 15] (PCA9685 tiene 16 canales), recibido: {self.channel}"
            )


# Claves requeridas en ActuatorCalibration.joints — deben coincidir con
# los atributos "qN_deg" de chess_kinematics.JointAngles.
REQUIRED_JOINT_KEYS: tuple[str, ...] = ("q1", "q2", "q3", "q4", "q5")


@dataclass(frozen=True)
class ActuatorCalibration:
    """Calibración física completa de los 6 servos del brazo.

    Propiedad del hardware, NO de la sesión de juego (a diferencia de
    CalibrationMap/JointMap) — ver M8_SPEC.md §2.4. Se persiste como
    archivo de configuración de proyecto, no de sesión.
    """

    joints: dict[str, ServoChannelCalibration]
    gripper: GripperCalibration
    pwm_frequency_hz: float = 50.0

    def __post_init__(self) -> None:
        missing = [k for k in REQUIRED_JOINT_KEYS if k not in self.joints]
        if missing:
            raise ActuatorCalibrationNotFoundError(
                f"Faltan canales de articulación en la calibración: {missing}"
            )
        channels_used = [c.channel for c in self.joints.values()] + [
            self.gripper.channel
        ]
        if len(channels_used) != len(set(channels_used)):
            raise ValueError(
                f"Canales PCA9685 duplicados en la calibración: {channels_used}"
            )


# --------------------------------------------------------------------------
# Configuración de ejecución (§4.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ActuatorConfig:
    """Parámetros de ejecución. Los valores marcados PLACEHOLDER son
    conservadores y no han sido validados contra hardware real — ver
    M8_SPEC.md §9."""

    serial_port: str
    baudrate: int = 115200
    ack_timeout_s: float = 0.5
    max_retries: int = 3
    retry_backoff_s: float = 0.1
    max_joint_speed_deg_s: float = 60.0  # PLACEHOLDER — ver M8_SPEC.md §9
    gripper_settle_s: float = 0.4  # PLACEHOLDER — ver M8_SPEC.md §9
    first_move_settle_s: float = 2.0

    def __post_init__(self) -> None:
        if self.max_retries < 1:
            raise ValueError("max_retries debe ser >= 1")
        if self.max_joint_speed_deg_s <= 0:
            raise ValueError("max_joint_speed_deg_s debe ser > 0")


# --------------------------------------------------------------------------
# Reporte de ejecución — contrato de salida M8 -> M9 (§4.1)
# --------------------------------------------------------------------------


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class WaypointExecutionResult:
    location: str
    kind: WaypointKind
    attempts: int
    status: ExecutionStatus


@dataclass(frozen=True)
class ExecutionReport:
    """Contrato de salida M8 -> M9.

    NO es una verificación del estado físico real (ver M8_SPEC.md §1):
    solo resume qué comandos se enviaron y confirmó el microcontrolador.
    La verificación física real es responsabilidad de M9.
    """

    trajectory_status: ExecutionStatus
    waypoint_results: list[WaypointExecutionResult] = field(default_factory=list)
    failed_at_index: int | None = None


# --------------------------------------------------------------------------
# Errores (§4.2)
# --------------------------------------------------------------------------


class ActuatorError(Exception):
    """Clase base de errores de contrato de chess_actuators."""


class ActuatorConnectionError(ActuatorError):
    """No se pudo abrir/mantener la conexión Serial (puerto no
    encontrado, o PING inicial sin PONG dentro de ack_timeout_s)."""


class ActuatorCalibrationNotFoundError(ActuatorError):
    """No existe un archivo de ActuatorCalibration válido, o le faltan
    canales requeridos (q1..q5 o gripper). Análogo a
    CalibrationSessionNotFoundError (M0) / JointMapSessionNotFoundError (M7)."""


class ServoAngleOutOfRangeError(ActuatorError):
    """Un JointAngles cae fuera de [angle_min_deg, angle_max_deg] de su
    ServoChannelCalibration. Se lanza ANTES de enviar el comando —
    defensa en profundidad adicional a la ya provista por M7."""


class TrajectoryExecutionError(ActuatorError):
    """Se agotaron los reintentos en un ArmWaypoint durante
    execute_trajectory. El Orquestador debe tratar esto como señal de
    flujo explícita (requiere intervención humana), mismo patrón que
    UnreachableLocationError (M7). Contiene el ExecutionReport parcial
    para que M10 pueda inspeccionar qué se alcanzó a ejecutar."""

    def __init__(self, partial_report: ExecutionReport) -> None:
        self.partial_report = partial_report
        super().__init__(
            f"Trayectoria abortada en el waypoint de índice {partial_report.failed_at_index}"
        )
