# SPEC — chess_planner: Planificación de Movimiento (M6)

## 1. Alcance

Este documento cubre:

- **`movement_types.py`** (contratos internos de `chess_planner`)
- **`movement_planner.py`** (M6 — Planificación de Movimiento)
- **`__init__.py`** (superficie pública del paquete)

Arquitectura: módulo Python (`chess_planner`) importado por el orquestador,
mismo proceso, mismo criterio YAGNI que `chess_brain` y `chess_vision`.
`chess_planner` depende de `chess_brain.brain_types` (`MoveResult`) y de
`python-chess` (`chess.Board`, `chess.Move`) — dependencia unidireccional,
sin importar nada de `chess_vision`.

**Aclaración de alcance crítica (no explícita en ningún documento previo):**
M6 planifica **únicamente las jugadas originadas por el motor** (la
respuesta de Stockfish, ejecutada por el brazo). Las jugadas del humano
ya se ejecutaron físicamente con su propia mano al momento en que Visión
las detecta — M4 solo necesita _inferirlas y validarlas_ sobre el
`chess.Board`, no planificar ninguna acción física para ellas. `MoveResult`
se genera para ambos turnos en M4-5 (para poder mostrarlas en consola vía
`display.py`), pero el Orquestador (M10) solo debe invocar `plan_move`
sobre el `MoveResult` correspondiente al turno del motor.

## 2. Decisiones de diseño

| Decisión                            | Valor                                                                                                                                                                                        |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alcance de planificación            | Solo jugadas del motor (robot). Jugadas humanas: sin acción física, ya ejecutadas por el humano                                                                                              |
| Unidad de acción física             | `PieceTransfer(origin, destination, piece, color)` — un único tipo, uniforme para movimiento normal, captura, enroque, captura al paso y promoción                                           |
| Descarte de piezas capturadas       | 2 zonas físicas fijas, una por color (`DISCARD_WHITE`, `DISCARD_BLACK`) — tipo bandeja/contenedor, la pieza se suelta, sin necesidad de slots individuales ni de trackear ocupación          |
| Promoción física                    | Política **"solo Dama"**: se asume repuesto físico de Dama por color (`SPARE_WHITE`, `SPARE_BLACK`). Subpromoción (T/A/C) no soportada en v1 → `UnsupportedPromotionError`                   |
| Nuevo requisito de hardware         | 4 zonas físicas nuevas (`DISCARD_WHITE/BLACK`, `SPARE_WHITE/BLACK`), no contempladas en `BOM.md` §5 — actualizar BOM y resolver sus coordenadas reales en M0 (Calibración)                   |
| Entrada de `plan_move`              | `MoveResult` **+** `board_before: chess.Board` (no alcanza con `MoveResult` solo) — se usa para derivar el color de quien movió (`board_before.turn`) y la casilla capturada al paso         |
| Orden de sub-movimientos en enroque | Rey primero, luego torre. Convención arbitraria pero determinística — el orden fino de trayectoria/colisión es responsabilidad de M7/M8, no de M6                                            |
| Mutua exclusión de categorías       | `is_castle`, `is_en_passant`, `is_promotion` son mutuamente excluyentes por reglas de ajedrez; `is_capture` puede combinarse con `is_en_passant` o con promoción, pero nunca con `is_castle` |
| Nivel de abstracción de la salida   | Casillas/zonas simbólicas (`Location = str`), NO coordenadas cartesianas — esa traducción es responsabilidad de M7, que a su vez depende del mapeo de M0                                     |
| Inventario de piezas de repuesto    | No gestionado por software en v1 (ver §7, Pendiente)                                                                                                                                         |
| Arquitectura                        | Módulo Python importado, funciones puras — mismo patrón que `game_state.py` (M4)                                                                                                             |

## 3. Contrato de datos

### 3.1 Tipos base

```python
Location = str
# Casilla algebraica ("e2".."h8") o uno de los valores de Zone.
# La resolución de Location -> coordenada cartesiana es responsabilidad de M7 (vía M0).

class Zone(str, Enum):
    DISCARD_WHITE = "DISCARD_WHITE"   # piezas blancas retiradas del tablero (capturadas o promovidas)
    DISCARD_BLACK = "DISCARD_BLACK"   # piezas negras retiradas del tablero
    SPARE_WHITE = "SPARE_WHITE"       # reserva de Dama blanca para promoción
    SPARE_BLACK = "SPARE_BLACK"       # reserva de Dama negra para promoción

@dataclass(frozen=True)
class PieceTransfer:
    """Una única acción física: mover una pieza de `origin` a
    `destination`. Ambos pueden ser una casilla del tablero o una Zone."""
    origin: Location
    destination: Location
    piece: Literal["P", "N", "B", "R", "Q", "K"]
    color: Literal["w", "b"]

PhysicalPlan = list[PieceTransfer]
# Secuencia ORDENADA de transferencias. El orden importa: debe ejecutarse
# tal cual, en ese orden, para que el tablero físico llegue al estado
# correcto (ej. remover la pieza capturada antes de ocupar su casilla).
```

### 3.2 Errores

```python
class UnsupportedPromotionError(Exception):
    """move_result.promotion_piece no es 'Q'. No hay pieza de repuesto
    física contemplada para T/A/C en v1 (ver §2, política de promoción)."""
```

## 4. Diseño interno

### 4.1 `movement_planner.py`

