"""chess_kinematics — Módulo 7: Cinemática Inversa.

Superficie pública. Ver M7_SPEC.md §4.4: este es el único contrato que
M8 y el futuro Orquestador (M10) deberían asumir estable.

Uso esperado por el Orquestador:
    1. build_joint_map(calibration_map)  — UNA VEZ por sesión, después de M0.
    2. plan_trajectory(physical_plan, joint_map) — UNA VEZ por cada MoveResult
       del motor, después de M6.
"""

from chess_kinematics.kinematics_map import (
    build_joint_map,
    load_joint_map_session,
    save_joint_map_session,
    solve_location,
)
from chess_kinematics.kinematics_planner import plan_trajectory
from chess_kinematics.kinematics_types import (
    ArmTrajectory,
    ArmWaypoint,
    DEConfig,
    GripperAction,
    JointAngles,
    JointMap,
    JointMapSessionNotFoundError,
    KinematicsError,
    LocationSolution,
    UnreachableLocationError,
    WaypointKind,
)

__all__ = [
    "build_joint_map",
    "save_joint_map_session",
    "load_joint_map_session",
    "solve_location",
    "plan_trajectory",
    "ArmTrajectory",
    "ArmWaypoint",
    "DEConfig",
    "GripperAction",
    "JointAngles",
    "JointMap",
    "JointMapSessionNotFoundError",
    "KinematicsError",
    "LocationSolution",
    "UnreachableLocationError",
    "WaypointKind",
]
