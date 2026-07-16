# SPEC — chess_brain: Estado del Juego (M4) + Motor de Decisión (M5)

## 1. Alcance

Este SPEC cubre:

- **`game_state.py`** (M4 — Estado del Juego)
- **`decision_engine.py`** (M5 — Motor de Decisión)
- **`io_adapter.py`** (Entrada / Salida del subsistema)
- **`vision_stub.py`** (simulador de Visión)
- **`display.py`** (presentación en consola)
- **`main.py`** (CLI de producto funcional)
- **`__init__.py`** (superficie pública del paquete)

Arquitectura: módulo Python (`chess_brain`) importado por el orquestador,
mismo proceso. Sin servicio HTTP/IPC.

## 2. Decisiones de diseño

| Decisión                        | Valor                                                                                                                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Formato de entrada desde Visión | Matriz 8x8: lista de listas, valores `"wP"`, `"bN"`, `"bK"`, `None`, etc.                                                                                                                         |
| Motor de ajedrez                | Stockfish vía UCI, usando `python-chess`                                                                                                                                                          |
| Construcción del FEN            | Responsabilidad de este subsistema, no de Visión                                                                                                                                                  |
| Arquitectura                    | Módulo Python importado, funciones puras + un `chess.Board` mutable pasado explícitamente                                                                                                         |
| Superficie pública              | `__init__.py` expone solo `get_best_move`, `init_engine`, `build_move_result`, `parse_vision_input`, `MoveResult`, `VisionInput`, `EngineError`, `IllegalStateError`. El resto es detalle interno |

## 3. Contrato de datos

### 3.1 Entrada al subsistema

```python
BoardMatrix = list[list[str | None]]  # 8x8, fila 0 = rank 8, col 0 = 'a'

@dataclass(frozen=True)
class VisionInput:
    board_matrix: BoardMatrix
    side_to_move: Literal["w", "b"]
```

### 3.2 Salida del subsistema

```python
@dataclass(frozen=True)
class MoveResult:
    move_uci: str
    from_square: str
    to_square: str
    piece: Literal["P", "N", "B", "R", "Q", "K"]
    is_capture: bool
    captured_piece: Literal["P", "N", "B", "R", "Q", "K"] | None
    is_castle: bool
    castle_side: Literal["kingside", "queenside"] | None
    is_en_passant: bool
    is_promotion: bool
    promotion_piece: Literal["Q", "R", "B", "N"] | None
    resulting_fen: str
    game_status: Literal["ongoing", "check", "checkmate", "stalemate", "draw"]
```

### 3.3 Errores

```python
class IllegalStateError(Exception):
    """La matriz recibida no corresponde a ningún movimiento legal desde el estado anterior."""

class EngineError(Exception):
    """Stockfish no respondió, no está disponible, o no devolvió una jugada válida."""
```

## 4. Diseño interno

### 4.1 `game_state.py` (M4 — Estado del Juego)

```python
def board_to_matrix(board: chess.Board) -> BoardMatrix:
    """Convierte un chess.Board a BoardMatrix. Usada para comparar contra
    lo que Vision reporta, y para generar matrices de prueba."""

def matrices_equal(a: BoardMatrix, b: BoardMatrix) -> bool:
    """Comparación estricta de dos matrices 8x8."""

def infer_human_move(board: chess.Board, new_matrix: BoardMatrix) -> chess.Move:
    """Recorre board.legal_moves, simula cada uno sobre una copia, y
    retorna el que produce new_matrix. No muta `board`.
    Lanza IllegalStateError si ninguno coincide."""

def apply_human_move(board: chess.Board, new_matrix: BoardMatrix) -> chess.Move:
    """Llama a infer_human_move y aplica el resultado sobre `board`
    (mutación). Retorna el Move aplicado."""

def get_game_status(board: chess.Board) -> str:
    """Estado DESPUÉS de aplicar un movimiento. Orden de evaluación:
    checkmate > (stalemate | insufficient_material | can_claim_draw,
    distinguiendo 'stalemate' de 'draw') > check > ongoing."""
```

### 4.2 `decision_engine.py` (M5 — Motor de Decisión)

