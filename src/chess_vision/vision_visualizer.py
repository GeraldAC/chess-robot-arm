from __future__ import annotations

import cv2
import matplotlib.pyplot as plt
from cv2.typing import MatLike

from chess_vision.vision_types import (
    BoardCorners,
    CameraOrientedGrid,
    PieceDetection,
)


def plot_board_grid(
    frame: MatLike, corners: BoardCorners, grid: CameraOrientedGrid
) -> None:
    """M2: Dibuja las esquinas detectadas y la grilla sobre la imagen original."""
    img_board = frame.copy()

    # Dibujar las 4 esquinas principales del tablero (Rojo)
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


def plot_piece_detections(frame: MatLike, raw_detections: list[PieceDetection]) -> None:
    """M3: Dibuja las cajas delimitadoras y etiquetas de piezas detectadas."""
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


def show_plots() -> None:
    """Bloquea la ejecución para mantener las ventanas de Matplotlib abiertas."""
    plt.show()
