# Brazo Robótico para Ajedrez

![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![uv](https://img.shields.io/badge/deps-uv-DE5FE9?logo=uv&logoColor=white)
![OpenCV](https://img.shields.io/badge/vision-OpenCV-5C3EE8?logo=opencv&logoColor=white)
![Ultralytics YOLOv8](https://img.shields.io/badge/model-YOLOv8m-00FFFF?logo=yolo&logoColor=black)
![python-chess](https://img.shields.io/badge/chess-python--chess-769656?logo=chessdotcom&logoColor=white)
![Stockfish](https://img.shields.io/badge/engine-Stockfish-black?logo=stockfish&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Status](https://img.shields.io/badge/status-en%20desarrollo-yellow)
![Platform](https://img.shields.io/badge/OS-Windows%2011-0078D6?logo=windows&logoColor=white)

## Descripción

Sistema robótico capaz de jugar una partida de ajedrez completa contra un
humano sobre un tablero físico. El sistema percibe el estado del tablero
mediante visión artificial, calcula la mejor jugada de respuesta con un
motor de ajedrez, y la ejecuta físicamente mediante un brazo robótico
con pinza.

## Arquitectura

El sistema se compone de diez módulos, coordinados por un orquestador
central. La comunicación entre módulos sigue contratos de datos
explícitos y tipados.

| #   | Módulo                       | Responsabilidad                                                     | Estado       |
| --- | ---------------------------- | ------------------------------------------------------------------- | ------------ |
| 0   | Calibración                  | Mapeo píxel ↔ casilla ↔ coordenada del brazo                        | Pendiente    |
| 1   | Captura de imagen            | ESP32-CAM obtiene el frame y lo envía a la laptop                   | Pendiente    |
| 2   | Detección del tablero        | Localización de las 64 casillas (OpenCV clásico)                    | Implementado |
| 3   | Clasificación de piezas      | Identificación de tipo/color por casilla (YOLOv8m pretrained)       | Implementado |
| 4   | Estado del juego             | `chess.Board` autoritativo, inferencia de jugada humana, validación | Implementado |
| 5   | Motor de decisión            | Cálculo de la mejor jugada vía Stockfish                            | Implementado |
| 6   | Planificación de movimiento  | Traducción de la jugada a acciones físicas                          | Pendiente    |
| 7   | Cinemática inversa           | Coordenadas cartesianas → ángulos de articulaciones                 | Pendiente    |
| 8   | Control de actuadores        | Ejecución de trayectoria y control de pinza                         | Pendiente    |
| 9   | Verificación post-movimiento | Confirmación del estado físico contra el esperado                   | Pendiente    |
| 10  | Orquestador / comunicación   | Coordinación del ciclo completo entre dispositivos                  | Pendiente    |

Documentación detallada por subsistema:

- `SPEC` — chess_vision (Módulos 2-3): detección del tablero y clasificación de piezas.
- `SPEC` — chess_brain (Módulos 4-5): estado del juego y motor de decisión.
- `SPEC` general: alcance, contratos entre módulos y decisiones transversales.

## Hardware

- Tablero de ajedrez clásico, piezas físicas estándar.
- ESP32-CAM para captura de imágenes del tablero.
- Brazo robótico con pinza (controlador físico dedicado aún no definido).
- Laptop (Windows 11): ejecuta Visión, Motor de Decisión y Orquestador.

## Estructura del proyecto

```text
chess-robot-arm/
├── pyproject.toml
├── README.md
├── .python-version
├── src/
│   ├── chess_brain/       # M4-5: estado del juego, motor de decisión, CLI
│   └── chess_vision/      # M2-3: detección de tablero, clasificación de piezas
├── tests/
│   ├── test_brain/
│   └── test_vision/
└── .gitignore
```

## Requisitos previos

- Python 3.11
- [uv](https://docs.astral.sh/uv/) para gestión de proyecto y dependencias
- Binario de Stockfish para Windows ([descarga oficial](https://stockfishchess.org/download/))
- Peso del modelo YOLOv8 ([descarga oficial](https://github.com/siromermer/Dynamic-Chess-Board-Piece-Extraction/blob/main/chess-model-yolov8m.pt))

## Instalación

```powershell
uv sync
```

Colocar el binario de Stockfish en:

```text
src/chess_brain/engine_binaries/stockfish.exe
```

Descargar el modelo de piezas (`chess-model-yolov8m.pt`, vía Git LFS) y
colocarlo en:

```text
src/chess_vision/models/chess-model-yolov8m.pt
```

## Uso

Jugar una partida completa contra Stockfish desde terminal (sin
depender de Visión ni del brazo físico):

```powershell
uv run chess-brain
```

Ejecutar el pipeline de visión sobre una imagen local:

```powershell
uv run chess-vision
```

## Pruebas

```powershell
uv run poe chess-test-brain
uv run poe chess-test-vision
uv run poe chess-test
```

Alternativamente:

```powershell
uv run pytest --cov
```

## Estado del proyecto

Los módulos 2 a 5 (visión y motor de decisión) están implementados y
validados de punta a punta mediante simuladores y pruebas automatizadas.
Los módulos 6 a 10 (planificación de movimiento, cinemática inversa,
control de actuadores, verificación y orquestación) están pendientes de
diseño e implementación.

### Limitaciones conocidas

- La precisión del modelo de piezas no ha sido validada aún con
  hardware y fotografías reales del tablero físico.
- El protocolo de comunicación entre ESP32-CAM, laptop y controlador
  del brazo no está definido.

## Licencia

MIT
