"""CLI interactiva - producto funcional standalone de los módulos 4 (Estado
del Juego) y 5 (Motor de Decision).

Permite jugar una partida completa contra Stockfish desde la terminal,
visualizando el tablero en ASCII, sin depender de Vision ni del brazo físico.
Sirve como banco de pruebas end-to-end del contrato VisionInput -> MoveResult.

Uso:
    uv run chess-brain --stockfish-path /ruta/a/stockfish
    uv run chess-brain --stockfish-path /ruta/a/stockfish --human-color black
    uv run chess-brain --stockfish-path /ruta/a/stockfish --think-time 2.0
    uv run chess-brain --stockfish-path "./src/chess_brain/engine_binaries/stockfish.exe" --human-color white --think-time 1.0

Comandos dentro de la partida:
    e2e4        Jugar el movimiento UCI indicado (entrada rápida).
    matrix      Entrar en modo matriz manual (simula entrada cruda de Vision).
    random      Simula una jugada legal aleatoria reportada por Vision.
    board       Reimprimir el tablero actual.
    fen         Mostrar el FEN actual.
    quit        Salir.
"""

from __future__ import annotations

import argparse
import random
import sys

import chess

from chess_brain.brain_types import BoardMatrix
from chess_brain.decision_engine import EngineError, get_best_move, init_engine
from chess_brain.display import render_board, render_move_result
from chess_brain.game_state import IllegalStateError, get_game_status
from chess_brain.io_adapter import build_move_result, parse_vision_input
from chess_brain.vision_stub import vision_input_from_matrix, vision_input_from_move

_VALID_PIECE_CODES = {f"{color}{kind}" for color in "wb" for kind in "PNBRQK"} | {""}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CLI de prueba para Estado del Juego (M4) + Motor de Decision (M5).",
    )
    parser.add_argument(
        "--stockfish-path",
        default="./src/chess_brain/engine_binaries/stockfish.exe",
        help="Ruta al binario de Stockfish (ej. C:\\stockfish\\stockfish.exe en Windows).",
    )
    parser.add_argument(
        "--human-color",
        choices=["white", "black"],
        default="white",
        help="Color que jugara el humano. El robot/motor juega el color contrario. (default: white)",
    )
    parser.add_argument(
        "--think-time",
        type=float,
        default=1.0,
        help="Segundos que Stockfish piensa por jugada. (default: 1.0)",
    )
    return parser.parse_args(argv)


def _read_manual_matrix() -> BoardMatrix:
    """Modo manual: pide al usuario las 8 filas, casilla por casilla, separadas por coma.

    Formato esperado por fila (de rank 8 a rank 1): wR,wN,wB,wQ,wK,wB,wN,wR
    Casilla vacía: deja el campo vacío (",," produce None entre comas).
    """
    print(
        "\nModo matriz manual. Ingresa 8 filas (rank 8 -> rank 1), 8 valores separados por coma."
    )
    print("Códigos validos: wP wN wB wR wQ wK / bP bN bB bR bQ bK / vacío = sin pieza.")
    print("Ejemplo fila inicial negras: bR,bN,bB,bQ,bK,bB,bN,bR\n")

    matrix: BoardMatrix = []
    for rank_label in range(8, 0, -1):
        while True:
            raw = input(f"Fila (rank {rank_label}): ").strip()
            cells = [c.strip() for c in raw.split(",")]
            if len(cells) != 8:
                print(
                    f"  Error: se esperaban 8 valores separados por coma, llegaron {len(cells)}."
                )
                continue
            if not all(c in _VALID_PIECE_CODES for c in cells):
                invalid = [c for c in cells if c not in _VALID_PIECE_CODES]
                print(f"  Error: códigos inválidos: {invalid}")
                continue
            matrix.append([c if c else None for c in cells])
            break
    return matrix


def _human_turn_uci(board: chess.Board) -> tuple[chess.Move, chess.Board] | None:
    """Lee un comando o movimiento UCI por teclado y lo aplica via el contrato VisionInput.

    Retorna (movimiento aplicado, tablero previo al movimiento), o None si
    el usuario pidió salir. Los comandos 'board' y 'fen' reimprimen
    información sin consumir el turno.
    """
    while True:
        raw = (
            input(
                "\nTu jugada (UCI, ej. e2e4) o 'matrix'/'random'/'board'/'fen'/'quit': "
            )
            .strip()
            .lower()
        )

        if raw == "quit":
            return None

        if raw == "board":
            print("\n" + render_board(board))
            continue

        if raw == "fen":
            print(f"FEN actual: {board.fen()}")
            continue

        if raw == "matrix":
            matrix = _read_manual_matrix()
            side_to_move = "w" if board.turn == chess.WHITE else "b"
            vision_input = vision_input_from_matrix(matrix, side_to_move)
        elif raw == "random":
            move = random.choice(list(board.legal_moves))
            print(f"  (Vision simulado reporta la jugada aleatoria: {move.uci()})")
            vision_input = vision_input_from_move(board, move)
        else:
            try:
                move = chess.Move.from_uci(raw)
            except ValueError:
                print(
                    "  Formato invalido. Usa notación UCI, ej. e2e4 (o e7e8q para promoción)."
                )
                continue
            if move not in board.legal_moves:
                print("  Esa jugada no es legal en la posición actual.")
                continue
            vision_input = vision_input_from_move(board, move)

        board_before = board.copy()
        try:
            applied_move = parse_vision_input(vision_input, board)
        except IllegalStateError as exc:
            print(f"  [IllegalStateError] {exc}")
            print(
                "  (Esto simula un fallo de Vision: la matriz no coincide con ninguna jugada legal.)"
            )
            continue

        return applied_move, board_before


def run() -> int:
    args = _parse_args(sys.argv[1:])

    try:
        engine = init_engine(args.stockfish_path)
    except EngineError as exc:
        print(f"Error al iniciar el motor: {exc}")
        return 1

    board = chess.Board()
    human_is_white = args.human_color == "white"
    human_label = "Humano"
    robot_label = "Robot"

    print(render_board(board))
    print(f"\nJuegas como {'blancas' if human_is_white else 'negras'}.")

    try:
        while not board.is_game_over():
            human_turn_now = (board.turn == chess.WHITE) == human_is_white

            if human_turn_now:
                outcome = _human_turn_uci(board)
                if outcome is None:
                    print("\nPartida interrumpida por el usuario.")
                    break
                applied_move, board_before = outcome
                result = build_move_result(board, applied_move, board_before)
                print("\n" + render_board(board))
                print(render_move_result(result, human_label))
            else:
                print(f"\n{robot_label} esta pensando...")
                board_before = board.copy()
                try:
                    robot_move = get_best_move(
                        board, engine, think_time=args.think_time
                    )
                except EngineError as exc:
                    print(f"  [EngineError] {exc}")
                    break
                board.push(robot_move)
                result = build_move_result(board, robot_move, board_before)
                print("\n" + render_board(board))
                print(render_move_result(result, robot_label))

        if board.is_game_over():
            print(
                f"\nPartida terminada. Estado final: {get_game_status(board)}. FEN: {board.fen()}"
            )

    finally:
        engine.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
