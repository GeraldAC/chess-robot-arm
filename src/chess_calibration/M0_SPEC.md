# SPEC — chess_calibration: Calibración (M0)

> **Estado: implementado, 28/28 tests pasando, ~98% cobertura.** Ver §11
> para el detalle de pruebas. Depende de decisiones de producto tomadas
> explícitamente para este SPEC: calibración por **medición manual**,
> **recalibración una vez por sesión de juego** (no montaje fijo
> permanente), y las 4 zonas físicas nuevas se definen **como parte de
> este módulo**, no antes.

## 1. Alcance

Este documento cubre:

- **`calibration_types.py`** (contratos internos de `chess_calibration`)
- **`calibration_geometry.py`** (interpolación y validación geométrica)
- **`calibration_io.py`** (lectura de medición manual, construcción y
  persistencia del `CalibrationMap`)
- **`calibration_main.py`** (CLI de producto funcional, una ejecución por
  sesión de juego)
- **`__init__.py`** (superficie pública del paquete)

Arquitectura: módulo Python (`chess_calibration`) importado por el
orquestador, mismo proceso, mismo criterio YAGNI que `chess_brain`,
`chess_vision` y `chess_planner`. `chess_calibration` depende de
`chess_planner.movement_types.Zone` (reutiliza el enum de zonas ya
definido, en vez de duplicarlo) — dependencia unidireccional, sin
importar nada de `chess_vision` ni `chess_brain`.

**Lo que este módulo NO hace** (aclaración de alcance, mismo espíritu que
§1 de `M6_SPEC.md`): M0 no mueve el brazo, no lee ángulos de servo, y no
calcula cinemática inversa. Solo produce un mapa estático
`Location -> coordenada cartesiana del brazo`, a partir de medición física
manual. La resolución de ese mapa a ángulos de articulación es
responsabilidad de M7 (Cinemática Inversa), que queda fuera de este SPEC.

## 2. Enfoque técnico

El README describe la responsabilidad de M0 como "mapeo píxel ↔ casilla ↔
coordenada del brazo". El tramo **píxel ↔ casilla** ya está resuelto por M2
(`compute_square_grid` + `square_mapper.py`). Lo que falta, y lo único que
cubre este SPEC, es **casilla/zona ↔ coordenada del brazo**.

- **Método de calibración: medición manual** (regla/calibre), no
  "teach mode" ni hand-eye calibration por cámara. Motivo: los servos
  MG996R del BOM no tienen feedback de posición, y M7/M8 (cinemática
  inversa, control de actuadores) todavía no existen — cualquier enfoque
  que dependa de mover el brazo para calibrar invierte el orden de
  dependencias del proyecto. Ver §9 para el detalle de las alternativas
  descartadas.
- **Geometría del tablero:** se miden las 4 casillas-esquina (`a1`, `a8`,
  `h1`, `h8`) por su **centro**, no el borde físico del tablero. Con esos
  4 puntos 3D se interpola el resto de las 64 casillas mediante
  **interpolación bilineal en (x, y, z)** — mismo principio que
  `board_detector.compute_square_grid` (M2), pero en espacio real (mm) en
  vez de píxeles, y sin homografía de perspectiva (un tablero físico
  medido con regla es plano por definición del método; no hay distorsión
  de cámara que corregir). Interpolar también `z` (no asumir un plano
  perfectamente nivelado) tolera una ligera inclinación del tablero sin
  requerir un tipo de dato distinto.
- **Zonas nuevas** (`DISCARD_WHITE/BLACK`, `SPARE_WHITE/BLACK`): no forman
  parte de la grilla 8x8, así que cada una se mide como **un único punto**
  (no se interpola) — consistente con `BOM.md` §5, que ya especifica que
  el descarte es por caída en bandeja, sin necesidad de posicionamiento
  fino.
- **Recalibración por sesión:** dado que tablero/brazo pueden moverse
  entre partidas (decisión de producto), M0 se ejecuta **una vez al
  inicio de cada sesión de juego**, antes de que el Orquestador (M10)
  arranque el ciclo de partida — mismo patrón que ya usa M2/M3 con
  `--calibrate` para resolver orientación una vez por partida. El
  resultado se persiste en un archivo de sesión (JSON), no en un config
  permanente del proyecto.

## 3. Sistema de referencia (decisión de diseño explícita)

- **Origen (0, 0, 0):** intersección del eje de rotación de la base del
  brazo (servo 1 / articulación 0) con el plano de la mesa.
- **Eje X:** dirección "hacia adelante" del brazo (posición 0° de la
  base).
