"""Traducción de PhysicalPlan (M6) + JointMap a ArmTrajectory (M7).

plan_trajectory es el contrato de salida hacia M8 (resuelve el pendiente
de GENERAL_SPEC.md §4.2: "M7 → M8: formato de ángulos de articulación /
trayectoria"). NO invoca IK: solo consulta el JointMap ya resuelto por
kinematics_map.build_joint_map — ver M7_SPEC.md §4.3.
"""

from __future__ import annotations

from chess_kinematics.kinematics_types import (
    ArmTrajectory,
    ArmWaypoint,
    GripperAction,
    JointMap,
    KinematicsError,
    LocationSolution,
    WaypointKind,
)
from chess_planner.movement_types import Location, PhysicalPlan, PieceTransfer, Zone

_DISCARD_ZONE_VALUES = {Zone.DISCARD_WHITE.value, Zone.DISCARD_BLACK.value}


def _is_discard_zone(location: Location) -> bool:
    """True si location es Zone.DISCARD_WHITE/BLACK.

    Estas zonas no requieren descenso preciso (BOM.md §5: la pieza se
    libera por caída en bandeja, sin necesidad de posicionamiento fino),
    a diferencia de Zone.SPARE_* (toma de dama de repuesto) que sí
    requiere un grasp preciso, igual que una casilla del tablero.
    """
    return location in _DISCARD_ZONE_VALUES


def _location_release_sequence(
    location: Location,
    solution: LocationSolution,
    gripper_action: GripperAction,
) -> ArmTrajectory:
    """Secuencia de waypoints para una única Location dentro de una
    transferencia: [TRANSIT+HOLD, GRASP+gripper_action, TRANSIT+HOLD]
    para casillas y Zone.SPARE_*; [TRANSIT+gripper_action] para
    Zone.DISCARD_* (ver _is_discard_zone).
    """
    if _is_discard_zone(location):
        return [
            ArmWaypoint(
                location=location,
                joint_angles=solution.transit,
                gripper=gripper_action,
                kind=WaypointKind.TRANSIT,
            )
        ]

    return [
        ArmWaypoint(
            location=location,
            joint_angles=solution.transit,
            gripper=GripperAction.HOLD,
            kind=WaypointKind.TRANSIT,
        ),
        ArmWaypoint(
            location=location,
            joint_angles=solution.grasp,
            gripper=gripper_action,
            kind=WaypointKind.GRASP,
        ),
        ArmWaypoint(
            location=location,
            joint_angles=solution.transit,
            gripper=GripperAction.HOLD,
            kind=WaypointKind.TRANSIT,
        ),
    ]


def _lookup(location: Location, joint_map: JointMap) -> LocationSolution:
    try:
        return joint_map[location]
    except KeyError as exc:
        raise KinematicsError(
            f"Location '{location}' no está presente en el JointMap de la "
            f"sesión actual. ¿Se corrió build_joint_map con un "
            f"CalibrationMap completo?"
        ) from exc


def plan_transfer(transfer: PieceTransfer, joint_map: JointMap) -> ArmTrajectory:
    """Traduce un único PieceTransfer a su secuencia de waypoints.

    NO vuelve a invocar IK: solo consulta joint_map[location].
    """
    origin_solution = _lookup(transfer.origin, joint_map)
    destination_solution = _lookup(transfer.destination, joint_map)

    return _location_release_sequence(
        transfer.origin, origin_solution, GripperAction.CLOSE
    ) + _location_release_sequence(
        transfer.destination, destination_solution, GripperAction.OPEN
    )


def plan_trajectory(physical_plan: PhysicalPlan, joint_map: JointMap) -> ArmTrajectory:
    """Punto de entrada único de chess_kinematics para el ciclo de partida.

    Concatena plan_transfer(transfer, joint_map) para cada PieceTransfer
    del PhysicalPlan, en orden.
    """
    trajectory: ArmTrajectory = []
    for transfer in physical_plan:
        trajectory.extend(plan_transfer(transfer, joint_map))
    return trajectory
