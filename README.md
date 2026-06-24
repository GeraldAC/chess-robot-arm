# SPEC — Subsistema Estado del Juego (M4) + Motor de Decisión (M5)

## 1. Alcance

Este SPEC cubre los módulos **4 (Estado del Juego)** y **5 (Motor de Decisión)**, junto con dos módulos auxiliares de interfaz:

- **Entrada**: traduce la salida de Visión (matriz 8x8) en una jugada validada y un FEN actualizado.
- **Salida**: empaqueta la jugada elegida por el motor en un formato consumible por Planificación de Movimiento (M6).

Arquitectura: módulo Python importado por el orquestador (mismo proceso). Sin servicio HTTP/IPC.

## 2. Decisiones de diseño

| Decisión                        | Valor                                                                                                                |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Formato de entrada desde Visión | Matriz 8x8: lista de listas, valores `"wP"`, `"bN"`, `"bK"`, `None`, etc. (color + tipo de pieza, notación FEN-like) |
| Motor de ajedrez                | Stockfish vía UCI, usando `python-chess`                                                                             |
| Construcción del FEN            | Responsabilidad de este subsistema, no de Visión                                                                     |
| Arquitectura                    | Módulo Python importado, interfaz de funciones puras                                                                 |

## 3. Contrato de datos

### 3.1 Entrada al subsistema (desde Orquestador, originado en Visión)

```python
BoardMatrix = list[list[str | None]]  # 8x8, fila 0 = rank 8 (negras arriba), col 0 = columna 'a'

# Ejemplo de codificación de pieza: "{color}{tipo}"
# color: 'w' | 'b'
# tipo:  'P' 'N' 'B' 'R' 'Q' 'K'
```

```python
@dataclass
class VisionInput:
    board_matrix: BoardMatrix
    side_to_move: Literal["w", "b"]  # lo conoce el sistema, no la cámara
```

### 3.2 Salida del subsistema (hacia Planificación de Movimiento, M6)

```python
@dataclass
class MoveResult:
    move_uci: str              # ej. "e2e4"
    from_square: str           # "e2"
    to_square: str             # "e4"
    piece: str                 # "P", "N", "B", "R", "Q", "K"
    is_capture: bool
    captured_piece: str | None # tipo de pieza capturada, si aplica
    is_castle: bool
    castle_side: Literal["kingside", "queenside"] | None
    is_en_passant: bool
    is_promotion: bool
    promotion_piece: str | None  # "Q", "R", "B", "N"
    resulting_fen: str
    game_status: Literal["ongoing", "check", "checkmate", "stalemate", "draw"]
```

### 3.3 Errores esperados (no excepciones silenciosas)

```python
class IllegalStateError(Exception):
    """La matriz recibida no corresponde a ningún movimiento legal desde el estado anterior."""

class EngineError(Exception):
    """Stockfish no respondió o no está disponible."""
```

> **Por qué esto importa:** el módulo de Entrada es también el punto donde se detecta un fallo de Visión. Si `IllegalStateError` se lanza, el Orquestador debe pedir una nueva captura/clasificación, no continuar el flujo.

## 4. Diseño interno

### 4.1 Módulo `game_state.py` (M4 — Estado del Juego)

Responsabilidades:

1. Mantener el `chess.Board()` autoritativo (historial completo de la partida).
2. Recibir `BoardMatrix` y determinar qué movimiento legal del humano lo produjo.
3. Aplicar el movimiento al `Board` interno.
4. Determinar el estado resultante (jaque, mate, tablas, etc.).

Función pública principal:

```python
def infer_and_apply_human_move(
    board: chess.Board,
    new_matrix: BoardMatrix,
) -> chess.Move:
    """
    Compara el estado actual de `board` contra `new_matrix`.
    Recorre los movimientos legales desde `board` y encuentra cuál,
    al aplicarse, produce una matriz idéntica a `new_matrix`.
    Aplica ese movimiento sobre `board` (mutación) y lo retorna.

    Lanza IllegalStateError si ningún movimiento legal coincide.
    """
```

**Nota de implementación:** con `python-chess`, convertir `board.legal_moves` a matrices candidatas y comparar contra `new_matrix` es directo y suficientemente rápido (máximo ~40 movimientos legales en posiciones típicas).

### 4.2 Módulo `decision_engine.py` (M5 — Motor de Decisión)

Responsabilidades:

1. Inicializar y mantener el proceso de Stockfish (vía `chess.engine`).
2. Dado un `chess.Board`, solicitar la mejor jugada.
3. Aplicar esa jugada sobre el `Board` (turno del robot).

```python
def get_best_move(
    board: chess.Board,
    engine: chess.engine.SimpleEngine,
    think_time: float = 1.0,
) -> chess.Move:
    """
    Solicita a Stockfish la mejor jugada para `board.turn`.
    No aplica el movimiento (separación de responsabilidades: decidir != ejecutar).
    Lanza EngineError si el motor falla o no devuelve jugada.
    """
```

```python
def init_engine(stockfish_path: str) -> chess.engine.SimpleEngine:
    """Abre el proceso de Stockfish. Debe cerrarse con engine.quit() al finalizar."""
```

### 4.3 Módulo `io_adapter.py` (Entrada/Salida — capas amigables)

**Entrada:**

```python
def parse_vision_input(vision_input: VisionInput, board: chess.Board) -> chess.Move:
    """
    Punto de entrada único del subsistema.
    1. Llama a infer_and_apply_human_move(board, vision_input.board_matrix)
    2. Retorna el chess.Move aplicado (movimiento del humano)
    """
```