- **Eje Y:** perpendicular a X sobre el plano de la mesa, regla de la
  mano derecha.
- **Eje Z:** vertical, positivo hacia arriba desde la mesa.
- **Unidades:** milímetros, float.

Esta convención debe respetarse al medir; no la valida el software (no
hay forma de verificar desde una regla que el usuario alineó bien los
ejes). Ver protocolo en §4.

## 4. Protocolo de calibración física (procedimiento, no código)

1. Con el tablero y las 4 zonas ya colocadas en su posición de juego,
   ubica físicamente el origen y los ejes definidos en §3.
2. Mide `(x, y, z)` del **centro** de las casillas `a1`, `a8`, `h1`, `h8`.
3. Mide `(x, y, z)` del centro de cada una de las 4 zonas físicas
   (`DISCARD_WHITE`, `DISCARD_BLACK`, `SPARE_WHITE`, `SPARE_BLACK`),
   ubicadas dentro del radio de alcance de ~355 mm del brazo (`BOM.md`
   §3).
4. Registra los 8 puntos en el archivo YAML de entrada (§6.1).
5. Ejecuta `calibration_main.py` (§6.4). Si la geometría medida es
   inconsistente (ver `validate_board_geometry`, §6.2), el programa
   informa el error en vez de generar un mapa incorrecto.
6. Repite este proceso al inicio de cada sesión de juego en la que el
   tablero, las zonas o el brazo hayan podido moverse.

## 5. Contrato de datos

### 5.1 Tipos base

```python
@dataclass(frozen=True)
class ArmPoint:
    """Coordenada cartesiana en el sistema de referencia del brazo (§3)."""
    x_mm: float
    y_mm: float
    z_mm: float

@dataclass(frozen=True)
class BoardCornersArm:
    """Centros medidos de las 4 casillas-esquina del tablero físico,
    en coordenadas del brazo. NO son el borde físico del tablero."""
    a1: ArmPoint
    a8: ArmPoint
    h1: ArmPoint
    h8: ArmPoint

# Location reutiliza la misma noción que chess_planner: casilla
# algebraica ("a1".."h8") o el .value de chess_planner.movement_types.Zone
Location = str

CalibrationMap = dict[Location, ArmPoint]
# 64 entradas de casilla + 4 entradas de zona = 68 claves.
```

### 5.2 Errores

```python
class CalibrationError(Exception):
    """Clase base de errores de contrato de chess_calibration."""

class IncompleteCalibrationInputError(CalibrationError):
    """Falta algún corner o alguna zona requerida en el archivo de
    entrada."""

class InvalidBoardGeometryError(CalibrationError):
    """Los 4 puntos medidos de las esquinas no forman una geometría de
    tablero plausible dentro de la tolerancia configurada (ver
    validate_board_geometry). Suele indicar un error de medición o de
    tipeo, no un tablero real deforme."""

class CalibrationSessionNotFoundError(CalibrationError):
    """No existe un archivo de sesión de calibración válido para la
    partida actual (el Orquestador debe tratar esto como señal de
    flujo: pedir recalibración, no fallar en silencio)."""
```

## 6. Diseño interno

### 6.1 `calibration_io.py` — entrada de medición manual

```python
def load_calibration_input(
    path: str,
) -> tuple[BoardCornersArm, dict[Zone, ArmPoint]]:
    """Lee un YAML con los 4 corners (a1/a8/h1/h8) y los 4 puntos de
    zona medidos manualmente (ver formato de ejemplo en §7).
    Lanza IncompleteCalibrationInputError si falta algún campo
    requerido."""
```

### 6.2 `calibration_geometry.py`

```python
def compute_square_centers(
    corners: BoardCornersArm,
    grid_size: int = 8,
) -> dict[str, ArmPoint]:
    """Interpolación bilineal en (x, y, z) de los 4 centros medidos ->
    centro de cada una de las 64 casillas, en coordenadas del brazo.
    Análogo a board_detector.compute_square_grid (M2), sin homografía
    de perspectiva (medición física plana, no imagen de cámara)."""

def validate_board_geometry(
    corners: BoardCornersArm,
    expected_square_size_mm: float,
    tolerance_mm: float = 5.0,
) -> None:
    """Verifica, dentro de tolerance_mm:
    - distancia(a1, h1) y distancia(a8, h8) ~= 7 * expected_square_size_mm
    - distancia(a1, a8) y distancia(h1, h8) ~= 7 * expected_square_size_mm
    - distancia(a1, h8) y distancia(a8, h1) ~= 7 * expected_square_size_mm * sqrt(2)
    Lanza InvalidBoardGeometryError si alguna se sale de tolerancia.
    No exige perfección geométrica: solo atrapa errores gruesos de
    medición o de tipeo antes de que lleguen a un PhysicalPlan real."""
```

