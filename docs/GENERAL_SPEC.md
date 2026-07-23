# SPEC General — Proyecto Brazo Robótico para Ajedrez

## 1. Objetivo

Sistema robótico capaz de jugar una partida de ajedrez completa contra un
humano sobre un tablero físico: percibe el estado del tablero mediante
visión artificial, calcula la mejor jugada de respuesta, y la ejecuta
físicamente mediante un brazo robótico con pinza.

## 2. Alcance y hardware

**Hardware:**

- Tablero de ajedrez clásico, piezas físicas estándar.
- ESP32-CAM para captura de imágenes del tablero.
- Brazo robótico con pinza (gripper), controlado por Arduino UNO +
  PCA9685 vía Serial/USB — definido e implementado en M8, ver
  `M8_SPEC.md` §2.1.
- Laptop (Windows 11): ejecuta Visión, Motor de Decisión y Orquestador.

**Entorno de desarrollo:**

- Python 3.11
- VSCode
- `uv` (gestión de proyecto y dependencias)

## 3. Arquitectura general — Módulos del sistema

| #   | Módulo                       | Responsabilidad                                                                                               | Estado                                                                                                         | Spec de referencia            |
| --- | ---------------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| 0   | Calibración                  | Mapeo píxel ↔ casilla ↔ coordenada del brazo                                                                  | **Implementado**                                                                                               | SPEC — chess_calibration (M0) |
| 1   | Captura de imagen            | ESP32-CAM obtiene el frame y lo envía a la laptop                                                             | Pendiente                                                                                                      | —                             |
| 2   | Detección del tablero        | Localizar las 64 casillas en la imagen                                                                        | **Implementado** (detección clásica con OpenCV, sin ML — ver nota al final de esta sección)                    | SPEC — chess_vision (M2-3)    |
| 3   | Clasificación de piezas      | Identificar tipo/color de pieza por casilla                                                                   | **Implementado** (modelo pretrained de terceros, sin entrenamiento propio — ver nota al final de esta sección) | SPEC — chess_vision (M2-3)    |
| 4   | Estado del juego             | Mantener el `chess.Board` autoritativo, inferir la jugada humana desde la matriz de Visión, validar legalidad | **Implementado**                                                                                               | SPEC — chess_brain (M4-5)     |
| 5   | Motor de decisión            | Calcular la mejor jugada vía Stockfish                                                                        | **Implementado**                                                                                               | SPEC — chess_brain (M4-5)     |
| 6   | Planificación de movimiento  | Traducir la jugada en una secuencia de acciones físicas (normal / captura / enroque / promoción)              | **Implementado**                                                                                               | SPEC — chess_planner (M6)     |
| 7   | Cinemática inversa           | Coordenadas cartesianas → ángulos de articulaciones                                                           | **Implementado**                                                                                               | SPEC — chess_kinematics (M7)  |
| 8   | Control de actuadores        | Ejecutar trayectoria + control de pinza (alturas de aproximación, apertura/cierre)                            | **Implementado**                                                                                               | SPEC — chess_actuators (M8)   |
| 9   | Verificación post-movimiento | Confirmar que el tablero físico coincide con el estado esperado                                               | Pendiente                                                                                                      | —                             |
| 10  | Orquestador / comunicación   | Coordinar el ciclo completo y la comunicación entre dispositivos                                              | Pendiente                                                                                                      | —                             |

> Nota: dentro de M4-5 existen además mini-módulos de interfaz (Entrada,
> Salida, simulador de Visión, presentación en consola, CLI de producto)
> ya implementados. Se documentan en el SPEC de chess_brain, no aquí, para
> no duplicar contrato.

---

> **M2/M3 no usan modelos entrenados por este proyecto.** M2 es
> geometría clásica (OpenCV); M3 usa un modelo YOLOv8m pretrained de
> un proyecto comunitario open-source, sin fine-tuning. Ver
> `M2_M3_SPEC.md`, para el detalle y la advertencia
> de licencia del modelo de terceros (sin licencia explícita
> declarada en su repositorio de origen — revisar antes de cualquier
> uso más allá de prototipo).

## 4. Contratos entre módulos

### 4.1 Definidos y estables

- **`VisionInput`** (M2/M3 → M4): matriz 8x8 (`BoardMatrix`, códigos
  `"wP"`, `"bK"`, `None`, etc.) + `side_to_move`.
- **`MoveResult`** (M4/M5 → M6): jugada resultante con metadatos completos
  (captura, enroque, captura al paso, promoción, FEN, estado del juego).
- **`IllegalStateError`, `EngineError`**: errores de contrato explícitos —
  el Orquestador debe manejarlos como señales de flujo, no como fallos
  silenciosos.
