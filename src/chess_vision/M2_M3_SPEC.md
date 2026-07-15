# SPEC — chess_vision: Detección del Tablero (M2) + Clasificación de Piezas (M3)

> **Estado: implementado, 22/22 tests pasando.** Detección de tablero
> validada end-to-end con foto real. Modelo de piezas pendiente de
> validación con hardware/fotos reales del usuario — ver §10.

## 1. Alcance

Este documento cubre:

- **`board_detector.py`** (M2 — Detección del tablero, 100% OpenCV clásico)
- **`piece_classifier.py`** (M3 — Clasificación de piezas, modelo pretrained de terceros)
- **`square_mapper.py`** (asignación de detecciones a casillas vía point-in-polygon)
- **`orientation.py`** (resolución de orientación / autocalibración)
- **`pipeline.py`** (orquestación M2 → M3 → `VisionInput`)
- **`camera_capture.py`** (lado receptor de M1)
- **`main.py`** (producto funcional standalone: imagen local → `VisionInput`)
- **`types.py`** (contratos internos de `chess_vision`)
- **`__init__.py`** (superficie pública del paquete)

Arquitectura: módulo Python (`chess_vision`) importado por el orquestador,
mismo proceso, mismo criterio YAGNI que `chess_brain` (M4-5). `chess_vision`
depende de `chess_brain.types` (`VisionInput`) — dependencia unidireccional.

El firmware/lado-emisor de la ESP32-CAM (M1) y el envío del `MoveResult`
a M6 quedan fuera de alcance.

## 2. Enfoque técnico

- **Detección del tablero (M2):** OpenCV clásico — umbral OTSU + Canny
  - HoughLinesP + filtrado geométrico de contornos cuadrados. Sin
    ningún modelo, sin entrenamiento.
- **Clasificación de piezas (M3):** modelo YOLOv8m ya entrenado por la
  comunidad, usado directamente vía `ultralytics`, sin fine-tuning.
- **Motivo:** evitar recolectar y etiquetar un dataset propio y
  entrenar modelos para un problema que la comunidad ya resolvió, con
  buenos resultados en producción.