```python
def init_engine(stockfish_path: str) -> chess.engine.SimpleEngine:
    """Abre el proceso de Stockfish. Lanza EngineError si el binario no
    existe (FileNotFoundError) o si falla el arranque por cualquier otra
    razón. Debe cerrarse con engine.quit()."""

def get_best_move(
    board: chess.Board,
    engine: chess.engine.SimpleEngine,
    think_time: float = 1.0,
) -> chess.Move:
    """Solicita a Stockfish la mejor jugada para board.turn. No aplica el
    movimiento. Lanza EngineError si el motor falla o no devuelve jugada."""
```

### 4.3 `io_adapter.py` (Entrada / Salida)

```python
def parse_vision_input(vision_input: VisionInput, board: chess.Board) -> chess.Move:
    """Punto de entrada único. Llama a apply_human_move(board,
    vision_input.board_matrix). vision_input.side_to_move se acepta por
    contrato pero NO es la fuente de verdad del turno (eso es board.turn)."""

def build_move_result(
    board: chess.Board,
    move: chess.Move,
    board_before: chess.Board,
) -> MoveResult:
    """Punto de salida único. Inspecciona `move` (ya aplicado sobre
    `board`) junto con `board_before` (estado previo) para construir un
    MoveResult completo: capturas, enroque, captura al paso, promoción,
    estado final. `board_before` es necesario porque, una vez aplicado el
    movimiento, cierta información (ej. qué pieza había en la casilla
    destino) ya no está disponible directamente en `board`."""
```

### 4.4 `vision_stub.py` — simulador de Visión

```python
def vision_input_from_move(board: chess.Board, move: chess.Move) -> VisionInput:
    """Simula lo que Vision 'fotografiaría' tras jugar `move`. No muta
    `board`: aplica sobre una copia y reporta la matriz resultante."""

def vision_input_from_matrix(matrix: BoardMatrix, side_to_move: str) -> VisionInput:
    """Construye un VisionInput directamente desde una matriz dada a mano
    (para simular errores de clasificación o posiciones de prueba)."""
```

### 4.5 `display.py` — presentación en consola

```python
def render_board(board: chess.Board) -> str:
    """Tablero ASCII/Unicode con coordenadas, vista desde blancas."""

def render_move_result(result: MoveResult, mover_label: str) -> str:
    """Resumen legible de un MoveResult (movimiento, captura, enroque,
    promoción, jaque/mate/tablas)."""
```

### 4.6 `main.py` — CLI de producto funcional

Producto standalone que permite jugar una partida completa contra
Stockfish desde terminal, sin depender de Visión ni del brazo físico.

**Argumentos:**

| Argumento          | Requerido | Default | Descripción                                 |
| ------------------ | --------- | ------- | ------------------------------------------- |
| `--stockfish-path` | Sí        | —       | Ruta al binario de Stockfish                |
| `--human-color`    | No        | `white` | Color del humano (`white`/`black`)          |
| `--think-time`     | No        | `1.0`   | Segundos de cómputo de Stockfish por jugada |

**Comandos dentro de la partida (`_human_turn_uci`):**

| Comando                     | Comportamiento                                                                                                                          |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `e2e4` (UCI válido y legal) | Juega el movimiento vía `vision_input_from_move`                                                                                        |
| `matrix`                    | Modo de matriz manual (`_read_manual_matrix`): 8 filas de 8 valores separados por coma, simulando entrada cruda de Vision               |
| `random`                    | Elige una jugada legal al azar y la reporta como si Vision la hubiera detectado — util para probar el flujo sin escribir jugadas a mano |
| `board`                     | Reimprime el tablero actual (no consume el turno)                                                                                       |
| `fen`                       | Muestra el FEN actual (no consume el turno)                                                                                             |
| `quit`                      | Sale de la partida                                                                                                                      |

`_human_turn_uci` retorna `tuple[chess.Move, chess.Board] | None`: el
movimiento aplicado junto con el tablero previo a aplicarlo (necesario
para `build_move_result`), o `None` si el usuario salió.

### 4.7 `__init__.py` — Superficie pública

```python
from chess_brain.decision_engine import get_best_move, init_engine
from chess_brain.io_adapter import build_move_result, parse_vision_input
from chess_brain.brain_types import EngineError, IllegalStateError, MoveResult, VisionInput
```

Este es el único contrato que el Orquestador (futuro M10) debería asumir
estable; el resto de funciones internas puede cambiar sin romper
integración.

