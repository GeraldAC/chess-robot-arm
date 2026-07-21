"""Lectura de medición manual, construcción y persistencia del
CalibrationMap para chess_calibration (M0).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from chess_calibration.calibration_geometry import (
    compute_square_centers,
    validate_board_geometry,
)
from chess_calibration.calibration_types import (
    ArmPoint,
    BoardCornersArm,
    CalibrationMap,
    CalibrationSessionNotFoundError,
    IncompleteCalibrationInputError,
)
from chess_planner.movement_types import Zone

REQUIRED_CORNERS = ("a1", "a8", "h1", "h8")
REQUIRED_ZONES = tuple(zone.value for zone in Zone)


def _point_from_dict(raw: object, context: str) -> ArmPoint:
    if not isinstance(raw, dict):
        raise IncompleteCalibrationInputError(
            f"Punto inválido para '{context}': se esperaba un mapeo con x_mm, y_mm, z_mm"
        )
    try:
        return ArmPoint(
            x_mm=float(raw["x_mm"]), y_mm=float(raw["y_mm"]), z_mm=float(raw["z_mm"])
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IncompleteCalibrationInputError(
            f"Punto inválido o incompleto para '{context}': se esperaban x_mm, y_mm, z_mm numéricos"
        ) from exc


def load_calibration_input(path: str) -> tuple[BoardCornersArm, dict[Zone, ArmPoint]]:
    """Lee un YAML con los 4 corners (a1/a8/h1/h8) y los 4 puntos de zona
    medidos manualmente (ver formato en M0_SPEC.md §7). Lanza
    IncompleteCalibrationInputError si falta algún campo requerido o el
    archivo no existe / no es YAML válido."""
    input_path = Path(path)
    if not input_path.exists():
        raise IncompleteCalibrationInputError(
            f"No existe el archivo de entrada: {path}"
        )

    try:
        data = yaml.safe_load(input_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise IncompleteCalibrationInputError(
            f"YAML inválido en '{path}': {exc}"
        ) from exc

    raw_corners = data.get("square_corners", {}) or {}
    missing_corners = [c for c in REQUIRED_CORNERS if c not in raw_corners]
    if missing_corners:
        raise IncompleteCalibrationInputError(
            f"Faltan corners en '{path}': {', '.join(missing_corners)}"
        )
    corners = BoardCornersArm(
        a1=_point_from_dict(raw_corners["a1"], "square_corners.a1"),
        a8=_point_from_dict(raw_corners["a8"], "square_corners.a8"),
        h1=_point_from_dict(raw_corners["h1"], "square_corners.h1"),
        h8=_point_from_dict(raw_corners["h8"], "square_corners.h8"),
    )

    raw_zones = data.get("zones", {}) or {}
    missing_zones = [z for z in REQUIRED_ZONES if z not in raw_zones]
    if missing_zones:
        raise IncompleteCalibrationInputError(
            f"Faltan zonas en '{path}': {', '.join(missing_zones)}"
        )
    zones = {
        Zone(zone_name): _point_from_dict(raw_zones[zone_name], f"zones.{zone_name}")
        for zone_name in REQUIRED_ZONES
    }

    return corners, zones


def build_calibration_map(
    corners: BoardCornersArm,
    zones: dict[Zone, ArmPoint],
    expected_square_size_mm: float,
    tolerance_mm: float = 5.0,
) -> CalibrationMap:
    """Punto de entrada único del subsistema: valida geometría, interpola
    las 64 casillas, y combina el resultado con `zones` en un único
    CalibrationMap de 68 entradas."""
    validate_board_geometry(corners, expected_square_size_mm, tolerance_mm)
    calibration_map: CalibrationMap = dict(compute_square_centers(corners))
    for zone, point in zones.items():
        key = zone.value if isinstance(zone, Zone) else str(zone)
        calibration_map[key] = point
    return calibration_map


def save_calibration_session(calibration_map: CalibrationMap, path: str) -> None:
    """Persiste el CalibrationMap ya resuelto de la sesión actual a JSON,
    para que el Orquestador (M10) lo cargue sin repetir la interpolación
    durante la partida."""
    serializable = {
        location: {"x_mm": p.x_mm, "y_mm": p.y_mm, "z_mm": p.z_mm}
        for location, p in calibration_map.items()
    }
    Path(path).write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_calibration_session(path: str) -> CalibrationMap:
    """Carga un CalibrationMap ya resuelto de una sesión previa. Lanza
    CalibrationSessionNotFoundError si el archivo no existe, no es JSON
    válido, o está incompleto (< 68 claves: 64 casillas + 4 zonas)."""
    session_path = Path(path)
    if not session_path.exists():
        raise CalibrationSessionNotFoundError(
            f"No existe sesión de calibración en: {path}"
        )

    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CalibrationSessionNotFoundError(
            f"Sesión de calibración inválida en: {path}"
        ) from exc

    expected_keys = 64 + len(REQUIRED_ZONES)
    if len(data) < expected_keys:
        raise CalibrationSessionNotFoundError(
            f"Sesión de calibración incompleta en '{path}': "
            f"{len(data)} claves, se esperaban {expected_keys}"
        )

    return {
        location: ArmPoint(x_mm=p["x_mm"], y_mm=p["y_mm"], z_mm=p["z_mm"])
        for location, p in data.items()
    }