Ambas técnicas están adaptadas del proyecto open-source
[`Dynamic-Chess-Board-Piece-Extraction`](https://github.com/siromermer/Dynamic-Chess-Board-Piece-Extraction)
(autor: siromermer), que es también la base de **Chesspector**, una
app publicada en Google Play — es decir, no es un experimento de
laboratorio, es una solución que ya funciona en producción para
exactamente este problema (fotos reales de tableros físicos, no
diagramas digitales).

**Un detalle de diseño interno relevante:** la detección de piezas
corre sobre la **imagen original, sin deformar** — solo se calcula la
geometría (el cuadrilátero con perspectiva real) de cada una de las
64 casillas, y se usa esa geometría para asignar cada detección a su
casilla. Deformar la imagen distorsiona la apariencia 3D de piezas
altas de forma que el modelo pretrained no espera — correr la
detección sobre la imagen tal cual la tomó la cámara da mejores
resultados y es, de nuevo, lo que hace el proyecto de referencia.

## 3. Origen y licencia — leer antes de usarlo más allá de un prototipo

- Repo de referencia: <https://github.com/siromermer/Dynamic-Chess-Board-Piece-Extraction>
- **No se encontró un archivo `LICENSE` explícito** en ese repo al
  momento de esta revisión. Sin licencia declarada, por defecto el
  autor conserva todos los derechos — el código está públicamente
  visible, pero eso no equivale a permiso de uso irrestricto (y menos
  de redistribución comercial).
- **Recomendación:** para prototipo, aprendizaje o el flujo interno de
  este proyecto, es un riesgo razonable. Si el sistema se convierte en
  un producto que se distribuye o comercializa, conviene contactar al
  autor o confirmar los términos antes.
- El propio autor documenta que el modelo de piezas **"no fue
  entrenado lo suficiente"**: la ubicación de las piezas es casi
  perfecta, pero la clasificación exacta del tipo de pieza puede
  fallar en algunos casos. Si la precisión no alcanza, el camino no es
  entrenar desde cero, sino hacer _fine-tuning incremental_ sobre este
  mismo checkpoint (ver §11) con los scripts disponibles en
  `training/*.py`.

## 4. Decisiones de diseño

| Decisión                          | Valor                                                                                                                                                                                                   |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Detección del tablero             | **OpenCV clásico**: umbral OTSU + Canny + HoughLinesP + filtrado geométrico de contornos cuadrados. Sin modelo, sin entrenamiento                                                                       |
| Clasificación de piezas           | YOLOv8m **pretrained por la comunidad** (12 clases), usado directamente vía `ultralytics`, sin fine-tuning                                                                                              |
| Origen del modelo de piezas       | `chess-model-yolov8m.pt` del repo de referencia — base de la app publicada "Chesspector". Sin licencia explícita declarada — ver §3                                                                     |
| Superficie de detección de piezas | Imagen **original**, sin deformar — solo la geometría de las 64 casillas se calcula con perspectiva corregida (`compute_square_grid`)                                                                   |
| Ancla pieza → casilla             | Punto medio-inferior (bottom-center) del bbox, contra el cuadrilátero real (con perspectiva) de cada casilla — point-in-polygon, no aritmética de grilla uniforme                                       |
| Resolución de orientación (a1/h8) | Autocalibración una vez por partida: se compara la matriz cruda contra la posición inicial estándar probando identidad y rotación de 180°; el resultado se cachea para el resto de la partida           |
| Supuesto de montaje               | La cámara puede reposicionarse entre partidas, pero se asume que no queda rotada ~90° respecto al tablero. Si esta asunción no se cumple, `orientation.py` debe extenderse a las 4 rotaciones — ver §12 |
| Manejo de incertidumbre           | Confianza por casilla explícita; umbral de negocio separado del piso de ruido del detector — error de contrato en vez de inferencia silenciosa                                                          |
| Entrenamiento                     | **No requerido** para el estado actual. Los scripts `training/*.py` quedan disponibles para fine-tuning incremental futuro si la precisión del modelo pretrained no alcanza                             |
| Arquitectura                      | Módulo Python importado, funciones puras donde es posible, modelo YOLO cargado se pasa explícitamente como parámetro (mismo patrón que `engine: SimpleEngine` en M5)                                    |

## 5. Contrato de datos

### 5.1 Tipos base

```python
RawFrame = np.ndarray  # imagen BGR cruda (H, W, 3)
Point2D = tuple[float, float]

@dataclass(frozen=True)
class BoardCorners:
    """4 esquinas extremas del tablero, en coordenadas de píxel de la
    imagen cruda. Geometría de cámara, NO todavía a1/h8."""
    top_left: Point2D
    top_right: Point2D
    bottom_left: Point2D
    bottom_right: Point2D

CameraOrientedGrid = list[list[tuple[Point2D, Point2D, Point2D, Point2D]]]
# 8x8. grid[row][col] = las 4 esquinas (top_left, top_right, bottom_right,
# bottom_left) de esa casilla, EN COORDENADAS DE LA IMAGEN ORIGINAL.

CameraOrientedMatrix = list[list[str | None]]
# 8x8, fila 0 = fila superior de la imagen. Orientación de CÁMARA,
# aún no resuelta a orientación de ajedrez.

@dataclass(frozen=True)
class PieceDetection:
    piece_code: str  # "wP","bN","bK",... — alfabeto de BoardMatrix
    bbox_px: tuple[float, float, float, float]  # x1,y1,x2,y2, en la imagen ORIGINAL
    confidence: float
```

### 5.2 Errores

```python
class VisionError(Exception):
    """Clase base de errores de contrato de chess_vision."""

class BoardNotFoundError(VisionError):
    """No se detectó un contorno de tablero válido en el frame recibido."""

class LowConfidenceDetectionError(VisionError):
    """Una o más casillas quedaron por debajo del umbral de confianza
    configurado. Incluye la lista de casillas afectadas."""

    def __init__(self, uncertain_cells: list[tuple[int, int]]):
        ...

class OrientationAmbiguousError(VisionError):
    """La matriz cruda no coincide con la posición inicial estándar en
    ninguna orientación evaluada (identidad / rotación 180°)."""
```

### 5.3 Salida hacia `chess_brain`

`VisionInput(board_matrix, side_to_move)`, definido en
`chess_brain.types`. `chess_vision` no determina `side_to_move` (no es
su responsabilidad, ni tiene forma de saberlo a partir de una sola
imagen) — se recibe como parámetro externo desde quien orqueste el turno.

## 6. Diseño interno

### 6.1 `board_detector.py` (M2)

```python
def detect_board_corners(
    frame: RawFrame,
    contour_area_range: tuple[int, int] = (2000, 20000),
    side_length_tolerance: float = 35.0,
    hough_threshold: int = 500,
    hough_min_line_length: int = 150,
    hough_max_line_gap: int = 100,
) -> BoardCorners:
    """OTSU + Canny + HoughLinesP + contornos geométricamente
    cuadrados -> esquinas extremas del tablero. Los parámetros por
    defecto son un punto de partida validado con una foto de
    referencia, no un valor universal. Lanza BoardNotFoundError si no
    hay un contorno de tablero válido."""

def compute_square_grid(
    corners: BoardCorners,
    grid_size: int = 8,
    canvas_size: int = 1200,
) -> CameraOrientedGrid:
    """Homografía hacia un lienzo plano, grilla uniforme ahí, y
    retro-proyección (homografía inversa) de las esquinas de cada
    celda al espacio de la imagen original. No deforma la imagen en
    sí — solo calcula geometría."""

def compute_homography(corners: BoardCorners, canvas_size: int = 1200) -> np.ndarray:
    """Utilidad de diagnóstico/visualización, no forma parte del
    camino de detección."""

def warp_to_topdown(frame: RawFrame, homography: np.ndarray, canvas_size: int = 1200) -> np.ndarray:
    """Utilidad de diagnóstico/visualización."""
```

### 6.2 `piece_classifier.py` (M3)

```python
COMMUNITY_YOLOV8M_CLASS_MAP: dict[str, str]  # "white-pawn" -> "wP", etc.

def detect_pieces(
    image,
    model,  # ultralytics.YOLO ya cargado (chess-model-yolov8m.pt)
    conf_threshold: float = 0.25,
    class_name_map: dict[str, str] | None = None,
) -> list[PieceDetection]:
    """Corre el modelo sobre `image` (ORIGINAL, sin deformar). Traduce
    los nombres de clase del modelo de terceros al alfabeto de
    chess_brain vía class_name_map (default: COMMUNITY_YOLOV8M_CLASS_MAP)."""
```

### 6.3 `square_mapper.py`

```python
def assign_pieces_to_grid(
    detections: list[PieceDetection],
    grid: CameraOrientedGrid,
) -> tuple[CameraOrientedMatrix, list[list[float]]]:
    """Para cada detección, ancla = bottom-center del bbox. Busca la
    celda de `grid` cuyo cuadrilátero contiene esa ancla
    (cv2.pointPolygonTest). Colisiones: se conserva mayor confidence."""

def check_confidence(confidences: list[list[float]], threshold: float) -> None:
    """Recorre la matriz de confidence; si alguna celda está por
    debajo de `threshold`, lanza LowConfidenceDetectionError con la
    lista de celdas afectadas."""
```

### 6.4 `orientation.py`

```python
STANDARD_START_MATRIX: BoardMatrix  # posición inicial estándar de ajedrez, constante del módulo

def resolve_orientation(
    camera_matrix: CameraOrientedMatrix,
) -> Literal["identity", "rotated_180"]:
    """Se usa una única vez, al iniciar una partida (tablero en
    posición inicial). Compara camera_matrix contra
    STANDARD_START_MATRIX probando identidad y rotación 180°. Retorna
    la orientación que coincide. Lanza OrientationAmbiguousError si
    ninguna coincide."""

def apply_orientation(
    camera_matrix: CameraOrientedMatrix,
    orientation: Literal["identity", "rotated_180"],
) -> BoardMatrix:
    """Aplica la rotación ya resuelta. Función pura, sin estado."""
```

La resolución de orientación es independiente de cómo se detectó el
tablero, por lo que su lógica no depende del método usado en M2/M3.

### 6.5 `pipeline.py`

```python
def locate_board(
    frame: RawFrame,
    corner_detection_kwargs: dict | None = None,
    grid_size: int = 8,
) -> tuple[BoardCorners, CameraOrientedGrid]:
    """Paso de M2 aislado — expuesto por separado para depuración
    visual (usado directamente por main.py)."""

def calibrate_orientation(
    frame: RawFrame,
    piece_model,
    corner_detection_kwargs: dict | None = None,
) -> Orientation:
    """Una única vez por partida, con tablero en posición inicial."""

def process_frame(
    frame: RawFrame,
    piece_model,
    orientation: Orientation,
    side_to_move: Literal["w", "b"],
    confidence_threshold: float = 0.5,
    corner_detection_kwargs: dict | None = None,
) -> VisionInput:
    """Punto de entrada único del subsistema. Orquesta:
    locate_board → detect_pieces → assign_pieces_to_grid →
    check_confidence → apply_orientation → VisionInput. Lanza
    BoardNotFoundError o LowConfidenceDetectionError según
    corresponda; nunca retorna una matriz con casillas inciertas
    silenciadas."""
```

### 6.6 `camera_capture.py`

```python
def fetch_frame(esp32_cam_url: str, timeout: float = 5.0) -> RawFrame:
    """Descarga un frame JPEG desde el endpoint HTTP de la ESP32-CAM y
    lo decodifica (cv2.imdecode) a RawFrame. Lanza VisionError si falla
    la conexión o la decodificación. Cubre solo el lado receptor
    (laptop) de M1 — el firmware de la ESP32-CAM queda fuera de
    alcance."""
```

### 6.7 `main.py` — Producto funcional standalone

Análogo al `main.py` de `chess_brain` (M4-5): toma una imagen local,
corre el pipeline completo, imprime en consola cada etapa.

**Argumentos:**

| Argumento                | Requerido | Default                         | Descripción                                                                     |
| ------------------------ | --------- | ------------------------------- | ------------------------------------------------------------------------------- |
| `--image`                | No        | `test_tablero.jpg`              | Ruta a la imagen local del tablero                                              |
| `--model`                | No        | `models/chess-model-yolov8m.pt` | Ruta al modelo de piezas                                                        |
| `--side-to-move`         | No        | `w`                             | `w`/`b`                                                                         |
| `--orientation`          | No        | `identity`                      | Orientación fija a usar (ignorado si `--calibrate`)                             |
| `--calibrate`            | No        | —                               | Trata la imagen como posición inicial y resuelve la orientación automáticamente |
| `--confidence-threshold` | No        | `0.5`                           | Umbral de negocio para `check_confidence`                                       |

**Salida impresa (en orden):** dimensiones e info de la imagen de
entrada → esquinas y grilla detectadas por M2 → conteo de detecciones
crudas y mapeadas de M3 → `VisionInput` final (tablero ASCII +
estructura de datos exacta, `repr`-eable).

Ver §9 para ejemplos de invocación desde la terminal.

### 6.8 `__init__.py` — Superficie pública

```python
from chess_vision.pipeline import calibrate_orientation, locate_board, process_frame
from chess_vision.types import (
    VisionError, BoardNotFoundError, LowConfidenceDetectionError, OrientationAmbiguousError,
)
```

`locate_board` forma parte de la superficie pública porque `main.py` y
la depuración visual lo necesitan directamente. Igual que en
`chess_brain`, este es el único contrato que un futuro Orquestador
(M10) debería asumir estable.

## 7. Estructura del proyecto

```structure
chess-robot-arm/
├── src/
│   ├── chess_brain/                  # M4-5 (implementado)
│   └── chess_vision/                  # M2-3 (implementado)
│       ├── __init__.py
│       ├── types.py
│       ├── board_detector.py          # M2 — OpenCV clásico
│       ├── piece_classifier.py        # M3 — modelo pretrained
│       ├── square_mapper.py
│       ├── orientation.py
│       ├── pipeline.py
│       ├── camera_capture.py
│       └── models/
│           └── chess-model-yolov8m.pt # descargado por el usuario, no versionado en git
├── main.py                            # producto funcional standalone M2+M3
├── training/                          # scripts de fine-tuning incremental — no requeridos para el estado actual
│   ├── train_board_detector.py        # no aplica al enfoque actual de M2 (ver §2)
│   └── train_piece_classifier.py      # útil para fine-tuning incremental si hace falta
└── tests/
    ├── test_board_detector.py         # incluye foto real de referencia
    ├── test_piece_classifier.py
    ├── test_square_mapper.py
    ├── test_orientation.py
    ├── test_pipeline.py
    └── fixtures/
        ├── fake_yolo.py
        └── sample_board.jpeg          # foto real, tomada del repo de referencia
```

_(`train_board_detector.py` queda documentado como no aplicable al
enfoque actual de M2; se conserva por si en el futuro se decide volver
a un enfoque con ML para esa parte.)_

## 8. Setup del proyecto (Windows 11 + uv)

### 8.1 Instalar dependencias

```powershell
cd chess-robot-arm
uv add ultralytics opencv-python numpy requests
```

No se requiere Colab ni entrenamiento para el estado actual.

### 8.2 Descargar el modelo de piezas

El archivo de pesos (`chess-model-yolov8m.pt`, ~52 MB) está en el repo
de referencia vía **Git LFS**. Descargarlo con un enlace "raw" normal
no funciona (devuelve un puntero de texto, no el archivo real). Dos
formas que sí funcionan:

**Opción A — clonar el repo (recomendada si tienes `git lfs`):**

```powershell
git lfs install
git clone https://github.com/siromermer/Dynamic-Chess-Board-Piece-Extraction.git
# el archivo real queda en Dynamic-Chess-Board-Piece-Extraction/chess-model-yolov8m.pt
```

**Opción B — descarga manual desde el navegador:**
Abre el archivo en GitHub (`chess-model-yolov8m.pt` dentro del repo) y
usa el botón de descarga de la interfaz web — a diferencia de un link
`raw.githubusercontent.com`, el botón de la UI sí resuelve Git LFS
correctamente.

Luego copia el archivo a:

```text
src/chess_vision/models/chess-model-yolov8m.pt
```

## 9. Cómo correr el producto standalone

```powershell
uv run python main.py --image test_tablero.jpg --model src/chess_vision/models/chess-model-yolov8m.pt
```

Si la foto que usas es la posición inicial de una partida, puedes
pedir que la orientación se resuelva sola en vez de asumir `identity`:

```powershell
uv run python main.py --image test_tablero.jpg --model src/chess_vision/models/chess-model-yolov8m.pt --calibrate
```

`main.py` imprime, en orden: la imagen de entrada y sus dimensiones,
las esquinas del tablero detectadas, cuántas piezas detectó el modelo
y cuántas quedaron mapeadas a una casilla, y finalmente el
`VisionInput` completo (tablero ASCII + estructura de datos exacta).

**Primer paso recomendado con hardware/fotos propias:** correr
`main.py` con una foto real y mirar el conteo de piezas detectadas vs.
mapeadas, para tener una primera impresión de qué tan bien generaliza
el modelo pretrained al tablero específico del usuario (ver §10).

## 10. Plan de pruebas y estado de validación

**Estado: implementado, 22/22 tests pasando** (incluye una foto real
de tablero como fixture, no solo datos sintéticos).

| Archivo                    | Casos clave                                                                                                                                         |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_board_detector.py`   | Esquinas detectadas sobre foto real; `BoardNotFoundError` en imagen sin tablero; forma y contigüidad de la grilla de 64 casillas                    |
| `test_piece_classifier.py` | Traducción de nombres de clase del modelo de terceros a nuestro alfabeto; filtrado por confianza; bbox como floats planos (no tensores)             |
| `test_square_mapper.py`    | Asignación correcta vía point-in-polygon con ancla bottom-center; pieza fuera del tablero descartada; colisión resuelta por mayor confidence        |
| `test_orientation.py`      | Identidad, rotación 180° y caso ambiguo (`OrientationAmbiguousError`)                                                                               |
| `test_pipeline.py`         | Integración completa usando la geometría de una foto real + detecciones sintéticas controladas — reproduce la posición inicial estándar exactamente |

### Qué quedó validado en esta revisión, y qué no

| Componente                                                                          | Validación                                                                                                                                                                                                                                                                       |
| ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Detección clásica del tablero (M2)                                                  | Probada end-to-end con una foto real de tablero (tomada del propio repo de referencia) — 22/22 tests pasando, incluida geometría con perspectiva real                                                                                                                            |
| Forma de la API de `ultralytics` (`box.conf`, `box.cls`, `box.xyxy`, `model.names`) | Verificada contra un modelo YOLO real (no de ajedrez) — confirma que el código consume la interfaz correctamente                                                                                                                                                                 |
| Modelo de piezas real (`chess-model-yolov8m.pt`)                                    | **No se pudo descargar en el entorno de validación** (Git LFS bloqueado por restricciones de red del sandbox) — la lógica de traducción de clases y mapeo a casillas está probada con un modelo simulado, pero la precisión real del modelo en fotos del usuario queda pendiente |

## 11. Si la precisión no alcanza

- Ajusta los parámetros de `detect_board_corners` (`contour_area_range`,
  `hough_threshold`, etc.) — están calibrados para una foto de
  referencia, no para la tuya necesariamente.
- Si el modelo confunde tipos de pieza de forma sistemática (no
  posiciones, sino qué pieza es), considera el fine-tuning incremental
  mencionado en §3 con los scripts disponibles en `training/` — no
  hace falta empezar de cero.

## 12. Pendiente (fuera de alcance de este documento)

- Validar la precisión real del modelo de piezas pretrained con fotos
  del tablero/cámara reales del usuario (no hecho en esta revisión).
- Confirmar términos de licencia del modelo/código de terceros antes
  de cualquier uso más allá de prototipo (ver §3).
- Ajuste fino de los parámetros de `detect_board_corners` según la
  cámara/distancia/iluminación reales (los valores por defecto son un
  punto de partida, no una calibración final).
- Fine-tuning incremental del modelo de piezas (scripts ya disponibles
  en `training/`) si la clasificación de tipo de pieza no alcanza la
  precisión necesaria.
- Manejo de piezas capturadas que queden dentro del encuadre pero
  fuera del área de las 64 casillas.
- Política de reintento ante `BoardNotFoundError` /
  `LowConfidenceDetectionError` (¿recapturar automáticamente? ¿cuántas
  veces?) — corresponde al Orquestador (M10).
- Validación de la asunción "cámara no rotada ~90°"; si se viola,
  `orientation.py` debe extenderse a las 4 rotaciones, no solo 0°/180°.
- Latencia real del pipeline en CPU — no medida todavía.
- Robustez ante iluminación variable (luz ambiente, sombra proyectada
  por el brazo sobre el tablero durante su propio movimiento).
- Firmware/lado-emisor de la ESP32-CAM (M1) — sigue fuera de alcance.

## 13. Ajustes durante la implementación

`detect_pieces` usa un umbral de confianza bajo ("piso de ruido")
dentro del pipeline, distinto del umbral real de decisión que usa
`check_confidence`. Si se usara un solo umbral, una pieza detectada
con confianza baja simplemente desaparecía antes de llegar a la
matriz, y la casilla se reportaba como "vacía, 100% segura" —
exactamente la incertidumbre que el diseño quería exponer, no ocultar.
Queda documentado en el código (`piece_classifier.py` y `pipeline.py`).
