"""Contratos internos de chess_calibration (M0).

Ver M0_SPEC.md para el detalle de cada decisión de diseño.
"""

from __future__ import annotations

from dataclasses import dataclass

# Location reutiliza la misma noción que chess_planner: casilla algebraica
# ("a1".."h8") o el .value de chess_planner.movement_types.Zone.
Location = str


@dataclass(frozen=True)
class ArmPoint:
    """Coordenada cartesiana en el sistema de referencia del brazo.

    Origen: intersección del eje de rotación de la base del brazo con el
    plano de la mesa. Eje X: hacia adelante (posición 0° de la base).
    Eje Y: perpendicular a X sobre el plano de la mesa (regla de la mano
    derecha). Eje Z: vertical, positivo hacia arriba. Unidades: mm.
    """

    x_mm: float
    y_mm: float
    z_mm: float


@dataclass(frozen=True)
class BoardCornersArm:
    """Centros medidos de las 4 casillas-esquina del tablero físico, en
    coordenadas del brazo. NO son el borde físico del tablero, sino el
    centro de las casillas a1, a8, h1 y h8 (ver M0_SPEC.md §4)."""

    a1: ArmPoint
    a8: ArmPoint
    h1: ArmPoint
    h8: ArmPoint


CalibrationMap = dict[Location, ArmPoint]
# 64 entradas de casilla ("a1".."h8") + 4 entradas de zona
# (Zone.value de chess_planner.movement_types) = 68 claves.


class CalibrationError(Exception):
    """Clase base de errores de contrato de chess_calibration."""


class IncompleteCalibrationInputError(CalibrationError):
    """Falta algún corner, alguna zona requerida, o el archivo de entrada
    no existe / no se pudo interpretar."""


class InvalidBoardGeometryError(CalibrationError):
    """Los 4 puntos medidos de las esquinas no forman una geometría de
    tablero plausible dentro de la tolerancia configurada. Suele indicar
    un error de medición o de tipeo, no un tablero real deforme."""

    def __init__(
        self,
        message: str,
        measured: dict[str, float],
        expected: dict[str, float],
    ) -> None:
        super().__init__(message)
        self.measured = measured
        self.expected = expected


class CalibrationSessionNotFoundError(CalibrationError):
    """No existe un archivo de sesión de calibración válido para la
    partida actual. El Orquestador (M10) debe tratar esto como señal de
    flujo (pedir recalibración), no como fallo silencioso."""
