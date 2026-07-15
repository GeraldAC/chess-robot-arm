# SPEC — chess_vision: Detección del Tablero (M2) + Clasificación de Piezas (M3)

## 1. Alcance

Este SPEC cubre:

- **`board_detector.py`** (M2 — Detección del tablero)
- **`piece_classifier.py`** (M3 — Clasificación de piezas)
- **`square_mapper.py`** (asignación de detecciones a casillas)
- **`orientation.py`** (resolución de orientación / autocalibración)
- **`pipeline.py`** (orquestación M2 → M3 → `VisionInput`)
- **`camera_capture.py`** (lado receptor de M1: obtiene el frame desde la ESP32-CAM)
- **`types.py`** (contratos internos de `chess_vision`)
- **`__init__.py`** (superficie pública del paquete)

Arquitectura: módulo Python (`chess_vision`) importado por el orquestador,
mismo proceso, mismo criterio YAGNI que `chess_brain` (M4-5). `chess_vision`
depende de `chess_brain.types` (`VisionInput`, `BoardMatrix`) — la
dependencia es unidireccional, `chess_brain` no conoce a `chess_vision`.

**Frontera aclarada respecto al SPEC general:** M0 (Calibración) queda
acotado a la calibración cinemática del brazo (coordenada de imagen ↔
coordenada física, insumo de M7/M8). La responsabilidad de "¿dónde está
cada casilla en esta imagen?" es de M2, y se resuelve **por cada frame**,
no una sola vez — porque la cámara puede reposicionarse entre partidas
(decisión de producto confirmada en esta revisión) y no se usan
marcadores físicos (ArUco descartado por preferencia del proyecto).

El firmware/lado-emisor de la ESP32-CAM (M1) y el envío del `MoveResult`
a M6 (Planificación de movimiento) quedan fuera de alcance.

## 2. Decisiones de diseño

| Decisión                          | Valor                                                                                                                                                                                                                                                                                                                |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Detección del tablero             | YOLO11n, detecta 4 esquinas (puntos), se ejecuta en cada frame — sin homografía estática ni marcadores                                                                                                                                                                                                               |
| Clasificación de piezas           | YOLO11s, 12 clases, sobre la imagen **ya rectificada** (vista cenital) por M2, no sobre la imagen cruda                                                                                                                                                                                                              |
| Origen de los modelos             | Fine-tuning desde checkpoint COCO-preentrenado de YOLO11 (`ultralytics`), no entrenamiento desde cero. Datasets públicos de piezas (Roboflow Universe) se usan como _dataset_ de partida para el fine-tuning de M3 — no se cargan pesos de YOLOv8 dentro de YOLO11 (arquitecturas distintas, no son intercambiables) |
| Entrenamiento vs. inferencia      | Entrenamiento/fine-tuning en Colab (GPU gratuita); inferencia en producción sobre CPU (laptop)                                                                                                                                                                                                                       |
| Ancla pieza → casilla             | Punto medio-inferior (bottom-center) del bounding box, no el centroide — corrige el error de paralaje de piezas altas (rey/dama) vistas en ángulo                                                                                                                                                                    |
| Resolución de orientación (a1/h8) | Autocalibración una única vez por partida: se compara la matriz cruda contra la posición inicial estándar probando identidad y rotación de 180°; el resultado se cachea para el resto de la partida                                                                                                                  |
| Supuesto de montaje               | La cámara puede reposicionarse entre partidas, pero se asume que no queda rotada ~90° respecto al tablero (mismo "arriba/abajo" aproximado). Si esta asunción no se cumple, `orientation.py` debe extenderse a las 4 rotaciones — ver §8                                                                             |
| Manejo de incertidumbre           | Confianza por casilla explícita; por debajo de un umbral configurable se lanza un error de contrato — nunca se infiere en silencio                                                                                                                                                                                   |
| Arquitectura                      | Módulo Python importado, funciones puras donde es posible; los modelos YOLO cargados se pasan explícitamente como parámetro (mismo patrón que `engine: SimpleEngine` en M5)                                                                                                                                          |

## 3. Contrato de datos

### 3.1 Tipos base

