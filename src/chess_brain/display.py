"""Presentación en consola: tablero ASCII y formato legible de MoveResult.

Separado del CLI (main.py) para poder reusarlo en tests o en otras interfaces
(ej. un futuro log de partida) sin arrastrar lógica de entrada de usuario.
"""

from __future__ import annotations

import chess

from chess_brain.brain_types import MoveResult

_UNICODE_PIECES = {
    "P": "\u2659",
    "N": "\u2658",
    "B": "\u2657",
    "R": "\u2656",
    "Q": "\u2655",
    "K": "\u2654",
    "p": "\u265f",
    "n": "\u265e",
    "b": "\u265d",
    "r": "\u265c",
    "q": "\u265b",
    "k": "\u265a",
}


def render_board(board: chess.Board) -> str:
    """Tablero ASCII/Unicode con coordenadas, vista desde el lado de las blancas."""
    lines: list[str] = []
    lines.append("    a   b   c   d   e   f   g   h")
    lines.append("  +---+---+---+---+---+---+---+---+")
    for rank in range(7, -1, -1):
        row_cells = []
        for file in range(8):
            piece = board.piece_at(chess.square(file, rank))
            symbol = _UNICODE_PIECES[piece.symbol()] if piece else "."
            row_cells.append(symbol)
        lines.append(f"{rank + 1} | " + " | ".join(row_cells) + f" | {rank + 1}")
        lines.append("  +---+---+---+---+---+---+---+---+")
    lines.append("    a   b   c   d   e   f   g   h")
    return "\n".join(lines)


def render_move_result(result: MoveResult, mover_label: str) -> str:
    """Resumen legible de un MoveResult, para imprimir tras cada turno."""
    parts = [
        f"{mover_label} jugo {result.move_uci} ({result.piece}: {result.from_square}->{result.to_square})"
    ]

    tags = []
    if result.is_capture:
        tags.append(
            f"captura de {result.captured_piece}"
            + (" (al paso)" if result.is_en_passant else "")
        )
    if result.is_castle:
        tags.append(f"enroque {result.castle_side}")
    if result.is_promotion:
        tags.append(f"promocion a {result.promotion_piece}")
    if tags:
        parts.append("[" + ", ".join(tags) + "]")

    status_labels = {
        "checkmate": "¡JAQUE MATE!",
        "check": "Jaque.",
        "stalemate": "Tablas por ahogado.",
        "draw": "Tablas.",
        "ongoing": "",
    }
    label = status_labels.get(result.game_status, "")
    if label:
        parts.append(label)

    return " ".join(parts)
