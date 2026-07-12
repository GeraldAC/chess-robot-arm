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

| #   | Módulo                       | Responsabilidad                                                                                               | Estado                        | Spec de referencia        |
| --- | ---------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------- | ------------------------- |
| 0   | Calibración                  | Mapeo píxel ↔ casilla ↔ coordenada del brazo                                                                  | Pendiente                     | —                         |
| 1   | Captura de imagen            | ESP32-CAM obtiene el frame y lo envía a la laptop                                                             | Pendiente                     | —                         |
| 2   | Detección del tablero        | Localizar las 64 casillas en la imagen                                                                        | Pendiente (siguiente enfoque) | —                         |
| 3   | Clasificación de piezas      | Identificar tipo/color de pieza por casilla                                                                   | Pendiente (siguiente enfoque) | —                         |
| 4   | Estado del juego             | Mantener el `chess.Board` autoritativo, inferir la jugada humana desde la matriz de Visión, validar legalidad | **Implementado**              | SPEC — chess_brain (M4-5) |
| 5   | Motor de decisión            | Calcular la mejor jugada vía Stockfish                                                                        | **Implementado**              | SPEC — chess_brain (M4-5) |
| 6   | Planificación de movimiento  | Traducir la jugada en una secuencia de acciones físicas (normal / captura / enroque / promoción)              | Pendiente                     | —                         |
| 7   | Cinemática inversa           | Coordenadas cartesianas → ángulos de articulaciones                                                           | Pendiente                     | —                         |
| 8   | Control de actuadores        | Ejecutar trayectoria + control de pinza (alturas de aproximación, apertura/cierre)                            | Pendiente                     | —                         |
| 9   | Verificación post-movimiento | Confirmar que el tablero físico coincide con el estado esperado                                               | Pendiente                     | —                         |
| 10  | Orquestador / comunicación   | Coordinar el ciclo completo y la comunicación entre dispositivos                                              | Pendiente                     | —                         |

> Nota: dentro de M4-5 existen además mini-módulos de interfaz (Entrada,
> Salida, simulador de Visión, presentación en consola, CLI de producto)
> ya implementados. Se documentan en el SPEC de chess_brain, no aquí, para
> no duplicar contrato.

## 4. Contratos entre módulos

### 4.1 Definidos y estables

- **`VisionInput`** (M2/M3 → M4): matriz 8x8 (`BoardMatrix`, códigos
  `"wP"`, `"bK"`, `None`, etc.) + `side_to_move`.
- **`MoveResult`** (M4/M5 → M6): jugada resultante con metadatos completos
  (captura, enroque, captura al paso, promoción, FEN, estado del juego).
- **`IllegalStateError`, `EngineError`**: errores de contrato explícitos —
  el Orquestador debe manejarlos como señales de flujo, no como fallos
  silenciosos.

Detalle completo de estos contratos en **SPEC — chess_brain (Módulos 4-5)**.

### 4.2 Pendientes de definir

- Salida de M2 (Detección del tablero) → entrada M3 (Clasificación de
  piezas): formato de las 64 regiones/casillas recortadas de la imagen.
- Cómo M3 construye el `BoardMatrix` a partir de clasificaciones con
  incertidumbre (¿score de confianza por casilla? ¿qué pasa si una
  clasificación es ambigua u ocluida?).
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

## 6. Estado actual y siguiente enfoque

- **M4 (Estado del Juego)** y **M5 (Motor de Decisión)** implementados
  y validados end-to-end con Stockfish real, incluyendo un CLI funcional
  para jugar partidas completas sin depender de Visión real.
- **Siguiente enfoque: Módulo 2 (Detección del tablero) y Módulo 3
  (Clasificación de piezas)**. Su salida combinada debe producir un
  `BoardMatrix` compatible con el contrato `VisionInput` que `chess_brain`
  ya consume — este contrato no debería renegociarse, solo satisfacerse.

## 7. Pendientes generales del proyecto

- Definir protocolo de comunicación entre dispositivos (M10).
- Definir controlador físico del brazo (¿Arduino/ESP32 dedicado?) y su
  interfaz de bajo nivel (M7/M8).
- Definir política de color/`side_to_move` del robot para el primer
  movimiento de una partida (decisión de producto, no solo técnica).
- Definir manejo de desincronización cuando Verificación (M9) detecte que
  el estado físico no coincide con lo esperado.
