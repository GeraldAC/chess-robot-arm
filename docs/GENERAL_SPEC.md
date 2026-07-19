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
- Brazo robótico con pinza (gripper). Controlador físico dedicado aún no
  definido (pendiente, ver Módulo 8).
- Laptop (Windows 11): ejecuta Visión, Motor de Decisión y Orquestador.

**Entorno de desarrollo:**

- Python 3.11
- VSCode
- `uv` (gestión de proyecto y dependencias)

## 3. Arquitectura general — Módulos del sistema

| #   | Módulo                       | Responsabilidad                                                                                               | Estado                                                                                                         | Spec de referencia         |
| --- | ---------------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------- |
| 0   | Calibración                  | Mapeo píxel ↔ casilla ↔ coordenada del brazo                                                                  | Pendiente                                                                                                      | —                          |
| 1   | Captura de imagen            | ESP32-CAM obtiene el frame y lo envía a la laptop                                                             | Pendiente                                                                                                      | —                          |
| 2   | Detección del tablero        | Localizar las 64 casillas en la imagen                                                                        | **Implementado** (detección clásica con OpenCV, sin ML — ver nota al final de esta sección)                    | SPEC — chess_vision (M2-3) |
| 3   | Clasificación de piezas      | Identificar tipo/color de pieza por casilla                                                                   | **Implementado** (modelo pretrained de terceros, sin entrenamiento propio — ver nota al final de esta sección) | SPEC — chess_vision (M2-3) |
| 4   | Estado del juego             | Mantener el `chess.Board` autoritativo, inferir la jugada humana desde la matriz de Visión, validar legalidad | **Implementado**                                                                                               | SPEC — chess_brain (M4-5)  |
| 5   | Motor de decisión            | Calcular la mejor jugada vía Stockfish                                                                        | **Implementado**                                                                                               | SPEC — chess_brain (M4-5)  |
| 6   | Planificación de movimiento  | Traducir la jugada en una secuencia de acciones físicas (normal / captura / enroque / promoción)              | Pendiente                                                                                                      | —                          |
| 7   | Cinemática inversa           | Coordenadas cartesianas → ángulos de articulaciones                                                           | Pendiente                                                                                                      | —                          |
| 8   | Control de actuadores        | Ejecutar trayectoria + control de pinza (alturas de aproximación, apertura/cierre)                            | Pendiente                                                                                                      | —                          |
| 9   | Verificación post-movimiento | Confirmar que el tablero físico coincide con el estado esperado                                               | Pendiente                                                                                                      | —                          |
| 10  | Orquestador / comunicación   | Coordinar el ciclo completo y la comunicación entre dispositivos                                              | Pendiente                                                                                                      | —                          |

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

Detalle completo de estos contratos en **SPEC — chess_brain (Módulos 4-5)**
y **SPEC — chess_vision (Módulos 2-3)**.

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
- M6 → M7: formato de la "secuencia de acciones físicas".
- M7 → M8: formato de ángulos de articulación / trayectoria.
- M8 → M9: formato del estado físico verificado.
- M10: protocolo de comunicación entre ESP32-CAM, laptop y controlador del
  brazo (WiFi/HTTP, Serial, MQTT — no decidido aún).

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

## 6. Estado actual y siguiente enfoque

- **M4 (Estado del Juego)** y **M5 (Motor de Decisión)** implementados
  y validados end-to-end con Stockfish real, incluyendo un CLI funcional
  para jugar partidas completas sin depender de Visión real.
- **M2 (Detección del tablero)** y **M3 (Clasificación de piezas)**
  implementados sobre soluciones ya existentes de la comunidad (sin
  entrenamiento propio), con un producto funcional standalone
  (`vision_main.py`) que corre el pipeline completo sobre una imagen local y
  muestra entrada/salida exactas. Pendiente de validación con hardware
  y tablero físico reales por parte del usuario.
- **Siguiente enfoque:** con M2-5 cubiertos de punta a punta (imagen →
  posición → jugada del motor), el siguiente cuello de botella real del
  proyecto es **Módulo 6 (Planificación de movimiento)** — traducir un
  `MoveResult` en una secuencia de acciones físicas — ya que ahí empieza
  a intervenir el hardware del brazo (M7-M8), todavía sin definir.

## 7. Pendientes generales del proyecto

- Definir protocolo de comunicación entre dispositivos (M10).
- Definir controlador físico del brazo (¿Arduino/ESP32 dedicado?) y su
  interfaz de bajo nivel (M7/M8).
- Definir política de color/`side_to_move` del robot para el primer
  movimiento de una partida (decisión de producto, no solo técnica).
- Definir manejo de desincronización cuando Verificación (M9) detecte que
  el estado físico no coincide con lo esperado.
