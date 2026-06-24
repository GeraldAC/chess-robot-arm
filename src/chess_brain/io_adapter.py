"""Entrada / Salida - puente entre los contratos formales (types.py) y la
lógica interna de Estado del Juego (módulo 4) y Motor de Decision (módulo 5).

Entrada:  VisionInput -> chess.Move aplicado sobre el board.
Salida:   chess.Move ya aplicado -> MoveResult (listo para Planificación de Movimiento).

Aislar esta capa permite que, en el futuro, cambiar el formato de Visión o el
formato esperado por Movimiento no obligue a tocar game_state.py ni
decision_engine.py.
"""

from __future__ import annotations

import chess

from chess_brain.game_state import apply_human_move, get_game_status
from chess_brain.types import GameStatus, MoveResult, PieceType, VisionInput

_CHAR_FROM_PIECE_TYPE = {
    chess.PAWN: "P",
    chess.KNIGHT: "N",
    chess.BISHOP: "B",
    chess.ROOK: "R",
    chess.QUEEN: "Q",
    chess.KING: "K",
}


def parse_vision_input(vision_input: VisionInput, board: chess.Board) -> chess.Move:
    """Punto de entrada único del subsistema para el turno humano.

    Infiere y aplica sobre `board` el movimiento que produjo
    `vision_input.board_matrix`. Retorna el chess.Move aplicado.

    Nota: `vision_input.side_to_move` se acepta por contrato (Vision podría
    reportarlo en el futuro como verificación cruzada), pero la fuente de
    verdad del turno es siempre `board.turn`.
    """
    return apply_human_move(board, vision_input.board_matrix)


def build_move_result(
    board: chess.Board, move: chess.Move, board_before: chess.Board
) -> MoveResult:
    """Punto de salida único del subsistema.

    Inspecciona `move` (ya aplicado sobre `board`) junto con `board_before`
    (estado previo a aplicar el movimiento) para construir un MoveResult
    completo: capturas, enroque, captura al paso, promoción, estado final.

    `board_before` es necesario porque, una vez aplicado el movimiento,
    cierta información (ej. que pieza había en la casilla destino antes
    de la captura) ya no esta disponible directamente en `board`.
    """
    piece = board_before.piece_at(move.from_square)
    if piece is None:
        raise ValueError("No hay pieza en la casilla de origen del movimiento dado.")

    piece_char: PieceType = _CHAR_FROM_PIECE_TYPE[piece.piece_type]  # type: ignore[assignment]

    is_en_passant = board_before.is_en_passant(move)
    captured_piece_obj = board_before.piece_at(move.to_square)
    is_capture = board_before.is_capture(move)

    captured_piece: PieceType | None = None
    if is_en_passant:
        # En captura al paso, la pieza capturada NO esta en la casilla destino.
        captured_piece = "P"
    elif captured_piece_obj is not None:
        captured_piece = _CHAR_FROM_PIECE_TYPE[captured_piece_obj.piece_type]  # type: ignore[assignment]

    is_castle = board_before.is_castling(move)
    castle_side = None
    if is_castle:
        castle_side = (
            "kingside" if board_before.is_kingside_castling(move) else "queenside"
        )

    is_promotion = move.promotion is not None
    promotion_piece: PieceType | None = (
        _CHAR_FROM_PIECE_TYPE[move.promotion] if is_promotion else None  # type: ignore[index]
    )

    status: GameStatus = get_game_status(board)  # board YA tiene el movimiento aplicado

    return MoveResult(
        move_uci=move.uci(),
        from_square=chess.square_name(move.from_square),
        to_square=chess.square_name(move.to_square),
        piece=piece_char,
        is_capture=is_capture,
        captured_piece=captured_piece,
        is_castle=is_castle,
        castle_side=castle_side,
        is_en_passant=is_en_passant,
        is_promotion=is_promotion,
        promotion_piece=promotion_piece,
        resulting_fen=board.fen(),
        game_status=status,
    )
