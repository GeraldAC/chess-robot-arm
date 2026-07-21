from __future__ import annotations

import matplotlib.patches as patches
import matplotlib.pyplot as plt

from chess_calibration.calibration_types import (
    CalibrationMap,
)

FILES = "abcdefgh"
RANKS = "12345678"


def plot_calibration_map(
    calibration_map: CalibrationMap, square_size_mm: float = 40.0
) -> None:
    """Visualiza en 2D el mapa de calibración del brazo robótico."""
    _, ax = plt.subplots(figsize=(10, 10))

    half_sq = square_size_mm / 2.0  # 20.0 mm
    board_min = -half_sq
    board_size = square_size_mm * 8  # 320.0 mm

    # 1. Dibujar el tablero con escaques claros y oscuros
    color_light = "#f0d9b5"
    color_dark = "#b58863"

    for row_idx in range(8):
        for col_idx in range(8):
            x_min = col_idx * square_size_mm - half_sq
            y_min = row_idx * square_size_mm - half_sq

            is_dark = (col_idx + row_idx) % 2 == 0
            square_color = color_dark if is_dark else color_light

            rect = patches.Rectangle(
                (x_min, y_min),
                square_size_mm,
                square_size_mm,
                facecolor=square_color,
                edgecolor="#8b6c42",
                linewidth=0.5,
                alpha=0.6,
                zorder=1,
            )
            ax.add_patch(rect)

    # Marco exterior del tablero
    board_outer = patches.Rectangle(
        (board_min, board_min),
        board_size,
        board_size,
        linewidth=2.5,
        edgecolor="#3a2510",
        facecolor="none",
        zorder=2,
        label="Borde Tablero",
    )
    ax.add_patch(board_outer)

    # 2. Coordenadas en los bordes del tablero (A-H, 1-8)
    for col_idx, file_ in enumerate(FILES):
        x_pos = col_idx * square_size_mm
        ax.text(
            x_pos,
            board_min - 12,
            file_.upper(),
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="top",
        )
        ax.text(
            x_pos,
            board_min + board_size + 12,
            file_.upper(),
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="bottom",
        )

    for row_idx, rank in enumerate(RANKS):
        y_pos = row_idx * square_size_mm
        ax.text(
            board_min - 12,
            y_pos,
            rank,
            fontsize=10,
            fontweight="bold",
            ha="right",
            va="center",
        )
        ax.text(
            board_min + board_size + 12,
            y_pos,
            rank,
            fontsize=10,
            fontweight="bold",
            ha="left",
            va="center",
        )

    # Banners de orientación de bandos
    ax.text(
        board_min + board_size / 2,
        board_min - 38,
        "♔ LADO BLANCAS (Filas 1-2) ♔",
        fontsize=9,
        fontweight="bold",
        color="#1f4e79",
        ha="center",
        va="top",
        bbox=dict(boxstyle="round,pad=0.3", fc="#e8f4f8", ec="#1f4e79", lw=1.2),
    )
    ax.text(
        board_min + board_size / 2,
        board_min + board_size + 38,
        "♚ LADO NEGRAS (Filas 7-8) ♚",
        fontsize=9,
        fontweight="bold",
        color="#1a1a1a",
        ha="center",
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.3", fc="#d9d9d9", ec="#1a1a1a", lw=1.2),
    )

    # 3. Zonas y Casillas
    board_x, board_y = [], []

    zone_styles = {
        "WHITE": {
            "marker_color": "#1f77b4",
            "fc": "#ffffff",
            "ec": "#1f77b4",
            "text_color": "#003366",
            "icon": "♔ ",
        },
        "BLACK": {
            "marker_color": "#2ca02c",
            "fc": "#262626",
            "ec": "#000000",
            "text_color": "#ffffff",
            "icon": "♚ ",
        },
        "DEFAULT": {
            "marker_color": "crimson",
            "fc": "#fff0f0",
            "ec": "crimson",
            "text_color": "crimson",
            "icon": "📍 ",
        },
    }

    for key, point in calibration_map.items():
        if len(key) == 2 and key[0] in FILES and key[1] in RANKS:
            board_x.append(point.x_mm)
            board_y.append(point.y_mm)
            ax.text(
                point.x_mm,
                point.y_mm - 5,
                key,
                fontsize=7,
                fontweight="bold",
                ha="center",
                va="center",
                color="#222222",
                zorder=5,
            )
        else:
            key_upper = key.upper()
            style = (
                zone_styles["WHITE"]
                if "WHITE" in key_upper
                else (
                    zone_styles["BLACK"]
                    if "BLACK" in key_upper
                    else zone_styles["DEFAULT"]
                )
            )

            ax.scatter(
                point.x_mm,
                point.y_mm,
                c=style["marker_color"],
                marker="D",
                s=100,
                edgecolors="black",
                linewidth=1,
                zorder=6,
            )

            display_text = f"{style['icon']}{key}\n({point.x_mm:.0f}, {point.y_mm:.0f}, z={point.z_mm:.0f})"
            va_align = "bottom" if point.y_mm >= 140 else "top"
            y_offset = 14 if point.y_mm >= 140 else -14

            ax.text(
                point.x_mm,
                point.y_mm + y_offset,
                display_text,
                fontsize=7.5,
                fontweight="bold",
                color=style["text_color"],
                ha="center",
                va=va_align,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    fc=style["fc"],
                    ec=style["ec"],
                    lw=1.2,
                    alpha=0.95,
                ),
                zorder=7,
            )

    ax.scatter(
        board_x,
        board_y,
        c="#d62728",
        marker="+",
        s=25,
        linewidths=1.0,
        label="Centros de Casilla",
        zorder=4,
    )

    # 4. Ajustes de límites y título
    ax.set_title(
        "M0: Mapa de Calibración del Espacio de Trabajo (Plano XY)",
        fontsize=12,
        fontweight="bold",
        pad=20,
    )
    ax.set_xlabel("Eje X del Brazo (mm)", fontsize=10, labelpad=8)
    ax.set_ylabel("Eje Y del Brazo (mm)", fontsize=10, labelpad=8)

    ax.set_aspect("equal", adjustable="box")

    # MÁRGENES AMPLIADOS: evitan que el título y las zonas se corten
    ax.set_xlim(-130, 410)
    ax.set_ylim(-140, 420)

    ax.grid(True, which="both", linestyle="--", alpha=0.25)

    # LEYENDA FUERA DEL ÁREA UTILIZADA: se ubica abajo horizontalmente para no obstruir nada
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=2,
        framealpha=0.9,
        fontsize=9,
    )

    plt.tight_layout()
    plt.show()