```python
RawFrame = np.ndarray  # imagen BGR cruda (H, W, 3), tal como la entrega camera_capture.py
Point2D = tuple[float, float]

@dataclass(frozen=True)
class BoardCorners:
    """4 esquinas del tablero en la imagen cruda, en orden cíclico
    horario, empezando por la de coordenada (x+y) mínima. Representan
    geometría de cámara, NO todavía a1/h8 — esa resolución ocurre en
    orientation.py."""
    points_px: tuple[Point2D, Point2D, Point2D, Point2D]
    confidences: tuple[float, float, float, float]

CameraOrientedMatrix = list[list[str | None]]
# 8x8, fila 0 = fila superior de la imagen rectificada.
# Orientación de CÁMARA, aún no resuelta a orientación de ajedrez.

@dataclass(frozen=True)
class PieceDetection:
    piece_code: str  # "wP", "bN", "bK", etc. — mismo alfabeto que BoardMatrix
    bbox_px: tuple[float, float, float, float]  # x1,y1,x2,y2 en la imagen rectificada
    confidence: float
```

### 3.2 Errores

```python
class VisionError(Exception):
    """Clase base de errores de contrato de chess_vision."""

class BoardNotFoundError(VisionError):
    """No se detectaron las 4 esquinas del tablero con confianza
    suficiente en el frame recibido."""

class LowConfidenceDetectionError(VisionError):
    """Una o más casillas quedaron por debajo del umbral de confianza
    configurado. Incluye la lista de casillas afectadas para que el
    llamador decida (reintentar captura, pedir confirmación, etc.)."""

    def __init__(self, uncertain_cells: list[tuple[int, int]]):
        ...

class OrientationAmbiguousError(VisionError):
    """La matriz cruda no coincide con la posición inicial estándar en
    ninguna orientación evaluada (identidad / rotación 180°)."""
```

### 3.3 Salida hacia `chess_brain`

El punto de salida de este subsistema es un `VisionInput`
(`chess_brain.types.VisionInput`, ya definido en el SPEC de M4-5):
`board_matrix: BoardMatrix` + `side_to_move: Literal["w","b"]`.
`chess_vision` no determina `side_to_move` (no es su responsabilidad,
ni tiene forma de saberlo a partir de una sola imagen) — se recibe como
parámetro externo desde quien orqueste el turno.

## 4. Diseño interno

### 4.1 `board_detector.py` (M2 — Detección del tablero)

```python
def detect_board_corners(
    frame: RawFrame,
    model,  # YOLO cargado (ultralytics.YOLO)
    conf_threshold: float = 0.5,
) -> BoardCorners:
    """Corre el modelo de esquinas sobre `frame`, ordena los 4 puntos
    en sentido horario desde el de coordenada mínima. Lanza
    BoardNotFoundError si no se detectan 4 puntos con confianza
    >= conf_threshold."""

def compute_homography(corners: BoardCorners, output_size: int = 800) -> np.ndarray:
    """cv2.getPerspectiveTransform: matriz 3x3 que mapea
    corners.points_px a las esquinas de un lienzo cuadrado de
    output_size x output_size."""

def warp_to_topdown(
    frame: RawFrame,
    homography: np.ndarray,
    output_size: int = 800,
) -> np.ndarray:
    """cv2.warpPerspective: aplica la homografía y retorna la imagen
    rectificada (vista cenital del tablero)."""
```

### 4.2 `piece_classifier.py` (M3 — Clasificación de piezas)

```python
def detect_pieces(
    topdown_image: np.ndarray,
    model,  # YOLO cargado, 12 clases
    conf_threshold: float = 0.4,
) -> list[PieceDetection]:
    """Corre el modelo de piezas sobre la imagen ya rectificada por M2.
    Retorna detecciones crudas con su bbox — no asigna a casillas
    todavía (responsabilidad de square_mapper.py)."""
```

### 4.3 `square_mapper.py`

```python
def build_camera_matrix(
    detections: list[PieceDetection],
    board_px: int,
    grid_size: int = 8,
) -> tuple[CameraOrientedMatrix, list[list[float]]]:
    """Asigna cada detección a una celda de la grilla usando el punto
    medio-inferior del bbox como ancla. Retorna la matriz cruda
    (orientación de cámara) y una matriz paralela de confidence por
    celda (1.0 en celdas vacías por ausencia de detección). Si dos
    detecciones caen en la misma celda, se conserva la de mayor
    confidence y se registra la colisión (log, no excepción)."""

def check_confidence(
    confidences: list[list[float]],
    threshold: float,
) -> None:
    """Recorre la matriz de confidence; si alguna celda está por
    debajo de `threshold`, lanza LowConfidenceDetectionError con la
    lista de celdas afectadas."""
```

### 4.4 `orientation.py`

