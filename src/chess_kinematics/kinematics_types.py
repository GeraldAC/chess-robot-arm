"""Contratos de datos de chess_kinematics (M7).

Ver M7_SPEC.md §3 para el detalle de cada decisión de diseño.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

Location = str
# Reutiliza la misma noción que chess_calibration/chess_planner: casilla
# algebraica ("a1".."h8") o el .value de chess_planner.movement_types.Zone.


# ---------------------------------------------------------------------------
# Ángulos articulares y waypoints
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JointAngles:
    """Ángulos de las 5 articulaciones activas del ROT3U, en grados.

    Mismo orden y convención que JOINT_LIMITS_DEG en
    chess_robot_arm_dk_ik.py. NO incluye q6 (pinza): el gripper es un
    actuador independiente, desacoplado de la cinemática de posición.
    """

    q1_deg: float  # Base (yaw)
    q2_deg: float  # Hombro
    q3_deg: float  # Codo
    q4_deg: float  # Flexión de muñeca (pitch)
    q5_deg: float  # Giro de muñeca (roll) — libre para agarre simétrico

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        return (self.q1_deg, self.q2_deg, self.q3_deg, self.q4_deg, self.q5_deg)


class GripperAction(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    HOLD = "HOLD"  # sin cambio de estado (usado en waypoints de tránsito)


class WaypointKind(str, Enum):
    TRANSIT = "TRANSIT"  # altura segura, sin contacto con pieza/zona
    GRASP = "GRASP"  # altura real de la pieza/zona


@dataclass(frozen=True)
class ArmWaypoint:
    """Una única configuración articular a alcanzar, con su acción de
    pinza asociada. `location` se conserva solo para trazabilidad/log."""

    location: Location
    joint_angles: JointAngles
    gripper: GripperAction
    kind: WaypointKind


ArmTrajectory = list[ArmWaypoint]
# Secuencia ORDENADA de waypoints — contrato de salida de M7 hacia M8.


# ---------------------------------------------------------------------------
# JointMap (resultado de IK, cacheado por sesión)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocationSolution:
    """Resultado de IK para una Location, ya resuelto y cacheado."""

    grasp: JointAngles
    transit: JointAngles
    orientation_relaxed: bool
    # True si tuvo que relajarse la verticalidad estricta para converger
    # (en grasp y/o en transit).


JointMap = dict[Location, LocationSolution]
# 68 entradas, mismas claves que CalibrationMap (M0).


# ---------------------------------------------------------------------------
# Configuración de IK
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DEConfig:
    """Parámetros de differential_evolution_ik.

    Valores por defecto: los del notebook original
    (chess_robot_arm_dk_ik.py). Ajustar requiere revalidar tiempos de
    cómputo de build_joint_map (ver M7_SPEC.md §2.1 y §7).
    """

    NP: int = 150
    G_max: int = 2000
    F: float = 0.7
    CR: float = 0.85
    tol: float = 1e-4
    W_p: float = 1.0
    W_o: float = 0.05
    seed: int | None = None


# Tolerancia de posición aceptada para considerar una solución IK válida,
# en mm. Distinta de DEConfig.tol (umbral de PARADA del algoritmo, en
# unidades de la función de costo combinada).
POSITION_TOLERANCE_MM: float = 2.0  # ⚠️ placeholder, ver M7_SPEC.md §7

# Pasos de inclinación a reintentar si la verticalidad estricta no
# converge, en grados respecto a la vertical.
TILT_RETRY_STEPS_DEG: tuple[float, ...] = (0.0, 10.0, 20.0, 30.0)
MAX_TILT_DEG: float = 30.0  # ⚠️ placeholder, ver M7_SPEC.md §7

# Altura de tránsito por encima de la altura real de la pieza/zona, en mm.
SAFE_TRAVEL_HEIGHT_MM: float = 80.0  # ⚠️ PLACEHOLDER — medir con set real


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


class KinematicsError(Exception):
    """Clase base de errores de contrato de chess_kinematics."""


class UnreachableLocationError(KinematicsError):
    """Ninguna orientación (vertical estricta ni las inclinaciones de
    TILT_RETRY_STEPS_DEG) permitió converger dentro de
    POSITION_TOLERANCE_MM, para grasp y/o transit de esta Location.

    Se lanza al construir el JointMap, nunca durante la partida.
    """

    def __init__(self, location: Location, message: str):
        self.location = location
        super().__init__(f"{location}: {message}")


class JointMapSessionNotFoundError(KinematicsError):
    """No existe un JointMap de sesión válido para la partida actual."""
