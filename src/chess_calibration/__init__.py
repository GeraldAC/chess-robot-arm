"""Superficie pública de chess_calibration (M0).

Ver M0_SPEC.md para el contrato completo. Igual que en chess_brain,
chess_vision y chess_planner, este es el único contrato que M7 y el
futuro Orquestador (M10) deberían asumir estable; el resto de funciones
internas puede cambiar sin romper integración.
"""

from chess_calibration.calibration_io import (
    build_calibration_map,
    load_calibration_session,
    save_calibration_session,
)
from chess_calibration.calibration_types import (
    ArmPoint,
    BoardCornersArm,
    CalibrationError,
    CalibrationMap,
    CalibrationSessionNotFoundError,
    IncompleteCalibrationInputError,
    InvalidBoardGeometryError,
)

__all__ = [
    "ArmPoint",
    "BoardCornersArm",
    "CalibrationMap",
    "CalibrationError",
    "IncompleteCalibrationInputError",
    "InvalidBoardGeometryError",
    "CalibrationSessionNotFoundError",
    "build_calibration_map",
    "save_calibration_session",
    "load_calibration_session",
]