```python
STANDARD_START_MATRIX: BoardMatrix  # posición inicial estándar de ajedrez, constante del módulo

def resolve_orientation(
    camera_matrix: CameraOrientedMatrix,
) -> Literal["identity", "rotated_180"]:
    """Se usa una única vez, al iniciar una partida (tablero en
    posición inicial). Compara camera_matrix contra
    STANDARD_START_MATRIX probando identidad y rotación 180° (reversa
    de filas y columnas). Retorna la orientación que coincide. Lanza
    OrientationAmbiguousError si ninguna coincide (ej. se llamó a
    mitad de partida por error)."""

def apply_orientation(
    camera_matrix: CameraOrientedMatrix,
    orientation: Literal["identity", "rotated_180"],
) -> BoardMatrix:
    """Aplica la rotación ya resuelta. Función pura, sin estado."""
```

### 4.5 `pipeline.py`

```python
def calibrate_orientation(
    frame: RawFrame,
    board_model,
    piece_model,
) -> Literal["identity", "rotated_180"]:
    """Se llama una única vez al inicio de cada partida, con el
    tablero en posición inicial. Corre el pipeline de detección (sin
    aplicar orientación) y delega en resolve_orientation. El resultado
    debe cachearse por el llamador para el resto de la partida."""

def process_frame(
    frame: RawFrame,
    board_model,
    piece_model,
    orientation: Literal["identity", "rotated_180"],
    side_to_move: Literal["w", "b"],
    confidence_threshold: float = 0.5,
) -> VisionInput:
    """Punto de entrada único del subsistema. Orquesta:
    detect_board_corners → compute_homography → warp_to_topdown →
    detect_pieces → build_camera_matrix → check_confidence →
    apply_orientation → VisionInput. Lanza BoardNotFoundError o
    LowConfidenceDetectionError según corresponda; nunca retorna una
    matriz con casillas inciertas silenciadas."""
```

### 4.6 `camera_capture.py`

```python
def fetch_frame(esp32_cam_url: str, timeout: float = 5.0) -> RawFrame:
    """Descarga un frame JPEG desde el endpoint HTTP de la ESP32-CAM y
    lo decodifica (cv2.imdecode) a RawFrame. Lanza VisionError si falla
    la conexión o la decodificación. Cubre solo el lado receptor
    (laptop) de M1 — el firmware de la ESP32-CAM queda fuera de
    alcance."""
```

### 4.7 `__init__.py` — Superficie pública

```python
from chess_vision.pipeline import process_frame, calibrate_orientation
from chess_vision.types import (
    VisionError,
    BoardNotFoundError,
    LowConfidenceDetectionError,
    OrientationAmbiguousError,
)
```

Igual que en `chess_brain`, este es el único contrato que un futuro
Orquestador (M10) debería asumir estable.

## 5. Estructura del proyecto

```structure
chess-robot-arm/
├── pyproject.toml
├── README.md
├── src/
│   ├── chess_brain/                 # M4-5 (ya implementado)
│   └── chess_vision/                 # NUEVO — M2-3
│       ├── __init__.py
│       ├── types.py
│       ├── board_detector.py         # M2
│       ├── piece_classifier.py       # M3
│       ├── square_mapper.py
│       ├── orientation.py
│       ├── pipeline.py
│       ├── camera_capture.py
│       └── models/
│           ├── board_corners.pt      # pesos YOLO11n fine-tuned
│           └── pieces.pt             # pesos YOLO11s fine-tuned
├── training/
│   ├── train_board_detector.ipynb    # Colab: fine-tuning YOLO11n (esquinas)
│   ├── train_piece_classifier.ipynb  # Colab: fine-tuning YOLO11s (piezas)
│   └── datasets/
│       ├── board_corners/            # imágenes + labels propias (formato YOLO)
│       └── pieces/                   # dataset propio + base pública (Roboflow)
└── tests/
    ├── test_board_detector.py
    ├── test_piece_classifier.py
    ├── test_square_mapper.py
    ├── test_orientation.py
    ├── test_pipeline.py
    └── fixtures/
        ├── fake_yolo.py
        └── sample_frames/             # imágenes reales de prueba
```

## 6. Setup del proyecto (Windows 11 + uv)

```powershell
cd chess-robot-arm

uv add ultralytics opencv-python numpy requests
```

`pyproject.toml` — fragmento a añadir:

```toml
[project]
dependencies = [
    "chess>=1.11.2",
    "ultralytics>=8.3.0",
    "opencv-python>=4.10.0",
    "numpy>=2.0.0",
    "requests>=2.32.0",
]
```