- **`BoardCorners`, `CameraOrientedGrid`** (M2 → M3, internos a
  `chess_vision`): geometría del tablero detectado, con perspectiva real
  preservada por casilla. No son parte del contrato hacia `chess_brain`
  (eso sigue siendo `VisionInput`), pero quedan documentados como
  estables dentro de `chess_vision`.
- **`PhysicalPlan`** (M6 → M7): secuencia ordenada de `PieceTransfer`
  (origen, destino, pieza, color). Origen/destino pueden ser casillas
  del tablero o zonas simbólicas (`Zone`: `DISCARD_WHITE/BLACK`,
  `SPARE_WHITE/BLACK`).
- **`CalibrationMap`** (M0 → M7): `dict[Location, ArmPoint]` con las 64
  casillas más las 4 `Zone` de `chess_planner`, resueltas a coordenadas
  cartesianas del brazo vía medición manual.
- **`ArmTrajectory`** (M7 → M8): secuencia ordenada de `ArmWaypoint`
  (ángulos de las 5 articulaciones activas + acción de pinza + tipo de
  waypoint `TRANSIT`/`GRASP`). Resuelve el pendiente "M7 → M8: formato
  de ángulos de articulación / trayectoria" de la versión anterior de
  este documento.
- **`ExecutionReport`** (M8 → M9): resumen de qué `ArmWaypoint` se
  enviaron y confirmó el microcontrolador durante la ejecución de una
  `ArmTrajectory`. Resuelve parcialmente el pendiente "M8 → M9: formato
  del estado físico verificado" — NO es verificación física real; M9
  sigue siendo responsable de comparar el tablero físico contra el
  estado esperado vía visión.

Detalle completo de estos contratos en **SPEC — chess_brain (Módulos 4-5)**, **SPEC — chess_vision (Módulos 2-3)**, **SPEC — chess_planner (Módulo 6)**, **SPEC — chess_calibration (Módulo 0)**, **SPEC — chess_kinematics (Módulo 7)** y **SPEC — chess_actuators (Módulo 8)**.

### 4.2 Pendientes de definir

> Nota: formato de salida M2→M3 y manejo de incertidumbre en M3
> quedaron resueltos — ver `M2_M3_SPEC.md` (point-in-polygon + confianza
> por casilla con umbral de negocio separado del piso de ruido del detector).

- Validar la precisión real del pipeline M2-3 con hardware y tablero
  físico reales (no se pudo ejecutar con el modelo de piezas real en
  el entorno de desarrollo asistido — ver
  `M2_M3_SPEC.md`).
- Confirmar licencia del modelo de piezas de terceros antes de
  cualquier despliegue más allá de prototipo/uso personal.
- M9 debe definir cómo compara el estado físico verificado (vía
  visión) contra el `ExecutionReport`/estado esperado, y qué hace el
  Orquestador ante una discrepancia — la estructura de `ExecutionReport`
  (M8) ya está definida, pero no reemplaza la verificación real.
- M10: protocolo de comunicación entre ESP32-CAM y la laptop (WiFi/HTTP
  — no decidido aún). El protocolo laptop↔controlador del brazo ya
  quedó resuelto en M8 (Serial/USB).

## 5. Decisiones arquitectónicas transversales

- **Proceso único, módulos importados**: M4-5 se implementaron como
  paquete Python importado en el mismo proceso (no microservicio), bajo
  criterio YAGNI. Se recomienda mantener el mismo criterio para M2-3 y
  M6-9 mientras no exista necesidad real de distribuir carga entre
  dispositivos físicos.
- **M10 como punto de decisión de distribución física**: es el módulo
  natural para decidir qué corre en la ESP32-CAM (captura) vs. qué corre
  en la laptop (clasificación, decisión, orquestación). Diseño pendiente.
- **Gestión de dependencias**: `uv`. Testing: `pytest` + `pytest-cov`.
- **Reutilización antes que entrenamiento propio**: para M2 y M3 se
  priorizó adoptar soluciones ya resueltas por la comunidad (geometría
  clásica + modelo pretrained) en vez de recolectar dataset y entrenar
  desde cero. Se recomienda aplicar el mismo criterio a futuros módulos
  de percepción antes de asumir que hace falta entrenar algo propio —
  mismo espíritu YAGNI ya declarado para la arquitectura de proceso
  único.
- **Excepción al patrón mono-lenguaje**: M8 es el primer módulo que no
  es puro Python — incluye un firmware C/C++ para el Arduino
  (`firmware/chess_arm_controller/`), fuera de `src/` y fuera del
  alcance de `uv`. El contrato Python (`chess_actuators`) sigue las
  mismas convenciones que el resto del proyecto; el firmware se rige
  por el protocolo Serial documentado en `M8_SPEC.md` §3, no por
  `pytest`.

## 6. Estado actual y siguiente enfoque