## 5. Estructura del proyecto

```structure
chess-robot-arm/
├── pyproject.toml
├── README.md
├── .python-version
├── src/
│   └── chess_brain/
│       ├── __init__.py
│       ├── decision_engine.py    # M5
│       ├── display.py             # presentación en consola
│       ├── game_state.py         # M4
│       ├── io_adapter.py          # Entrada / Salida
│       ├── main.py                # CLI de producto funcional
│       ├── brain_types.py               # VisionInput, MoveResult, excepciones
│       ├── vision_stub.py         # simulador de Visión
│       └── engine_binaries/        # almacenamiento de stockfish.exe
├── tests/
│   ├── test_game_state.py
│   ├── test_decision_engine.py
│   ├── test_io_adapter.py
│   └── fixtures/
│       └── boards.py               # matrices 8x8 de prueba
└── .gitignore
```

## 6. Setup del proyecto (Windows 11 + uv)

```powershell
uv init chess-robot-arm
cd chess-robot-arm

uv add chess
uv add --dev pytest pytest-cov

# Stockfish: descargar binario para Windows desde https://stockfishchess.org/download/
# Colocar en una ruta conocida, ej: ./src/chess_brain/engine_binaries/stockfish.exe
```

`pyproject.toml` — fragmento relevante:

```toml
[project]
name = "chess-robot-arm"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "chess>=1.11.2",
]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
]
```

Ejecución:

```powershell
uv run poe chess-test

uv run chess-brain --stockfish-path "./src/chess_brain/engine_binaries/stockfish.exe" --human-color white --think-time 1.0
```

## 7. Plan de pruebas

### 7.1 `test_game_state.py`

| Caso                            | Verifica                                                  |
| ------------------------------- | --------------------------------------------------------- |
| Movimiento simple válido (peón) | `infer_human_move` identifica correctamente `e2e4`        |
| Captura                         | Se detecta la jugada de captura correcta                  |
| Enroque corto/largo             | Se infiere como enroque, no como dos movimientos sueltos  |
| Captura al paso                 | Caso especial, peón capturado fuera de la casilla destino |
| Promoción                       | Se infiere el tipo de pieza de promoción                  |
| Matriz inválida                 | Se lanza `IllegalStateError`                              |
| Jaque mate                      | `get_game_status` retorna `"checkmate"`                   |

### 7.2 `test_decision_engine.py`

| Caso                                  | Verifica                                   |
| ------------------------------------- | ------------------------------------------ |
| Posición inicial                      | El motor retorna una jugada legal          |
| Mate en 1 disponible                  | El motor encuentra el mate                 |
| `think_time` configurable             | El tiempo de cómputo respeta el parámetro  |
| Motor no disponible (ruta incorrecta) | Se lanza `EngineError`                     |
| Cierre limpio del motor               | `engine.quit()` no deja procesos huérfanos |

### 7.3 `test_io_adapter.py`

| Caso                                              | Verifica                                                             |
| ------------------------------------------------- | -------------------------------------------------------------------- |
| `parse_vision_input` con matriz válida            | Retorna `chess.Move` correcto                                        |
| `build_move_result` jugada normal                 | Todos los campos correctos, flags en `False`/`None`                  |
| `build_move_result` captura                       | `is_capture=True`, `captured_piece` correcto (usando `board_before`) |
| `build_move_result` enroque                       | `is_castle=True`, `castle_side` correcto                             |
| `build_move_result` jaque mate                    | `game_status="checkmate"`                                            |
| Integración M4→M5→Salida con `fixtures/boards.py` | Flujo completo matriz → `MoveResult`                                 |

## 8. Pendiente (fuera de alcance de este SPEC)

- Verificar la suite de tests actual contra este contrato (no fue
  compartida en esta revisión).
- Cobertura de tests para `vision_stub.py`, `display.py` y los comandos
  de `main.py` (hoy sin tests automatizados por ser CLI interactiva).
- Definir contrato del módulo 6 (Planificación de Movimiento) consumiendo
  `MoveResult`.
- Definir política de color/`side_to_move` del robot para el primer
  movimiento del sistema completo (parcialmente resuelto aquí vía
  `--human-color`, pero es una decisión de producto para el sistema
  integrado).
- Manejo de timeout/reconexión si Stockfish se cuelga a mitad de partida.