**Salida:**

```python
def build_move_result(board: chess.Board, move: chess.Move) -> MoveResult:
    """
    Punto de salida único del subsistema.
    Inspecciona `move` y el estado de `board` DESPUÉS de aplicado
    para construir un MoveResult completo (capturas, enroque, jaque mate, etc.)
    """
```

### 4.4 Flujo orquestado (pseudocódigo de alto nivel)

```python
# Turno del humano
human_move = parse_vision_input(vision_input, board)          # M4 + Entrada
# (opcional: reportar al log/UI qué jugó el humano)

if board.is_game_over():
    handle_game_over(board)
else:
    # Turno del robot
    robot_move = get_best_move(board, engine)                  # M5
    board.push(robot_move)
    result = build_move_result(board, robot_move)               # Salida
    send_to_movement_planning(result)                            # -> M6
```

## 5. Estructura del proyecto

```structure
chess-robot-arm/
├── pyproject.toml
├── README.md
├── .python-version
├── src/
│   └── chess_brain/
│       ├── __init__.py
│       ├── game_state.py        # M4
│       ├── decision_engine.py    # M5
│       ├── io_adapter.py         # Entrada / Salida
│       ├── types.py              # VisionInput, MoveResult, excepciones
│       └── engine_binaries/       # (gitignored) o ruta configurable a stockfish.exe
├── tests/
│   ├── test_game_state.py
│   ├── test_decision_engine.py
│   ├── test_io_adapter.py
│   └── fixtures/
│       └── boards.py              # matrices 8x8 de prueba (posiciones conocidas)
└── .gitignore
```

## 6. Setup del proyecto (Windows 11 + uv)

```powershell
# Crear proyecto
uv init chess-robot-arm
cd chess-robot-arm

# Dependencias
uv add chess

# Dependencias de desarrollo
uv add --dev pytest pytest-cov

# Stockfish: descargar binario para Windows desde https://stockfishchess.org/download/
# Colocar en una ruta conocida, ej: ./engine_binaries/stockfish.exe
# (NO se instala vía uv/pip — es un binario nativo)
```

`pyproject.toml` — fragmento relevante:

```toml
[project]
name = "chess-robot-arm"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "chess>=1.11.2",
]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
]
```

Verificación rápida de Stockfish:

```powershell
uv run python -c "
import chess.engine
engine = chess.engine.SimpleEngine.popen_uci('./src/chess_brain/engine_binaries/stockfish.exe')
print(engine.id)
engine.quit()
"
```

Ejecución de test y main:

```powershell
uv run poe chess-test

uv run chess-brain --stockfish-path "./src/chess_brain/engine_binaries/stockfish.exe" --human-color white --think-time 1.0

```

## 7. Plan de pruebas

### 7.1 `test_game_state.py`

| Caso                                               | Verifica                                                                                                  |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Movimiento simple válido (peón)                    | Matriz tras `e2e4` → se infiere correctamente                                                             |
| Captura                                            | Matriz tras captura → `infer_and_apply_human_move` la detecta                                             |
| Enroque corto/largo                                | Matriz con rey y torre movidos simultáneamente → se infiere como enroque, no como dos movimientos sueltos |
| Captura al paso                                    | Caso especial, matriz con peón capturado fuera de la casilla destino                                      |
| Promoción                                          | Peón llega a última fila con pieza distinta → se infiere tipo de promoción                                |
| Matriz inválida (ningún movimiento legal coincide) | Se lanza `IllegalStateError`                                                                              |
| Jaque mate                                         | `board.is_checkmate()` tras aplicar movimiento → estado correcto                                          |

### 7.2 `test_decision_engine.py`

| Caso                                  | Verifica                                   |
| ------------------------------------- | ------------------------------------------ |
| Posición inicial                      | El motor retorna una jugada legal          |
| Mate en 1 disponible                  | El motor encuentra el mate                 |
| `think_time` configurable             | El tiempo de cómputo respeta el parámetro  |
| Motor no disponible (ruta incorrecta) | Se lanza `EngineError`                     |
| Cierre limpio del motor               | `engine.quit()` no deja procesos huérfanos |

### 7.3 `test_io_adapter.py`

| Caso                                              | Verifica                                                                                                     |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `parse_vision_input` con matriz válida            | Retorna `chess.Move` correcto                                                                                |
| `build_move_result` para jugada normal            | Todos los campos de `MoveResult` correctos, flags de captura/enroque/promoción en `False`/`None`             |
| `build_move_result` para captura                  | `is_capture=True`, `captured_piece` correcto                                                                 |
| `build_move_result` para enroque                  | `is_castle=True`, `castle_side` correcto                                                                     |
| `build_move_result` para jaque mate               | `game_status="checkmate"`                                                                                    |
| Integración M4→M5→Salida con `fixtures/boards.py` | Flujo completo desde matriz de entrada hasta `MoveResult` de salida, usando 3-4 posiciones reales de partida |

### 7.4 Fixtures (`fixtures/boards.py`)

Definir matrices 8x8 conocidas (posición inicial, posición a mitad de partida, posición con jaque mate en 1) para reutilizar en todos los tests sin repetir literales.

## 8. Pendiente para fases siguientes (fuera de este SPEC)

- Definir cómo Orquestador obtiene `side_to_move` cuando aún no hay historial (primer movimiento de la partida).
- Manejo de desincronización si Verificación (M9) detecta que el movimiento físico no coincide con `MoveResult`.
- Configuración de `think_time` / nivel de dificultad de Stockfish como parámetro de usuario.