- **M0 (Calibración)** implementado (`chess_calibration`): resuelve
  `Location -> ArmPoint` (64 casillas + 4 zonas) a partir de medición
  manual del tablero y las zonas físicas, con validación de geometría
  y persistencia de sesión (recalibración una vez por partida). Cubierto
  con 28 tests. Ver SPEC — chess_calibration (Módulo 0).
- **M2 (Detección del tablero)** y **M3 (Clasificación de piezas)**
  implementados sobre soluciones ya existentes de la comunidad (sin
  entrenamiento propio), con un producto funcional standalone
  (`vision_main.py`) que corre el pipeline completo sobre una imagen local y
  muestra entrada/salida exactas. Pendiente de validación con hardware
  y tablero físico reales por parte del usuario.
- **M4 (Estado del Juego)** y **M5 (Motor de Decisión)** implementados
  y validados end-to-end con Stockfish real, incluyendo un CLI funcional
  para jugar partidas completas sin depender de Visión real.
- **M6 (Planificación de Movimiento)** implementado (`chess_planner`):
  traduce `MoveResult` a `PhysicalPlan` para movimiento normal, captura,
  enroque, captura al paso y promoción (política "solo Dama"). Cubierto
  con 15 tests. Ver SPEC — chess_planner (Módulo 6).
- **M7 (Cinemática Inversa)** implementado (`chess_kinematics`):
  resuelve IK vía Evolución Diferencial (una vez por sesión, cacheada en
  `JointMap`) y traduce `PhysicalPlan` a `ArmTrajectory` (waypoints con
  altura de tránsito segura). Cubierto con 21 tests. Ver SPEC —
  chess_kinematics (Módulo 7).
- **M8 (Control de Actuadores)** implementado (`chess_actuators`):
  traduce `ArmTrajectory` a comandos Serial hacia Arduino UNO + PCA9685
  (protocolo en `M8_SPEC.md` §3), sin interpolación fina — temporización
  a nivel de waypoint — y con reintentos acotados + congelamiento en
  sitio ante fallos de comunicación. Incluye firmware de referencia
  (`firmware/chess_arm_controller/`). Cubierto con 44 tests. Ver SPEC —
  chess_actuators (Módulo 8).
- **Siguiente enfoque:** con M0 y M2-8 cubiertos (calibración física →
  imagen → posición → jugada → plan físico simbólico → ángulos de
  articulación → ejecución física sobre el brazo), el cuello de botella
  pasa a ser **Módulo 9 (Verificación post-movimiento)**: ya tiene un
  contrato de entrada cerrado (`ExecutionReport`, M8 → M9) contra el
  cual diseñarse, aunque sigue dependiendo de M2-3 (Visión) para
  comparar el tablero físico real contra el estado esperado.

## 7. Pendientes generales del proyecto

- Definir protocolo de comunicación entre ESP32-CAM y la laptop (M1
  → M10) — el protocolo laptop↔controlador del brazo ya quedó resuelto
  en M8.
- Definir política de color/`side_to_move` del robot para el primer
  movimiento de una partida (decisión de producto, no solo técnica).
- Definir manejo de desincronización cuando Verificación (M9) detecte que
  el estado físico no coincide con lo esperado.
- Ejecutar el protocolo de medición física de M0 (`M0_SPEC.md` §4) con
  el tablero, las zonas y el brazo reales — el mecanismo ya existe,
  falta la medición sobre el hardware definitivo. Al medir, verificar
  además que las 4 esquinas queden dentro del radio de alcance del
  brazo (~355 mm, `BOM.md` §3): `chess_kinematics` (M7) ya lo detecta
  como `UnreachableLocationError`, pero recién al construir el
  `JointMap`, no antes.
- Medir físicamente `SAFE_TRAVEL_HEIGHT_MM` (altura de la pieza más
  alta, típicamente el Rey, + margen) y las tolerancias de posición/
  inclinación de `chess_kinematics` — placeholders sin validar, ver
  `M7_SPEC.md` §7.
- Verificar la convención de montaje de la pinza (eje de aproximación)
  contra el efector físico real — asunción no verificable sin hardware,
  ver nota en `kinematics_ik.py` (M7).
- Gestión de inventario de piezas de repuesto (cuántas quedan, cuándo
  reponerlas manualmente) — sin resolver, ver SPEC chess_planner §7.
- Ejecutar el protocolo de calibración física de los 6 servos
  (`M8_SPEC.md` §6) sobre el hardware real.
- Validar `max_joint_speed_deg_s`, `gripper_settle_s` y
  `first_move_settle_s` (`chess_actuators`) contra el comportamiento
  real de los MG996R — placeholders sin medir, ver `M8_SPEC.md` §9.
- Mitigar el auto-reset del Arduino UNO al abrir el puerto Serial
  (capacitor en RESET o similar) — ver `M8_SPEC.md` §3, §9.
- Definir posición de home/parking del brazo al iniciar/finalizar una
  sesión de juego — decisión de producto para M10, ver `M8_SPEC.md` §9.