**Entrenamiento (Colab, no en la laptop):** los notebooks en `training/`
parten de un checkpoint COCO-preentrenado de YOLO11 (`yolo11n.pt`,
`yolo11s.pt`) y hacen fine-tuning sobre los datasets en
`training/datasets/`. Los `.pt` resultantes se descargan y se colocan
en `src/chess_vision/models/`. La inferencia en producción corre en CPU
sobre la laptop — no se asume GPU disponible en tiempo de ejecución.

## 7. Plan de pruebas

### 7.1 `test_board_detector.py`

| Caso                          | Verifica                                                                                     |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| Tablero centrado en la imagen | Se detectan las 4 esquinas correctas                                                         |
| Imagen sin tablero visible    | Se lanza `BoardNotFoundError`                                                                |
| Esquinas con confianza baja   | Se lanza `BoardNotFoundError` (no se aceptan esquinas de baja confianza)                     |
| Homografía + warp             | La imagen resultante es cuadrada, del tamaño esperado, sin distorsión de perspectiva visible |

### 7.2 `test_piece_classifier.py`

| Caso                                 | Verifica                                                                              |
| ------------------------------------ | ------------------------------------------------------------------------------------- |
| Posición inicial (32 piezas)         | Se detectan las 32 piezas con el código correcto                                      |
| Posición con capturas (menos piezas) | Coincide el conteo y tipo de piezas restantes                                         |
| Tablero vacío                        | Retorna lista de detecciones vacía                                                    |
| Pieza con confianza baja             | La detección se conserva pero con su confidence real (no se descarta silenciosamente) |

### 7.3 `test_square_mapper.py`

| Caso                                  | Verifica                                                                                  |
| ------------------------------------- | ----------------------------------------------------------------------------------------- |
| Pieza alta vista en ángulo (rey/dama) | El ancla bottom-center asigna la pieza a su casilla real, no a la de atrás                |
| Dos detecciones en la misma celda     | Se conserva la de mayor confidence, se registra la colisión                               |
| Celda por debajo del umbral           | `check_confidence` lanza `LowConfidenceDetectionError` con la celda correcta identificada |

### 7.4 `test_orientation.py`

| Caso                                        | Verifica                                      |
| ------------------------------------------- | --------------------------------------------- |
| Matriz cruda = posición inicial estándar    | `resolve_orientation` retorna `"identity"`    |
| Matriz cruda = posición inicial rotada 180° | `resolve_orientation` retorna `"rotated_180"` |
| Matriz cruda no coincide con ninguna        | Se lanza `OrientationAmbiguousError`          |

### 7.5 `test_pipeline.py` (integración)

| Caso                                              | Verifica                                                                                       |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Frame real (fixture) → `process_frame`            | Devuelve un `VisionInput` válido, consumible directamente por `chess_brain.parse_vision_input` |
| `calibrate_orientation` con posición inicial real | Resuelve la orientación correcta end-to-end (esquinas → piezas → comparación)                  |

## 8. Pendiente (fuera de alcance de este SPEC)

- Recolección y etiquetado del dataset propio (esquinas y piezas) — los
  notebooks de `training/` asumen que el dataset ya existe.
- Validación empírica del mAP objetivo; los datasets públicos referenciados
  solo sirven como base de partida para el fine-tuning.
- Firmware/lado-emisor de la ESP32-CAM (M1) — `camera_capture.py` solo
  cubre la recepción en la laptop.
- Política de reintento ante `BoardNotFoundError` /
  `LowConfidenceDetectionError` (¿recapturar automáticamente? ¿cuántas
  veces?) — corresponde al Orquestador (M10).
- Manejo de piezas capturadas que queden dentro del encuadre pero fuera
  del área de las 64 casillas.
- Validación de la asunción "cámara no rotada ~90°"; si se viola,
  `orientation.py` debe extenderse a las 4 rotaciones, no solo 0°/180°.
- Latencia real del pipeline (dos modelos YOLO por jugada) en CPU — no
  medida todavía.
- Robustez ante iluminación variable (luz ambiente, sombra proyectada
  por el brazo sobre el tablero durante su propio movimiento).

## 9. Ajustes durante la implementación

`detect_pieces` ahora usa un umbral de confianza bajo ("piso de
ruido") dentro del pipeline, distinto del umbral real de decisión que
usa `check_confidence`. Si se usara un solo umbral, una pieza
detectada con confianza baja simplemente desaparecía antes de llegar
a la matriz, y la casilla se reportaba como "vacía, 100% segura" —
exactamente la incertidumbre que el diseño quería exponer, no
ocultar. Queda documentado en el código (`piece_classifier.py` y
`pipeline.py`).
