"""M6 — Planificación de Movimiento.

Traduce un MoveResult (M4-5, jugada ya calculada y aplicada por el
motor) en una secuencia ordenada de PieceTransfer: las acciones físicas
necesarias para ejecutarla con el brazo robótico.

Alcance (ver M6_SPEC.md §1): SOLO jugadas originadas por el motor (la
respuesta de Stockfish). Las jugadas del humano ya se ejecutaron
físicamente con su propia mano y no requieren planificación de M6.
"""

from __future__ import annotations

from typing import Literal

import chess

from chess_brain.brain_types import MoveResult
from chess_planner.movement_types import (
    Color,
    PhysicalPlan,
    PieceTransfer,
    UnsupportedPromotionError,
    Zone,
)

CastleSide = Literal["kingside", "queenside"]

_DISCARD_ZONE: dict[Color, Zone] = {
    "w": Zone.DISCARD_WHITE,
    "b": Zone.DISCARD_BLACK,
}

_SPARE_ZONE: dict[Color, Zone] = {
    "w": Zone.SPARE_WHITE,
    "b": Zone.SPARE_BLACK,
}

_OPPONENT: dict[Color, Color] = {"w": "b", "b": "w"}

# Tabla fija: (color, castle_side) -> (rook_from, rook_to). Ver M6_SPEC.md §2.
_CASTLE_ROOK_SQUARES: dict[tuple[Color, CastleSide], tuple[str, str]] = {
    ("w", "kingside"): ("h1", "f1"),
    ("w", "queenside"): ("a1", "d1"),
    ("b", "kingside"): ("h8", "f8"),
    ("b", "queenside"): ("a8", "d8"),
}


def resolve_en_passant_captured_square(from_square: str, to_square: str) -> str:
    """Casilla real del peón capturado al paso: mismo file (columna) que
    `to_square`, mismo rank (fila) que `from_square`.

    No confundir con `to_square`, que es donde aterriza el peón que
    captura, no donde estaba el peón capturado.
    """
    captured_file = to_square[0]
    captured_rank = from_square[1]
    return f"{captured_file}{captured_rank}"


def resolve_castle_rook_squares(
    color: Color, castle_side: CastleSide
) -> tuple[str, str]:
    """Tabla fija de 4 casos (color x lado) -> (rook_from, rook_to)."""
    try:
        return _CASTLE_ROOK_SQUARES[(color, castle_side)]
    except KeyError as exc:
        raise ValueError(
            f"Combinación color/castle_side inválida: {color!r}, {castle_side!r}"
        ) from exc


def _mover_color(board_before: chess.Board) -> Color:
    """El color de quien movió es board_before.turn — el turno ANTES de
    aplicar la jugada (board_before es el estado previo al push), no el
    board.turn actual (que ya está invertido)."""
    return "w" if board_before.turn == chess.WHITE else "b"


def plan_move(move_result: MoveResult, board_before: chess.Board) -> PhysicalPlan:
    """Punto de entrada único de chess_planner (M6).

    Bifurca sobre los flags de `move_result`. is_castle, is_en_passant e
    is_promotion son mutuamente excluyentes por reglas de ajedrez;
    is_capture puede combinarse con is_en_passant o con is_promotion,
    pero nunca con is_castle (ver M6_SPEC.md §2).

    Lanza UnsupportedPromotionError si move_result.promotion_piece no
    es 'Q' (política "solo Dama" — ver M6_SPEC.md §2).
    """
    color = _mover_color(board_before)
    opponent = _OPPONENT[color]

    if move_result.is_castle:
        return _plan_castle(move_result, color)

    if move_result.is_en_passant:
        return _plan_en_passant(move_result, color, opponent)

    if move_result.is_promotion:
        return _plan_promotion(move_result, color, opponent)

    if move_result.is_capture:
        return _plan_capture(move_result, color, opponent)

    return _plan_normal_move(move_result, color)


def _plan_normal_move(move_result: MoveResult, color: Color) -> PhysicalPlan:
    return [
        PieceTransfer(
            origin=move_result.from_square,
            destination=move_result.to_square,
            piece=move_result.piece,
            color=color,
        )
    ]


def _plan_capture(
    move_result: MoveResult, color: Color, opponent: Color
) -> PhysicalPlan:
    captured_piece = move_result.captured_piece
    assert captured_piece is not None, "is_capture=True requiere captured_piece"
    return [
        PieceTransfer(
            origin=move_result.to_square,
            destination=_DISCARD_ZONE[opponent],
            piece=captured_piece,
            color=opponent,
        ),
        *_plan_normal_move(move_result, color),
    ]


def _plan_en_passant(
    move_result: MoveResult, color: Color, opponent: Color
) -> PhysicalPlan:
    ep_square = resolve_en_passant_captured_square(
        move_result.from_square, move_result.to_square
    )
    return [
        PieceTransfer(
            origin=ep_square,
            destination=_DISCARD_ZONE[opponent],
            piece="P",
            color=opponent,
        ),
        PieceTransfer(
            origin=move_result.from_square,
            destination=move_result.to_square,
            piece="P",
            color=color,
        ),
    ]


def _plan_castle(move_result: MoveResult, color: Color) -> PhysicalPlan:
    assert move_result.castle_side is not None, "is_castle=True requiere castle_side"
    rook_from, rook_to = resolve_castle_rook_squares(color, move_result.castle_side)
    return [
        PieceTransfer(
            origin=move_result.from_square,
            destination=move_result.to_square,
            piece="K",
            color=color,
        ),
        PieceTransfer(origin=rook_from, destination=rook_to, piece="R", color=color),
    ]


def _plan_promotion(
    move_result: MoveResult, color: Color, opponent: Color
) -> PhysicalPlan:
    if move_result.promotion_piece != "Q":
        raise UnsupportedPromotionError(move_result.promotion_piece)

    plan: PhysicalPlan = []

    if move_result.is_capture:
        captured_piece = move_result.captured_piece
        assert captured_piece is not None, "is_capture=True requiere captured_piece"
        plan.append(
            PieceTransfer(
                origin=move_result.to_square,
                destination=_DISCARD_ZONE[opponent],
                piece=captured_piece,
                color=opponent,
            )
        )

    # El peón nunca "pasa" por to_square en el plan físico: va directo a
    # descarte, evitando un transfer redundante (ver M6_SPEC.md §4.1).
    plan.append(
        PieceTransfer(
            origin=move_result.from_square,
            destination=_DISCARD_ZONE[color],
            piece="P",
            color=color,
        )
    )
    plan.append(
        PieceTransfer(
            origin=_SPARE_ZONE[color],
            destination=move_result.to_square,
            piece="Q",
            color=color,
        )
    )
    return plan
