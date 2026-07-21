"""CLI de producto funcional de chess_calibration (M0).

Se ejecuta una vez por sesión de juego, antes de que el Orquestador (M10)
arranque el ciclo de partida. Lee el archivo de medición manual
(--input), valida y resuelve el CalibrationMap, lo imprime en consola y
lo persiste en un archivo de sesión (--output) para que el resto del
sistema lo consuma durante la partida.

Ejemplo:
    uv run python -m chess_calibration.calibration_main \\
        --input calibration_input.yaml \\
        --square-size-mm 40.0
    uv run chess-calibration
    uv run chess-calibration --input ./mis_puntos.yaml --square-size-mm 35.0 --output mi_mapa.json
    uv run chess-calibration -i ./mis_puntos.yaml -s 35.0 -o mi_mapa.json
"""

from __future__ import annotations

import argparse
import sys

from chess_calibration.calibration_io import (
    build_calibration_map,
    load_calibration_input,
    save_calibration_session,
)
from chess_calibration.calibration_types import ArmPoint, CalibrationError
from chess_calibration.calibration_visualizer import plot_calibration_map

FILES = "abcdefgh"
RANKS = "12345678"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "M0 - Calibración: resuelve casilla/zona -> coordenada del brazo "
            "a partir de medición manual."
        )
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="tests/test_calibration/fixtures/sample_calibration.yaml",
        help=(
            "Ruta al archivo YAML de entrada con las coordenadas de calibración. "
            "(default: tests/test_calibration/fixtures/sample_calibration.yaml)"
        ),
    )
    parser.add_argument(
        "--square-size-mm",
        "-s",
        type=float,
        default=40.0,
        help="Tamaño del lado de cada casilla del tablero en milímetros. (default: 40.0)",
    )
    parser.add_argument(
        "--tolerance-mm",
        type=float,
        default=5.0,
        help="Tolerancia de validación de geometría, en mm (default: 5.0)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="tests/test_calibration/fixtures/calibration_map.json",
        help="Ruta de salida para guardar el mapa de calibración generado. (default: tests/test_calibration/fixtures/calibration_map.json)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Abre una ventana interactiva de matplotlib con la vista 2D del mapa generado.",
    )
    return parser.parse_args(argv)


def _print_summary(corners, zones: dict, calibration_map: dict[str, ArmPoint]) -> None:
    print("=== M0 - Calibración ===\n")

    print("Corners medidos (centro de casilla):")
    for name, point in (
        ("a1", corners.a1),
        ("a8", corners.a8),
        ("h1", corners.h1),
        ("h8", corners.h8),
    ):
        print(
            f"  {name}: x={point.x_mm:8.1f}  y={point.y_mm:8.1f}  z={point.z_mm:7.1f}  (mm)"
        )

    print("\nZonas medidas:")
    for zone, point in zones.items():
        label = zone.value if hasattr(zone, "value") else str(zone)
        print(
            f"  {label:<14}: x={point.x_mm:8.1f}  y={point.y_mm:8.1f}  z={point.z_mm:7.1f}  (mm)"
        )

    print(
        f"\nCalibrationMap resuelto: {len(calibration_map)} entradas (64 casillas + {len(zones)} zonas)\n"
    )
    for rank in reversed(RANKS):
        row = []
        for file_ in FILES:
            square = f"{file_}{rank}"
            p = calibration_map[square]
            row.append(f"{square}=({p.x_mm:6.1f},{p.y_mm:6.1f},{p.z_mm:5.1f})")
        print("  ".join(row))


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        corners, zones = load_calibration_input(args.input)
        calibration_map = build_calibration_map(
            corners=corners,
            zones=zones,
            expected_square_size_mm=args.square_size_mm,
            tolerance_mm=args.tolerance_mm,
        )
    except CalibrationError as exc:
        print(f"Error de calibración: {exc}", file=sys.stderr)
        return 1

    _print_summary(corners, zones, calibration_map)

    save_calibration_session(calibration_map, args.output)
    print(f"\nSesión de calibración guardada en: {args.output}")

    # Lógica de visualización opcional
    if args.plot:
        print("\nAbriendo visualización (cierra la ventana para terminar)...")
        plot_calibration_map(calibration_map, args.square_size_mm)

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
