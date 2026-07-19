"""Producto funcional standalone de chess_vision (M2 + M3).

Toma una imagen local de un tablero real, la corre por el pipeline
completo (detección clásica del tablero + modelo de piezas pretrained
de la comunidad) e imprime en consola, de forma clara:

    1. La ENTRADA exacta (imagen, dimensiones).
    2. Lo que hace M2 (esquinas detectadas, grilla de casillas).
    3. Lo que hace M3 (detecciones crudas del modelo).
    4. La SALIDA exacta: el VisionInput final, con la posición de las
       piezas ya mapeada a casillas.

No depende de Vision real (ESP32-CAM) ni del brazo — es la
contraparte de M2/M3 al `vision_main.py` de chess_brain (M4/M5).

Uso:
    python vision_main.py --image test_tablero.jpg --model models/chess-model-yolov8m.pt
    python vision_main.py --image test_tablero.jpg --model models/chess-model-yolov8m.pt --calibrate
    uv run python ./src/chess_vision/vision_main.py --image ./tests/test_vision/fixtures/sample_frames/test_tablero.jpeg --model ./src/chess_vision/models/chess-model-yolov8m.pt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import matplotlib.pyplot as plt

from chess_vision.piece_classifier import detect_pieces
from chess_vision.pipeline import calibrate_orientation, locate_board, process_frame
from chess_vision.square_mapper import assign_pieces_to_grid
from chess_vision.vision_types import (
    BoardNotFoundError,
    LowConfidenceDetectionError,
    VisionError,
)

_SEP = "=" * 70


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Extrae y define los argumentos de configuración del módulo Vision."""
    parser = argparse.ArgumentParser(
        description="CLI de prueba para Módulo de Visión (M2+M3).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--image",
        default="./tests/test_vision/fixtures/sample_frames/test_tablero.jpeg",
        help="Ruta a la imagen local.",
    )
    parser.add_argument(
        "--model",
        default="./src/chess_vision/models/chess-model-yolov8m.pt",
        help="Ruta al modelo (.pt).",
    )
    parser.add_argument("--side-to-move", choices=["w", "b"], default="w")
    parser.add_argument(
        "--orientation", choices=["identity", "rotated_180"], default="identity"
    )
    parser.add_argument(
        "--calibrate", action="store_true", help="Resuelve orientación automáticamente."
    )
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    return parser.parse_args(argv)


def _print_header(title: str) -> None:
    print(f"\n{_SEP}\n{title}\n{_SEP}")


def _render_ascii_board(board_matrix: list[list[str | None]]) -> str:
    """Tablero ASCII simple, vista desde blancas (fila 0 = rank 8)."""
    lines = []
    for rank_idx, row in enumerate(board_matrix):
        rank_label = 8 - rank_idx
        cells = " ".join(cell if cell else ".." for cell in row)
        lines.append(f"  {rank_label}  {cells}")
    lines.append("      a  b  c  d  e  f  g  h")
    return "\n".join(lines)


def _load_piece_model(model_path: str):
    try:
        from ultralytics import YOLO
    except ImportError:
        print(
            "ERROR: no está instalado 'ultralytics'. Instálalo con:\n"
            "    uv add ultralytics\n"
            "(o `pip install ultralytics --break-system-packages` fuera de uv)"
        )
        sys.exit(1)

    if not Path(model_path).exists():
        print(
            f"ERROR: no se encontró el modelo en '{model_path}'.\n"
            "Ver M2_M3_SPEC.md para instrucciones de descarga."
        )
        sys.exit(1)

    return YOLO(model_path)


