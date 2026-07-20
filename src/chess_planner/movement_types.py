"""Contratos internos de chess_planner (M6 — Planificación de Movimiento).

Ver M6_SPEC.md §3 para el detalle completo del diseño.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

PieceType = Literal["P", "N", "B", "R", "Q", "K"]
Color = Literal["w", "b"]


class Zone(str, Enum):
    """Zonas físicas simbólicas fuera del tablero.

    La resolución de cada Zone a una coordenada cartesiana real es
    responsabilidad de M7 (Cinemática Inversa), vía el mapeo de M0
    (Calibración) — chess_planner nunca conoce coordenadas.
    """

    DISCARD_WHITE = "DISCARD_WHITE"  # piezas blancas retiradas del tablero
    DISCARD_BLACK = "DISCARD_BLACK"  # piezas negras retiradas del tablero
    SPARE_WHITE = "SPARE_WHITE"  # reserva de Dama blanca para promoción
    SPARE_BLACK = "SPARE_BLACK"  # reserva de Dama negra para promoción


Location = str
"""Casilla algebraica ("e2".."h8") o uno de los valores de `Zone`."""


@dataclass(frozen=True)
class PieceTransfer:
    """Una única acción física: mover una pieza de `origin` a
    `destination`. Ambos pueden ser una casilla del tablero o un valor
    de `Zone`. `color` es el color de la pieza que se transfiere (para
    capturas, es el color del OPONENTE de quien mueve — la pieza
    retirada es suya, no la del que captura)."""

    origin: Location
    destination: Location
    piece: PieceType
    color: Color


PhysicalPlan = list[PieceTransfer]
"""Secuencia ORDENADA de transferencias. El orden importa: debe
ejecutarse tal cual para que el tablero físico llegue al estado
correcto (ej. remover la pieza capturada antes de ocupar su casilla)."""


class UnsupportedPromotionError(Exception):
    """El MoveResult pide promoción a una pieza distinta de Dama. No hay
    pieza de repuesto física contemplada para T/A/C en v1 (ver
    M6_SPEC.md §2, política de promoción "solo Dama")."""

    def __init__(self, promotion_piece: str | None):
        self.promotion_piece = promotion_piece
        super().__init__(
            f"Promoción a {promotion_piece!r} no soportada en v1 "
            "(solo se admite promoción a Dama, 'Q')."
        )