```python
def resolve_en_passant_captured_square(from_square: str, to_square: str) -> str:
    """Casilla real del peón capturado al paso: mismo file que
    `to_square`, mismo rank que `from_square`. No confundir con
    `to_square` (que es donde aterriza el peón que captura, no donde
    estaba el peón capturado)."""

def resolve_castle_rook_squares(
    color: Literal["w", "b"],
    castle_side: Literal["kingside", "queenside"],
) -> tuple[str, str]:
    """Tabla fija de 4 casos (color x lado) -> (rook_from, rook_to).
    Blancas kingside: h1->f1. Blancas queenside: a1->d1.
    Negras kingside: h8->f8. Negras queenside: a8->d8."""

def plan_move(move_result: MoveResult, board_before: chess.Board) -> PhysicalPlan:
    """Punto de entrada único. mover_color = 'w' si board_before.turn es
    True, si no 'b'. Bifurca sobre move_result (categorías mutuamente
    excluyentes, ver §2):

    - is_castle: [PieceTransfer(king_from, king_to, 'K', color),
                  PieceTransfer(*resolve_castle_rook_squares(...), 'R', color)]
    - is_en_passant: [PieceTransfer(ep_square, DISCARD[oponente], 'P', oponente),
                      PieceTransfer(from_square, to_square, 'P', color)]
    - is_capture (no e.p.): [PieceTransfer(to_square, DISCARD[oponente],
                             captured_piece, oponente), <transfer principal>]
    - is_promotion: <transfers de captura si aplica> +
                    [PieceTransfer(from_square, DISCARD[color], 'P', color),
                     PieceTransfer(SPARE[color], to_square, promotion_piece, color)]
                    Si promotion_piece != 'Q' -> UnsupportedPromotionError.
                    Nota: el peón nunca "pasa" por to_square en el plan —
                    va directo a descarte, evitando un transfer redundante.
    - caso normal: [PieceTransfer(from_square, to_square, piece, color)]
    """
```

### 4.2 `__init__.py` — Superficie pública

```python
from chess_planner.movement_planner import plan_move
from chess_planner.movement_types import (
    PieceTransfer, PhysicalPlan, Zone, UnsupportedPromotionError,
)
```

Igual que en `chess_brain` y `chess_vision`, este es el único contrato
que un futuro Orquestador (M10) o M7 deberían asumir estable.

## 5. Estructura del proyecto

```structure
chess-robot-arm/
├── src/
│   ├── chess_brain/                   # M4-5 (implementado)
│   ├── chess_vision/                  # M2-3 (implementado)
│   └── chess_planner/                 # M6 (a implementar)
│       ├── __init__.py
│       ├── M6_SPEC.md
│       ├── movement_types.py           # PieceTransfer, Zone, PhysicalPlan, UnsupportedPromotionError
│       └── movement_planner.py         # plan_move y helpers
└── tests/
    ├── test_brain/
    ├── test_vision/
    └── test_planner/
        ├── __init__.py
        ├── test_movement_planner.py
        └── fixtures/
            ├── __init__.py
            └── move_results.py         # MoveResult + board_before de prueba por cada categoría
```

No se requieren dependencias nuevas (`chess_planner` solo usa `python-chess`,
ya presente en el proyecto).

## 6. Plan de pruebas

### 6.1 `test_movement_planner.py`

| Caso                                          | Verifica                                                                           |
| --------------------------------------------- | ---------------------------------------------------------------------------------- |
| Movimiento normal (sin captura)               | 1 solo `PieceTransfer`, origen/destino/color correctos                             |
| Captura simple                                | 2 transfers, en orden: remover capturada a `DISCARD[oponente]`, luego el principal |
| Captura al paso                               | `resolve_en_passant_captured_square` calcula la casilla correcta (≠ `to_square`)   |
| Enroque corto, blancas y negras               | 2 transfers, orden rey→torre, casillas correctas                                   |
| Enroque largo, blancas y negras               | Idem, con casillas de enroque largo                                                |
| Promoción a Dama, sin captura                 | 2 transfers: peón a `DISCARD[color]`, luego `SPARE[color]` a destino               |
| Promoción a Dama, con captura                 | 3 transfers, orden correcto (remover capturada, retirar peón, colocar dama)        |
| Subpromoción (T/A/C)                          | Lanza `UnsupportedPromotionError`                                                  |
| `mover_color` derivado de `board_before.turn` | Coincide con el color real de la pieza que se movió, en ambos colores              |

## 7. Pendiente (fuera de alcance de este SPEC)

- Inventario físico de piezas de repuesto: cuántas quedan disponibles en
  `SPARE_WHITE`/`SPARE_BLACK` y cuándo reponerlas manualmente — no
  gestionado por software en v1.
- Actualizar `BOM.md` §5 con las 4 zonas físicas nuevas (2 bandejas de
  descarte + 2 reservas de Dama).
- Definir las coordenadas reales de esas 4 zonas — corresponde a M0
  (Calibración), fuera de alcance de este documento.
- Contrato M6→M7: `PhysicalPlan` (secuencia de `PieceTransfer`) es la
  propuesta de este SPEC; M7 debe resolver cada `Location` (casilla o
  `Zone`) a coordenadas cartesianas.
- Trayectoria fina (altura de aproximación, evitar colisión con otras
  piezas al pasar por encima del tablero) — responsabilidad de M7/M8.
- Tablas/empate (`game_status` en `stalemate`/`draw`): sin acción física
  que planificar, fuera de alcance de M6.