def run() -> int:
    args = _parse_args(sys.argv[1:])

    # --- [1] ENTRADA ---------------------------------------------------
    _print_header("[1] ENTRADA")
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"ERROR: no se encontró la imagen '{image_path}'.")
        return 1

    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"ERROR: '{image_path}' existe pero no se pudo decodificar como imagen.")
        return 1

    height, width, channels = frame.shape
    print(f"  Archivo:      {image_path}")
    print(
        f"  Dimensiones:  {width} x {height} px (ancho x alto), {channels} canales (BGR)"
    )
    print(f"  dtype:        {frame.dtype}")

    piece_model = _load_piece_model(args.model)
    print(f"  Modelo:       {args.model}")

    # --- [2] M2 — Detección del tablero --------------------------------
    _print_header("[2] M2 — Detección del tablero (clásica, sin ML)")
    try:
        corners, grid = locate_board(frame)
    except BoardNotFoundError as exc:
        print(f"ERROR (BoardNotFoundError): {exc}")
        return 1

    print("  Esquinas detectadas (px):")
    print(f"    top_left:     {corners.top_left}")
    print(f"    top_right:    {corners.top_right}")
    print(f"    bottom_left:  {corners.bottom_left}")
    print(f"    bottom_right: {corners.bottom_right}")
    print(
        f"  Grilla de {len(grid)}x{len(grid[0])} casillas calculada (con perspectiva real)."
    )

    # --- VISUALIZACIÓN M2: Tablero y Grilla (Corregido) ---
    img_board = frame.copy()

    # Dibujar las 4 esquinas principales del tablero entero (Rojo)
    for corner in [
        corners.top_left,
        corners.top_right,
        corners.bottom_left,
        corners.bottom_right,
    ]:
        cv2.circle(
            img_board,
            (int(corner[0]), int(corner[1])),
            radius=8,
            color=(0, 0, 255),
            thickness=-1,
        )

    # Dibujar los vértices de cada casilla interna (Verde)
    for row in grid:
        for casilla in row:
            # 'casilla' contiene 4 esquinas: (v1, v2, v3, v4)
            for vertice in casilla:
                # 'vertice' es un Point2D: (x, y)
                cv2.circle(
                    img_board,
                    (int(vertice[0]), int(vertice[1])),
                    radius=3,
                    color=(0, 255, 0),
                    thickness=-1,
                )

    img_board_rgb = cv2.cvtColor(img_board, cv2.COLOR_BGR2RGB)

    plt.figure(figsize=(8, 8))
    plt.imshow(img_board_rgb)
    plt.title("M2: Esquinas detectadas y Grilla proyectada")
    plt.axis("off")
    plt.show(block=False)

    # --- [3] M3 — Detección de piezas ----------------------------------
    _print_header("[3] M3 — Detección de piezas")
    raw_detections = detect_pieces(frame, piece_model, conf_threshold=0.1)
    camera_matrix, confidences = assign_pieces_to_grid(raw_detections, grid)
    mapped_count = sum(1 for row in camera_matrix for cell in row if cell is not None)
    uncertain_count = sum(
        1 for row in confidences for c in row if c < args.confidence_threshold
    )
    print(f"  Detecciones crudas del modelo (conf >= 0.10): {len(raw_detections)}")
    print(f"  Piezas mapeadas a alguna casilla:             {mapped_count}")
    print(
        f"  Casillas con confianza < {args.confidence_threshold:.2f}:              {uncertain_count}"
    )

    # --- VISUALIZACIÓN M3: Detección de Piezas ---
    img_pieces = frame.copy()

    for det in raw_detections:
        x1, y1, x2, y2 = map(int, det.bbox_px)

        # Dibujar la caja delimitadora (Azul)
        cv2.rectangle(img_pieces, (x1, y1), (x2, y2), color=(255, 0, 0), thickness=2)

        # Dibujar el texto con la clase y confianza
        label = f"{det.piece_code} ({det.confidence:.2f})"
        cv2.putText(
            img_pieces,
            label,
            (x1, max(y1 - 10, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 0),
            2,
        )

    img_pieces_rgb = cv2.cvtColor(img_pieces, cv2.COLOR_BGR2RGB)

    plt.figure(figsize=(8, 8))
    plt.imshow(img_pieces_rgb)
    plt.title("M3: Detección de Piezas (Raw)")
    plt.axis("off")
    plt.show(block=False)

    # --- [4] SALIDA — VisionInput ---------------------------------------
    _print_header("[4] SALIDA — VisionInput")
    try:
        if args.calibrate:
            orientation = calibrate_orientation(frame, piece_model)
            print(
                f"  Orientación resuelta automáticamente (--calibrate): {orientation}"
            )
        else:
            orientation = args.orientation
            print(f"  Orientación usada (fija, --orientation): {orientation}")

        vision_input = process_frame(
            frame,
            piece_model,
            orientation=orientation,
            side_to_move=args.side_to_move,
            confidence_threshold=args.confidence_threshold,
        )
    except LowConfidenceDetectionError as exc:
        print(f"\nERROR (LowConfidenceDetectionError): {exc}")
        print(
            "(baja --confidence-threshold para ver el resultado de todas formas, con precaución)"
        )
        return 1
    except VisionError as exc:
        print(f"\nERROR ({type(exc).__name__}): {exc}")
        return 1

    print()
    print(_render_ascii_board(vision_input.board_matrix))
    print()
    print("  Estructura VisionInput exacta:")
    print(f"    side_to_move = {vision_input.side_to_move!r}")
    print("    board_matrix = [")
    for row in vision_input.board_matrix:
        print(f"        {row!r},")
    print("    ]")
    print(f"\n{_SEP}\n")

    plt.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
