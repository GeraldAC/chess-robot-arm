"""Construcción y persistencia del JointMap (M7).

build_joint_map se ejecuta UNA VEZ por sesión de juego, inmediatamente
después de M0 (chess_calibration) y antes de que el Orquestador (M10)
arranque el ciclo de partida — ver M7_SPEC.md §2.1 y §4.2.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from chess_calibration.calibration_types import ArmPoint, CalibrationMap, Location
from chess_kinematics.kinematics_ik import solve_ik
from chess_kinematics.kinematics_types import (
    DEConfig,
    JointAngles,
    JointMap,
    JointMapSessionNotFoundError,
    LocationSolution,
    POSITION_TOLERANCE_MM,
    SAFE_TRAVEL_HEIGHT_MM,
    TILT_RETRY_STEPS_DEG,
    UnreachableLocationError,
)

EXPECTED_LOCATION_COUNT = 68  # 64 casillas + 4 zonas, ver M0_SPEC.md §5.1


def _solve_with_retries(
    location: Location,
    point: ArmPoint,
    de_config: DEConfig,
    position_tolerance_mm: float,
    tilt_steps_deg: tuple[float, ...],
) -> tuple[JointAngles, bool]:
    """Intenta IK con verticalidad estricta primero, luego relaja la
    inclinación según tilt_steps_deg. Retorna (JointAngles, relaxed)."""
    last_error_mm = float("inf")
    for tilt_deg in tilt_steps_deg:
        angles, error_mm = solve_ik(point, tilt_deg=tilt_deg, de_config=de_config)
        last_error_mm = error_mm
        if error_mm <= position_tolerance_mm:
            return angles, (tilt_deg != 0.0)

    raise UnreachableLocationError(
        location,
        f"no convergió dentro de {position_tolerance_mm} mm en ninguna "
        f"inclinación probada ({tilt_steps_deg}); mejor error obtenido: "
        f"{last_error_mm:.2f} mm.",
    )


def solve_location(
    location: Location,
    point: ArmPoint,
    safe_travel_height_mm: float = SAFE_TRAVEL_HEIGHT_MM,
    de_config: DEConfig = DEConfig(),
    position_tolerance_mm: float = POSITION_TOLERANCE_MM,
    tilt_steps_deg: tuple[float, ...] = TILT_RETRY_STEPS_DEG,
) -> LocationSolution:
    """Resuelve grasp y transit para una única Location.

    Lanza UnreachableLocationError si alguna de las dos (grasp o
    transit) no converge en ninguna inclinación probada.
    """
    grasp_angles, grasp_relaxed = _solve_with_retries(
        location, point, de_config, position_tolerance_mm, tilt_steps_deg
    )

    transit_point = ArmPoint(
        x_mm=point.x_mm, y_mm=point.y_mm, z_mm=point.z_mm + safe_travel_height_mm
    )
    transit_angles, transit_relaxed = _solve_with_retries(
        location, transit_point, de_config, position_tolerance_mm, tilt_steps_deg
    )

    return LocationSolution(
        grasp=grasp_angles,
        transit=transit_angles,
        orientation_relaxed=(grasp_relaxed or transit_relaxed),
    )


def build_joint_map(
    calibration_map: CalibrationMap,
    safe_travel_height_mm: float = SAFE_TRAVEL_HEIGHT_MM,
    de_config: DEConfig = DEConfig(),
    position_tolerance_mm: float = POSITION_TOLERANCE_MM,
    tilt_steps_deg: tuple[float, ...] = TILT_RETRY_STEPS_DEG,
) -> JointMap:
    """Resuelve IK para las 68 Locations de calibration_map.

    Se ejecuta UNA VEZ por sesión de juego (ver M7_SPEC.md §2.1). Tiempo
    esperado: del orden de minutos en el hardware del BOM — aceptable
    por ser un paso de preparación de sesión, no de tiempo real de
    juego. Los 68 problemas de IK son independientes entre sí y
    paralelizables si el tiempo real resulta impráctico (ver
    M7_SPEC.md §7, no implementado en v1).
    """
    joint_map: JointMap = {}
    for location, point in calibration_map.items():
        joint_map[location] = solve_location(
            location,
            point,
            safe_travel_height_mm=safe_travel_height_mm,
            de_config=de_config,
            position_tolerance_mm=position_tolerance_mm,
            tilt_steps_deg=tilt_steps_deg,
        )
    return joint_map


# ---------------------------------------------------------------------------
# Persistencia de sesión (análogo a save/load_calibration_session de M0)
# ---------------------------------------------------------------------------


def _location_solution_to_dict(solution: LocationSolution) -> dict:
    return {
        "grasp": asdict(solution.grasp),
        "transit": asdict(solution.transit),
        "orientation_relaxed": solution.orientation_relaxed,
    }


def _location_solution_from_dict(data: dict) -> LocationSolution:
    return LocationSolution(
        grasp=JointAngles(**data["grasp"]),
        transit=JointAngles(**data["transit"]),
        orientation_relaxed=bool(data["orientation_relaxed"]),
    )


def save_joint_map_session(joint_map: JointMap, path: str) -> None:
    """Persiste el JointMap resuelto a JSON, análogo a
    save_calibration_session (M0)."""
    payload = {
        location: _location_solution_to_dict(solution)
        for location, solution in joint_map.items()
    }
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def load_joint_map_session(
    path: str, expected_location_count: int = EXPECTED_LOCATION_COUNT
) -> JointMap:
    """Carga un JointMap ya resuelto de una sesión previa.

    Lanza JointMapSessionNotFoundError si el archivo no existe, no es
    JSON válido, o tiene menos de expected_location_count claves.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise JointMapSessionNotFoundError(f"No existe el archivo de sesión: {path}")

    try:
        raw = json.loads(file_path.read_text())
    except json.JSONDecodeError as exc:
        raise JointMapSessionNotFoundError(f"Archivo de sesión inválido: {path}") from exc

    if len(raw) < expected_location_count:
        raise JointMapSessionNotFoundError(
            f"Sesión incompleta en {path}: {len(raw)} < {expected_location_count} claves."
        )

    return {location: _location_solution_from_dict(data) for location, data in raw.items()}
