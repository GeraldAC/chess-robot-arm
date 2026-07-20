"""Tests de chess_planner (M6) según el plan de pruebas de M6_SPEC.md §6.1."""

from __future__ import annotations

import pytest

from chess_planner.movement_planner import (
    plan_move,
    resolve_castle_rook_squares,
    resolve_en_passant_captured_square,
)
from chess_planner.movement_types import PieceTransfer, UnsupportedPromotionError, Zone
from test_planner.fixtures import move_results as fx


def test_normal_move_produces_single_transfer():
    board_before, move_result = fx.normal_move()
    plan = plan_move(move_result, board_before)

    assert plan == [PieceTransfer(origin="e2", destination="e4", piece="P", color="w")]


def test_simple_capture_removes_captured_piece_first():
    board_before, move_result = fx.simple_capture()
    plan = plan_move(move_result, board_before)

    assert plan == [
        PieceTransfer(
            origin="d5", destination=Zone.DISCARD_BLACK, piece="P", color="b"
        ),
        PieceTransfer(origin="e4", destination="d5", piece="P", color="w"),
    ]


def test_en_passant_captured_square_is_not_to_square():
    ep_square = resolve_en_passant_captured_square("e5", "f6")
    assert ep_square == "f5"
    assert ep_square != "f6"


def test_en_passant_capture_plan():
    board_before, move_result = fx.en_passant_capture()
    plan = plan_move(move_result, board_before)

    assert plan == [
        PieceTransfer(
            origin="f5", destination=Zone.DISCARD_BLACK, piece="P", color="b"
        ),
        PieceTransfer(origin="e5", destination="f6", piece="P", color="w"),
    ]


@pytest.mark.parametrize(
    "color,side,expected",
    [
        ("w", "kingside", ("h1", "f1")),
        ("w", "queenside", ("a1", "d1")),
        ("b", "kingside", ("h8", "f8")),
        ("b", "queenside", ("a8", "d8")),
    ],
)
def test_resolve_castle_rook_squares(color, side, expected):
    assert resolve_castle_rook_squares(color, side) == expected


def test_castle_kingside_white_moves_king_then_rook():
    board_before, move_result = fx.castle_kingside_white()
    plan = plan_move(move_result, board_before)

    assert plan == [
        PieceTransfer(origin="e1", destination="g1", piece="K", color="w"),
        PieceTransfer(origin="h1", destination="f1", piece="R", color="w"),
    ]


def test_castle_queenside_black_moves_king_then_rook():
    board_before, move_result = fx.castle_queenside_black()
    plan = plan_move(move_result, board_before)

    assert plan == [
        PieceTransfer(origin="e8", destination="c8", piece="K", color="b"),
        PieceTransfer(origin="a8", destination="d8", piece="R", color="b"),
    ]


def test_promotion_no_capture_plan():
    board_before, move_result = fx.promotion_no_capture()
    plan = plan_move(move_result, board_before)

    assert plan == [
        PieceTransfer(
            origin="e7", destination=Zone.DISCARD_WHITE, piece="P", color="w"
        ),
        PieceTransfer(origin=Zone.SPARE_WHITE, destination="e8", piece="Q", color="w"),
    ]


def test_promotion_with_capture_plan_order():
    board_before, move_result = fx.promotion_with_capture()
    plan = plan_move(move_result, board_before)

    assert plan == [
        PieceTransfer(
            origin="d8", destination=Zone.DISCARD_BLACK, piece="R", color="b"
        ),
        PieceTransfer(
            origin="e7", destination=Zone.DISCARD_WHITE, piece="P", color="w"
        ),
        PieceTransfer(origin=Zone.SPARE_WHITE, destination="d8", piece="Q", color="w"),
    ]


def test_underpromotion_raises_unsupported_promotion_error():
    board_before, move_result = fx.underpromotion_unsupported()

    with pytest.raises(UnsupportedPromotionError):
        plan_move(move_result, board_before)


def test_mover_color_derived_from_board_before_turn_white():
    board_before, move_result = fx.normal_move()
    plan = plan_move(move_result, board_before)
    assert plan[0].color == "w"


def test_mover_color_derived_from_board_before_turn_black():
    board_before, move_result = fx.castle_queenside_black()
    plan = plan_move(move_result, board_before)
    assert all(transfer.color == "b" for transfer in plan)