### 6.3 `calibration_io.py` (continuación) — construcción y persistencia

```python
def build_calibration_map(
    corners: BoardCornersArm,
    zones: dict[Zone, ArmPoint],
    expected_square_size_mm: float,
    tolerance_mm: float = 5.0,
) -> CalibrationMap:
    """Punto de entrada único del subsistema. Llama a
    validate_board_geometry, luego compute_square_centers, y combina
    el resultado con `zones` (usando Zone.value como clave) en un único
    CalibrationMap de 68 entradas."""

def save_calibration_session(calibration_map: CalibrationMap, path: str) -> None:
    """Persiste el CalibrationMap ya resuelto de la sesión actual a
    JSON, para que el Orquestador (M10) lo cargue sin repetir la
    interpolación durante la partida."""

def load_calibration_session(path: str) -> CalibrationMap:
    """Carga un CalibrationMap ya resuelto de una sesión previa.
    Lanza CalibrationSessionNotFoundError si el archivo no existe o
    está incompleto (< 68 claves)."""
```

### 6.4 `calibration_main.py` — CLI de producto funcional

Se ejecuta **una vez por sesión de juego**, antes de que el Orquestador
(M10) arranque el ciclo de partida — mismo rol que `--calibrate` en
`vision_main.py` (M2/M3), pero para geometría física en vez de
orientación de imagen.

**Argumentos:**

| Argumento          | Requerido | Default                    | Descripción                                                                                           |
| ------------------ | --------- | -------------------------- | ----------------------------------------------------------------------------------------------------- |
| `--input`          | Sí        | —                          | Ruta al YAML con los 8 puntos medidos (§7)                                                            |
| `--square-size-mm` | Sí        | —                          | Tamaño real de casilla del tablero del usuario. Sin default: depende del set físico, no debe asumirse |
| `--tolerance-mm`   | No        | `5.0`                      | Tolerancia de `validate_board_geometry`                                                               |
| `--output`         | No        | `calibration_session.json` | Dónde guardar el `CalibrationMap` resuelto                                                            |

**Salida impresa:** los 4 corners y las 4 zonas leídos → resultado de la
validación de geometría → resumen del `CalibrationMap` (68 entradas,
formato tabular casilla/zona → x, y, z) → confirmación de guardado.

### 6.5 `__init__.py` — Superficie pública

```python
from chess_calibration.calibration_io import (
    build_calibration_map, load_calibration_session, save_calibration_session,
)
from chess_calibration.calibration_types import (
    ArmPoint, BoardCornersArm, CalibrationMap,
    CalibrationError, InvalidBoardGeometryError,
    IncompleteCalibrationInputError, CalibrationSessionNotFoundError,
)
```

Igual que en los módulos anteriores, este es el único contrato que M7 y
el futuro Orquestador (M10) deberían asumir estable.

## 7. Formato del archivo de entrada (`--input`)

```yaml
square_corners:
  a1: { x_mm: 120.0, y_mm: -80.0, z_mm: 15.0 }
  a8: { x_mm: 120.0, y_mm: 200.0, z_mm: 16.0 }
  h1: { x_mm: 400.0, y_mm: -80.0, z_mm: 14.0 }
  h8: { x_mm: 400.0, y_mm: 200.0, z_mm: 15.0 }

zones:
  DISCARD_WHITE: { x_mm: 60.0, y_mm: -120.0, z_mm: 40.0 }
  DISCARD_BLACK: { x_mm: 460.0, y_mm: -120.0, z_mm: 40.0 }
  SPARE_WHITE: { x_mm: 60.0, y_mm: 220.0, z_mm: 40.0 }
  SPARE_BLACK: { x_mm: 460.0, y_mm: 220.0, z_mm: 40.0 }
```

Los valores mostrados son de ejemplo, no medidos.

## 8. Estructura del proyecto

