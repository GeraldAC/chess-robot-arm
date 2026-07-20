"""Superficie pública de chess_planner (M6 — Planificación de Movimiento).

Único contrato que un futuro Orquestador (M10) o M7 (Cinemática Inversa)
deberían asumir estable. El resto de funciones/módulos internos puede
cambiar sin romper integración — ver M6_SPEC.md §4.
"""

from chess_planner.movement_planner import plan_move
from chess_planner.movement_types import (
    PhysicalPlan,
    PieceTransfer,
    UnsupportedPromotionError,
    Zone,
)

__all__ = [
    "plan_move",
    "PieceTransfer",
    "PhysicalPlan",
    "Zone",
    "UnsupportedPromotionError",
]
