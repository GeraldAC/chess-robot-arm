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
| 0   | Calibración                  | Mapeo píxel ↔ casilla ↔ coordenada del brazo                        | Implementado |
| 1   | Captura de imagen            | ESP32-CAM obtiene el frame y lo envía a la laptop                   | Pendiente    |
| 2   | Detección del tablero        | Localización de las 64 casillas (OpenCV clásico)                    | Implementado |
| 3   | Clasificación de piezas      | Identificación de tipo/color por casilla (YOLOv8m pretrained)       | Implementado |
| 4   | Estado del juego             | `chess.Board` autoritativo, inferencia de jugada humana, validación | Implementado |
| 5   | Motor de decisión            | Cálculo de la mejor jugada vía Stockfish                            | Implementado |
| 6   | Planificación de movimiento  | Traducción de la jugada a acciones físicas                          | Implementado |
| 7   | Cinemática inversa           | Coordenadas cartesianas → ángulos de articulaciones                 | Implementado |
| 8   | Control de actuadores        | Ejecución de trayectoria y control de pinza                         | Implementado |
| 9   | Verificación post-movimiento | Confirmación del estado físico contra el esperado                   | Pendiente    |
| 10  | Orquestador / comunicación   | Coordinación del ciclo completo entre dispositivos                  | Pendiente    |

Documentación detallada por subsistema:

- `SPEC` — chess_calibration (Módulo 0): calibración física del brazo (casilla/zona ↔ coordenada cartesiana).
- `SPEC` — chess_vision (Módulos 2-3): detección del tablero y clasificación de piezas.
- `SPEC` — chess_brain (Módulos 4-5): estado del juego y motor de decisión.
- `SPEC` — chess_planner (Módulo 6): planificación de movimiento físico.
- `SPEC` — chess_kinematics (Módulo 7): cinemática inversa y trayectoria fina.
- `SPEC` — chess_actuators (Módulo 8): protocolo Serial Host↔Arduino, calibración física de servos y ejecución de trayectoria.
- `SPEC` general: alcance, contratos entre módulos y decisiones transversales.

## Hardware

- Tablero de ajedrez clásico, piezas físicas estándar.
- ESP32-CAM para captura de imágenes del tablero.
- Brazo robótico con pinza, controlado por Arduino UNO + PCA9685 vía Serial/USB (ver `BOM.md` §4 y `M8_SPEC.md` §2.1).
- Laptop (Windows 11): ejecuta Visión, Motor de Decisión y Orquestador.

## Estructura del proyecto

```text
chess-robot-arm/
├── pyproject.toml
├── README.md
├── .python-version
├── src/
│   ├── chess_brain/        # M4-5: estado del juego, motor de decisión, CLI
│   ├── chess_vision/       # M2-3: detección de tablero, clasificación de piezas
│   ├── chess_planner/      # M6: planificación de movimiento físico
│   ├── chess_calibration/  # M0: calibración física del brazo
│   ├── chess_kinematics/   # M7: cinemática inversa y trayectoria fina
│   └── chess_actuators/    # M8: control de actuadores, protocolo Serial
├── firmware/
│   └── chess_arm_controller/  # firmware Arduino (fuera de src/, no lo gestiona uv)
├── tests/
│   ├── test_brain/
│   ├── test_vision/
│   ├── test_planner/
│   ├── test_calibration/
|   ├── test_kinematics/
|   └── test_actuators/
└── .gitignore
```

## Requisitos previos