```structure
chess-robot-arm/
├── src/
│   ├── chess_brain/                   # M4-5 (implementado)
│   ├── chess_vision/                  # M2-3 (implementado)
│   ├── chess_planner/                 # M6 (implementado)
│   └── chess_calibration/             # M0 (a implementar)
│       ├── __init__.py
│       ├── M0_SPEC.md
│       ├── calibration_types.py        # ArmPoint, BoardCornersArm, CalibrationMap, excepciones
│       ├── calibration_geometry.py     # compute_square_centers, validate_board_geometry
│       ├── calibration_io.py           # load_calibration_input, build_calibration_map, save/load session
│       └── calibration_main.py         # CLI de producto funcional
└── tests/
    ├── test_brain/
    ├── test_vision/
    ├── test_planner/
    └── test_calibration/
        ├── __init__.py
        ├── test_calibration_geometry.py
        ├── test_calibration_io.py
        ├── test_calibration_main.py
        └── fixtures/
            ├── __init__.py
            └── sample_calibration.yaml   # entrada de ejemplo, geometría válida
```

No se requieren dependencias nuevas más allá de un parser YAML
(`uv add pyyaml`); el resto usa solo `dataclasses` y `json` de la
librería estándar.

## 9. Alternativas evaluadas y descartadas

| Alternativa                                                                                                      | Por qué se descartó para v1                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Teach mode** (mover el gripper a cada punto de referencia y registrar la posición)                             | Requiere M7 (modelo cinemático) y M8 (control de actuadores) ya implementados para poder mover el brazo y conocer su pose — invierte el orden de dependencias del proyecto. Además, los servos MG996R del BOM no tienen feedback de posición, por lo que "registrar la posición actual" no es directo incluso con M7/M8 listos. |
| **Hand-eye calibration** (cámara ve un marcador en el efector final, se resuelve la transformación cámara↔brazo) | Mismo problema de fondo: requiere mover el brazo a poses conocidas. Además introduce un requisito de hardware no contemplado en `BOM.md` (marcador tipo ArUco en el efector). Queda como mejora natural una vez que M7/M8 existan (ver §10).                                                                                    |

## 10. Pendiente (fuera de alcance de este SPEC)

- **Ubicación física real de las 4 zonas** dentro del radio de ~355 mm:
  este SPEC define cómo medirlas y representarlas, pero no decide dónde
  van — es una decisión física que toma quien arma el hardware, guiada
  por el protocolo de §4.
- **Actualizar `BOM.md` §5** con las 4 zonas ya formalizadas por
  `chess_planner` (M6) y con un instrumento de medición (calibre/regla)
  como material explícito del proyecto, requerido por el método de
  calibración elegido aquí.
- **Contrato M0 → M7:** este SPEC entrega `CalibrationMap`; queda para el
  SPEC de M7 decidir si la función de lookup `Location -> ArmPoint` vive
  en `chess_calibration` o en `chess_planner`/`chess_kinematics`.
- **Validación de alcance físico:** confirmar que los 68 puntos del
  `CalibrationMap` caen dentro del radio de alcance del brazo (~355 mm)
  es una mejora natural a `validate_board_geometry`, no incluida en v1.
- **Manejo de `CalibrationSessionNotFoundError` por el Orquestador (M10):**
  si al iniciar una partida no hay sesión de calibración vigente, M10
  debe decidir si bloquea el inicio o dispara `calibration_main.py`
  automáticamente — decisión de producto, no de este SPEC.
- **Migración a teach mode / hand-eye calibration** una vez que M7/M8
  existan y, si se decide, se agregue feedback de posición al hardware
  (ver §9) — el `CalibrationMap` como contrato de salida no debería
  cambiar, solo el método para construirlo.
- Reubicar `Zone` a un módulo compartido si la dependencia
  `chess_calibration -> chess_planner` resulta incómoda más adelante.

## 11. Plan de pruebas

| Archivo                        | Casos clave                                                                                                                                                                                                                                                                                              |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_calibration_geometry.py` | Interpolación bilineal de las 64 casillas; casillas-esquina coinciden exactamente con la medición; tolera tablero inclinado (z variable); geometría dentro/fuera de tolerancia; detección de tablero no rectangular vía diagonales; `ValueError` en parámetros inválidos                                 |
| `test_calibration_io.py`       | Carga de YAML válido; archivo/corner/zona faltante, punto malformado o YAML inválido → `IncompleteCalibrationInputError`; `build_calibration_map` produce 68 entradas; geometría inválida se propaga; round-trip de sesión JSON; sesión faltante/incompleta/corrupta → `CalibrationSessionNotFoundError` |
| `test_calibration_main.py`     | CLI end-to-end: éxito con 68 entradas y archivo de sesión creado; geometría inválida retorna código de salida 1 sin crear archivo; archivo de entrada faltante retorna código de salida 1                                                                                                                |

28 tests, ~98% de cobertura de líneas.