- Python 3.11
- [uv](https://docs.astral.sh/uv/) para gestión de proyecto y dependencias
- Binario de Stockfish para Windows ([descarga oficial](https://stockfishchess.org/download/))
- Peso del modelo YOLOv8 ([descarga oficial](https://github.com/siromermer/Dynamic-Chess-Board-Piece-Extraction/blob/main/chess-model-yolov8m.pt))
- Arduino IDE (o `arduino-cli`) + librería "Adafruit PWM Servo Driver Library", para compilar y cargar `firmware/chess_arm_controller/chess_arm_controller.ino`

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

Cargar el firmware del brazo (`firmware/chess_arm_controller/chess_arm_controller.ino`)
al Arduino UNO desde el Arduino IDE o `arduino-cli` — solo es necesario
una vez, o cada vez que cambie el firmware.

Colocar el archivo de calibración física de servos (ver `M8_SPEC.md`
§6) en:

```text
src/chess_actuators/servo_calibration.yaml
```

A diferencia de la sesión de calibración de M0, este archivo no se
regenera por partida: es una propiedad del hardware del brazo (ver
`M8_SPEC.md` §2.4).

## Uso

Jugar una partida completa contra Stockfish desde terminal (sin
depender de Visión ni del brazo físico):

```powershell
uv run chess-brain
```

Ejecutar el pipeline de visión sobre una imagen local:

```powershell
uv run chess-vision --plot
```

Ejecutar calibración sobre una muestra:

```powershell
uv run chess-calibration --plot
```

Ejecutar el control de actuadores sobre una trayectoria de prueba, sin
hardware real:

```powershell
uv run chess-actuators --simulate --calibration src/chess_actuators/servo_calibration.yaml --trajectory <ruta-a-trayectoria.json>
```

Contra el brazo físico:

```powershell
uv run chess-actuators --port COM3 --calibration src/chess_actuators/servo_calibration.yaml --trajectory <ruta-a-trayectoria.json>
```

## Pruebas

```powershell
uv run poe chess-test-brain
uv run poe chess-test-vision
uv run poe chess-test-planner
uv run poe chess-test-calibration
uv run poe chess-test-kinematics
uv run poe chess-test-actuators
uv run poe chess-test
```

Alternativamente:

```powershell
uv run pytest --cov
```

## Estado del proyecto

Los módulos 0 y 2 a 8 (calibración, visión, motor de decisión,
planificación de movimiento, cinemática inversa y control de
actuadores) están implementados y validados mediante simuladores y
pruebas automatizadas. Los módulos 1, 9 y 10 (captura de imagen,
verificación post-movimiento y orquestación) están pendientes de
diseño e implementación.

### Limitaciones conocidas

- La precisión del modelo de piezas no ha sido validada aún con
  hardware y fotografías reales del tablero físico.
- El protocolo de comunicación entre ESP32-CAM y la laptop (M1) no
  está definido. El protocolo laptop↔controlador del brazo sí quedó
  definido e implementado en M8 (Serial/USB, ver `M8_SPEC.md` §3).
- M6 asume 4 zonas físicas nuevas (bandejas de descarte, reserva de
  piezas para promoción). M0 ya define cómo medirlas y resolverlas a
  coordenadas del brazo (`CalibrationMap`), pero falta ejecutar el
  protocolo de medición manual (`M0_SPEC.md` §4) sobre el hardware
  físico definitivo — no se ha hecho aún.
- M7 asume una convención de montaje de la pinza (eje de aproximación =
  eje Z del frame 6 del D-H) que no se ha podido verificar contra el
  hardware real. `SAFE_TRAVEL_HEIGHT_MM` y las tolerancias de posición/
  inclinación (`M7_SPEC.md` §7) son también placeholders a medir.
- Validado con datos de ejemplo: una geometría de tablero puede ser
  válida (`validate_board_geometry`, M0) y aun así quedar fuera del
  alcance físico del brazo (~355 mm, `BOM.md` §3) — se recomienda
  verificar el radio de las 4 esquinas antes de ejecutar la calibración
  completa.
- La calibración física de los 6 servos del brazo (ángulo↔pulso PWM
  por canal, `chess_actuators`) no ha sido medida sobre hardware real
  — ver `M8_SPEC.md` §2.4 y §6.
- El Arduino UNO se reinicia por defecto al abrirse la conexión Serial
  (toggle de DTR), lo que apaga los canales PWM hasta el primer
  comando — puede soltar una pieza sostenida si ocurre a mitad de
  sesión. Mitigación de hardware pendiente — ver `M8_SPEC.md` §3, §9.
- `max_joint_speed_deg_s`, `gripper_settle_s` y `first_move_settle_s`
  (`chess_actuators`) son placeholders conservadores sin validar
  contra los servos MG996R reales — ver `M8_SPEC.md` §9.
