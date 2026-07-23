# SPEC — chess_actuators: Control de Actuadores (M8)

> **Estado: a implementar.** Depende de tres decisiones de producto tomadas
> explícitamente para este SPEC (ver §2): (1) el controlador físico es
> **Arduino UNO + PCA9685 vía Serial/USB**, resolviendo la inconsistencia
> entre `README.md`/`GENERAL_SPEC.md` (que lo daban como "no definido") y
> `BOM.md` §4 (que ya lo especifica); (2) **no hay interpolación fina** entre
> waypoints — cada `ArmWaypoint` se envía como un único comando de posición
> objetivo y el Host espera un tiempo calculado antes del siguiente, dejando
> que el propio servo ejecute la rampa física; (3) el manejo de fallos de
> comunicación es **reintentos acotados + congelar en la última posición
> confirmada**, sin intento de recuperación automática.

## 1. Alcance

Este documento cubre dos componentes:

- El paquete Python **`chess_actuators`** (Host, importado por el
  Orquestador — mismo proceso, mismo criterio YAGNI que el resto del
  proyecto):
  - **`actuator_types.py`** (contratos internos, excepciones, `ExecutionReport`)
  - **`actuator_calibration.py`** (calibración física de servos: ángulo ↔ pulso)
  - **`actuator_protocol.py`** (framing y parsing del protocolo Serial, §3)
  - **`actuator_driver.py`** (`SerialActuatorDriver` real + `SimulatedActuatorDriver` para tests/CLI sin hardware)
  - **`actuator_executor.py`** (`execute_trajectory`: `ArmTrajectory` → `ExecutionReport`)
  - **`actuator_main.py`** (CLI de producto: ejecución de trayectoria y modo de calibración manual)
  - **`__init__.py`**
- El **contrato de protocolo Serial** (§3) que debe implementar el firmware
  del Arduino. Este SPEC especifica el protocolo y el comportamiento
  requerido del firmware, no cada línea de su código — mismo criterio que
  M7 usó con el notebook de IK: el firmware es una implementación de
  referencia guiada por el contrato, no forma parte del paquete `uv` del
  proyecto (vive fuera de `src/`, ver §7).

`chess_actuators` depende de:

- `chess_kinematics` (`ArmTrajectory`, `ArmWaypoint`, `JointAngles`,
  `GripperAction`, `WaypointKind`) — de dónde viene la entrada.
- `pyserial` — nueva dependencia (`uv add pyserial`), análoga a `pyyaml`
  en M0.

**Lo que este módulo NO hace:** M8 no decide la secuencia de movimientos
(`chess_planner`, M6), no resuelve cinemática inversa ni waypoints
(`chess_kinematics`, M7), no calibra posiciones cartesianas del tablero
(`chess_calibration`, M0), y **no verifica el estado físico real** del
tablero ni de la pieza sujetada — eso es M9. M8 tampoco tiene forma de
saber si un servo llegó realmente a su ángulo objetivo: los MG996R del
BOM no tienen feedback de posición (mismo hecho ya señalado en
`M0_SPEC.md` §9 y `M7_SPEC.md` §2.1). Lo único que M8 puede confirmar es
que el microcontrolador **recibió y aplicó** el comando — no que la
pieza física terminó donde se esperaba. Esa distinción es la razón por
la que `ExecutionReport` (§4.1) se documenta explícitamente como "no
verificación física", y por la que existe M9 como módulo separado.

## 2. Enfoque técnico

### 2.1 Arquitectura del controlador

```text
Host (Windows 11, chess_actuators)
   │  Serial/USB, ASCII, 115200 8N1
   ▼
Arduino UNO (firmware, fuera de src/)
   │  I2C
   ▼
PCA9685 (16 canales PWM, 12 bits) ── alimentación dedicada (BOM §4: SMPS 5-6V, 10-15A)
   │  PWM (6 canales usados de 16)
   ▼
6x servo MG996R (5 articulaciones + 1 pinza)
```

Se confirma `BOM.md` §4 como arquitectura definitiva (resolviendo la
inconsistencia con `README.md`/`GENERAL_SPEC.md` — ver Pendiente §9).
Motivo: con 6 servos el Arduino UNO podría en teoría manejarlos
directamente, pero el PCA9685 (a) libera al Arduino de generar PWM por
software, dejándolo disponible para parsing de Serial sin competir por
timers; (b) da 12 bits de resolución con oscilador propio, PWM estable
sin intervención continua del microcontrolador; y (c) permite alimentar
los servos desde el riel dedicado del BOM (§4, SMPS externa) separado de
la alimentación lógica del Arduino — evita que la corriente de arranque
de los servos (picos típicos de varios cientos de mA a ~1A por servo bajo
carga) produzca brownouts que reinicien el microcontrolador a mitad de
una jugada.

### 2.2 Sin interpolación fina: temporización a nivel de waypoint

`M7_SPEC.md` §7 dejó explícitamente abierto "cómo interpolar/temporizar
entre los `ArmWaypoint` consecutivos". Se evaluaron dos enfoques y se
descartan ambos a favor de un tercero (ver también §8):

- **Streaming fino desde el Host** (Python calcula pasos intermedios y
  los transmite en tiempo real, p. ej. a 50 Hz): descartado — Windows no
  es un SO de tiempo real, y la latencia/jitter de USB-Serial (típica de
  drivers FTDI/CH340) hace poco confiable sostener una cadencia de
  streaming fina sin movimientos entrecortados.
- **Interpolación en el Arduino** (Host envía solo objetivo + duración,
  el firmware interpola): descartado — movería lógica de negocio
  (perfiles de movimiento) a C/C++ sin cobertura de `pytest`, rompiendo
  el patrón del proyecto de mantener la inteligencia en Python testeable
  (mismo patrón que `chess_calibration`, `chess_kinematics`, etc.).
- **Adoptado: comando de posición objetivo por waypoint, sin
  sub-interpolación.** El MG996R ya tiene su propio control interno que
  rampea hacia el ángulo comandado — no necesitamos generar los pasos
  intermedios nosotros. Cada `ArmWaypoint` se traduce a **un único
  comando `SET`** (los 6 canales, incluida la pinza si corresponde,
  actualizados en el mismo mensaje — ver §3), y el Host calcula cuánto
  esperar antes de emitir el siguiente waypoint, en función del mayor
  delta angular entre el waypoint anterior y el actual, y una velocidad
  angular máxima configurable y conservadora (§4.1,
  `max_joint_speed_deg_s`). El firmware queda deliberadamente "tonto":
  solo relé de comandos Serial → registros del PCA9685.

### 2.3 Manejo de fallos: reintentos acotados + congelar en sitio

También dejado abierto por `M7_SPEC.md` §7 ("qué hacer si la ejecución
física falla a mitad de una trayectoria"). Dado que M8 solo detecta
fallos **de comunicación** (timeout de ACK, puerto desconectado,
respuesta `ERR`) y no fallos físicos reales (sin feedback de posición,
ver §1), la estrategia adoptada es:

1. Ante un fallo de comunicación en un `ArmWaypoint`, reintentar hasta
   `max_retries` veces (default 3) con espera `retry_backoff_s` entre
   intentos — absorbe glitches transitorios típicos de USB-Serial.
2. Si se agotan los reintentos, **abortar inmediatamente la trayectoria
   completa**: no se envían los waypoints restantes, y no se intenta
   ningún movimiento de recuperación (ni volver a un `TRANSIT` seguro ni
   ninguna otra maniobra). El brazo queda sosteniendo la última posición
   confirmada por el microcontrolador (los servos mantienen torque sobre
   el último pulso aplicado; el Arduino simplemente deja de recibir
   comandos nuevos).
3. Se descarta explícitamente el "volver automáticamente al último
   `TRANSIT` seguro": si el canal de comunicación que acaba de fallar es
   el mismo que se usaría para la maniobra de recuperación, no hay razón
   para asumir que esa maniobra tendría más éxito — y mover el brazo a
   ciegas sin saber la causa del fallo es más riesgoso que quedarse
   quieto. La recuperación queda como intervención humana, señalizada
   vía `TrajectoryExecutionError` (§4.2) al Orquestador (M10), mismo
   patrón que `UnreachableLocationError` (M7) o
   `CalibrationSessionNotFoundError` (M0): señal de flujo explícita, no
   fallo silencioso.

### 2.4 Calibración física de servos (nueva, distinta de M0 y M7)

Ni `CalibrationMap` (M0, casilla → coordenada cartesiana) ni `JointMap`
(M7, coordenada cartesiana → ángulo articular en la convención DH) saben
nada sobre el servo físico real que ejecuta cada articulación: cada
MG996R tiene su propio offset de montaje, y la relación entre "ángulo
en la convención DH del notebook" y "ancho de pulso PWM que hay que
mandarle a ese canal en particular" no es universal — depende de cómo
quedó montado cada servo. Este es un tercer nivel de calibración,
exclusivo de M8: `ActuatorCalibration` (§4.1, §6), con un rango
`[angle_min_deg, angle_max_deg]` medido físicamente por canal, análogo en
espíritu al método de medición manual de M0 (mismo motivo: los MG996R no
tienen feedback de posición, así que no hay forma de calibrar por
software sin medir).

A diferencia de `CalibrationMap`/`JointMap` (que se recalculan **una vez
por sesión de juego**, porque el tablero puede moverse), la calibración
de servos es una propiedad del **hardware físico del brazo**, no de la
sesión — no cambia entre partidas salvo que se reemplace o remonte un
servo. Se persiste como un archivo de configuración de proyecto (§6), no
de sesión, y se vuelve a medir solo cuando cambia el hardware.

## 3. Protocolo de comunicación Serial (Host ↔ Arduino)

Framing: texto ASCII, un comando por línea terminada en `\n`. Baudrate
default `115200`, 8N1. Cada comando del Host espera una respuesta de una
línea antes de considerarse resuelto; si no llega respuesta dentro de
`ack_timeout_s` (default 0.5 s), se cuenta como fallo para efectos de
reintento (§2.3).

| Comando (Host → Arduino)                   | Respuesta OK | Respuesta error                                                                                      | Descripción                                                                                                                                                                    |
| ------------------------------------------ | ------------ | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `PING`                                     | `PONG`       | (timeout)                                                                                            | Handshake de conexión, usado por `SerialActuatorDriver.connect()` antes de aceptar la conexión como válida.                                                                    |
| `SET ch0:pulse0,ch1:pulse1,...,chN:pulseN` | `ACK`        | `ERR 1` (canal inválido) / `ERR 2` (pulso fuera de rango PCA9685) / `ERR 3` (fallo de escritura I2C) | Fija el ancho de pulso (µs) de uno o más canales del PCA9685 en el mismo comando. Un `ArmWaypoint` completo (5 articulaciones + pinza si cambia) se envía como un único `SET`. |

Se evaluó agregar `STOP`/`RESUME` como comandos explícitos de
freeze/reanudación a nivel de firmware, pero se descarta para v1: el
Host ya logra "congelar en sitio" (§2.3) simplemente dejando de enviar
comandos `SET`, sin necesitar que el firmware entienda un estado
adicional. Queda como mejora candidata si se agrega un botón físico de
parada de emergencia independiente del Host (§9).

**Nota de implementación del firmware:** se recomienda `Adafruit_PWMServoDriver`
(librería estándar para PCA9685 en Arduino), que expone
`writeMicroseconds(channel, microseconds)` y evita implementar a mano la
conversión de µs a cuentas de 12 bits dentro del firmware.

**Advertencia de hardware conocida:** el Arduino UNO se reinicia por
defecto al abrirse una conexión Serial (toggle de DTR), lo que borra el
estado de los canales PWM del PCA9685 (vuelven a apagado) hasta el
primer `SET`. Si esto ocurre con el brazo sosteniendo una pieza a media
altura, la pieza puede perder sujeción. Mitigación de hardware (capacitor
en la línea RESET, o deshabilitar el auto-reset) queda fuera de este
SPEC de software — ver §9.

## 4. Contrato de datos

### 4.1 Tipos base

```python
Location = str
# Reutiliza la misma noción que chess_planner/chess_calibration/chess_kinematics.

@dataclass(frozen=True)
class ServoChannelCalibration:
    """Calibración física de un canal servo del PCA9685."""
    channel: int          # 0-15, canal físico en el PCA9685
    pulse_min_us: float    # ancho de pulso en el límite mecánico inferior
    pulse_max_us: float    # ancho de pulso en el límite mecánico superior
    angle_min_deg: float   # ángulo (convención DH de M7) en pulse_min_us
    angle_max_deg: float   # ángulo (convención DH de M7) en pulse_max_us
    reversed: bool = False # True si el sentido físico está invertido vs. la convención DH

@dataclass(frozen=True)
class GripperCalibration:
    """La pinza no recibe un ángulo de JointAngles: solo dos estados
    discretos, resueltos por GripperAction."""
    channel: int
    pulse_open_us: float
    pulse_closed_us: float

@dataclass(frozen=True)
class ActuatorCalibration:
    """Calibración física completa de los 6 servos del brazo. Propiedad
    del hardware, no de la sesión de juego (a diferencia de
    CalibrationMap/JointMap) — ver §2.4."""
    joints: dict[str, ServoChannelCalibration]  # claves "q1".."q5"
    gripper: GripperCalibration
    pwm_frequency_hz: float = 50.0

@dataclass(frozen=True)
class ActuatorConfig:
    """Parámetros de ejecución, expuestos como configuración en vez de
    constantes fijas."""
    serial_port: str                      # p. ej. "COM3" (Windows 11, BOM §1)
    baudrate: int = 115200
    ack_timeout_s: float = 0.5
    max_retries: int = 3
    retry_backoff_s: float = 0.1
    max_joint_speed_deg_s: float = 60.0   # PLACEHOLDER conservador — validar contra MG996R cargado (ver §9)
    gripper_settle_s: float = 0.4         # PLACEHOLDER — validar tiempo real de cierre (ver §9)
    first_move_settle_s: float = 2.0      # espera fija para el primer waypoint de la sesión (posición inicial desconocida)

class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

@dataclass(frozen=True)
class WaypointExecutionResult:
    location: Location
    kind: WaypointKind
    attempts: int              # 1 si tuvo éxito al primer intento
    status: ExecutionStatus

@dataclass(frozen=True)
class ExecutionReport:
    """Contrato de salida M8 -> M9. Resume qué comandos se enviaron y
    confirmó el microcontrolador — NO es una verificación del estado
    físico real (ver §1): eso corresponde a M9, que sí tiene visión
    para comparar contra el tablero."""
    trajectory_status: ExecutionStatus
    waypoint_results: list[WaypointExecutionResult]
    failed_at_index: int | None   # índice del waypoint donde abortó, si aplica
```

### 4.2 Errores

```python
class ActuatorError(Exception):
    """Clase base de errores de contrato de chess_actuators."""

class ActuatorConnectionError(ActuatorError):
    """No se pudo abrir/mantener la conexión Serial (puerto no
    encontrado, PING inicial sin PONG dentro de ack_timeout_s)."""

class ActuatorCalibrationNotFoundError(ActuatorError):
    """Análogo a CalibrationSessionNotFoundError (M0) /
    JointMapSessionNotFoundError (M7): no existe un archivo de
    ActuatorCalibration válido, o le faltan canales (q1..q5 o gripper)."""

class ServoAngleOutOfRangeError(ActuatorError):
    """Un JointAngles cae fuera de [angle_min_deg, angle_max_deg] de su
    ServoChannelCalibration. Se lanza ANTES de enviar el comando —
    defensa en profundidad adicional a la ya provista por M7 (que valida
    alcanzabilidad contra los límites del modelo DH, no contra los
    límites físicos reales medidos aquí)."""

class TrajectoryExecutionError(ActuatorError):
    """Se agotaron los reintentos en un ArmWaypoint durante
    execute_trajectory. El Orquestador debe tratar esto como señal de
    flujo explícita (requiere intervención humana antes de continuar la
    partida), mismo patrón que UnreachableLocationError (M7). Contiene
    el ExecutionReport parcial para que M10 pueda inspeccionar qué se
    alcanzó a ejecutar antes del fallo."""
    def __init__(self, partial_report: ExecutionReport):
        self.partial_report = partial_report
        super().__init__(f"Trayectoria abortada en índice {partial_report.failed_at_index}")
```

## 5. Diseño interno

### 5.1 `actuator_calibration.py`

```python
def load_actuator_calibration(path: str) -> ActuatorCalibration:
    """Carga la calibración de servos desde YAML (formato §6). Lanza
    ActuatorCalibrationNotFoundError si el archivo no existe o le faltan
    canales requeridos (q1..q5, gripper)."""

def save_actuator_calibration(calibration: ActuatorCalibration, path: str) -> None:
    """Persiste la calibración a YAML. A diferencia de
    save_calibration_session (M0) / save_joint_map_session (M7), esto no
    es un archivo de sesión: se re-guarda solo cuando cambia el hardware
    físico (servo reemplazado/remontado), no una vez por partida."""

def pulses_from_joint_angles(
    joint_angles: JointAngles, calibration: ActuatorCalibration,
) -> dict[int, int]:
    """Convierte JointAngles (grados, convención DH de M7) a pulsos PWM
    (µs) por canal físico: interpolación lineal dentro de
    [angle_min_deg, angle_max_deg] -> [pulse_min_us, pulse_max_us] de
    cada ServoChannelCalibration, invirtiendo el sentido si reversed=True.
    Lanza ServoAngleOutOfRangeError si algún ángulo cae fuera del rango
    calibrado de su canal."""

def gripper_pulse(
    action: GripperAction, calibration: GripperCalibration, current_pulse_us: int,
) -> int:
    """OPEN -> pulse_open_us, CLOSE -> pulse_closed_us, HOLD -> current_pulse_us (sin cambio)."""
```

### 5.2 `actuator_protocol.py`

```python
def format_ping() -> str:
    """Retorna 'PING\\n'."""

def format_set(pulses: dict[int, int]) -> str:
    """Retorna 'SET ch:pulse,ch:pulse,...\\n' a partir de un dict
    {canal: pulso_us}, orden determinístico (por número de canal
    ascendente) para reproducibilidad en logs/tests."""

def parse_response(raw_line: str) -> tuple[bool, str | None]:
    """Interpreta una línea de respuesta del Arduino. Retorna
    (True, None) para 'PONG'/'ACK'; (False, código) para 'ERR <code>';
    lanza ValueError si la línea no matchea ningún formato conocido."""
```

### 5.3 `actuator_driver.py`

```python
class ActuatorDriver(Protocol):
    """Interfaz común entre el driver real y el simulado — permite que
    actuator_executor.py y los tests no dependan de pyserial ni de
    hardware conectado."""
    def connect(self) -> None: ...
    def send_set(self, pulses: dict[int, int]) -> None:
        """Envía un comando SET y espera ACK dentro de ack_timeout_s.
        Lanza ActuatorConnectionError en timeout, ValueError en ERR del
        firmware. No reintenta — el reintento es responsabilidad de
        actuator_executor.py (§2.3), no del driver."""
    def close(self) -> None: ...

class SerialActuatorDriver:
    """Implementación real sobre pyserial. connect() abre el puerto y
    hace PING/PONG antes de retornar; si no hay respuesta dentro de
    ack_timeout_s, lanza ActuatorConnectionError."""

class SimulatedActuatorDriver:
    """Implementación en memoria, sin hardware: registra cada send_set
    en una lista (para asserts en tests) y responde ACK inmediatamente.
    Acepta un parámetro de inyección de fallos (fail_at: set[int], por
    índice de llamada) para testear la lógica de reintentos de
    actuator_executor.py sin hardware real — mismo espíritu que el
    simulador de Visión (M2/M3) y las fixtures sin DE real de M7."""
```

### 5.4 `actuator_executor.py`

```python
def compute_settle_time_s(
    previous: JointAngles | None, target: JointAngles,
    gripper_changed: bool, config: ActuatorConfig,
) -> float:
    """Si previous es None (primer waypoint de la sesión), retorna
    config.first_move_settle_s. Si no, retorna
    max(|delta| por articulación) / config.max_joint_speed_deg_s,
    sumando config.gripper_settle_s si gripper_changed."""

def execute_waypoint(
    waypoint: ArmWaypoint, driver: ActuatorDriver, calibration: ActuatorCalibration,
    config: ActuatorConfig, previous_angles: JointAngles | None, current_gripper_pulse_us: int,
) -> tuple[WaypointExecutionResult, JointAngles, int]:
    """Convierte el waypoint a pulsos (pulses_from_joint_angles +
    gripper_pulse), llama driver.send_set con hasta config.max_retries
    intentos (backoff config.retry_backoff_s entre intentos), y si tiene
    éxito espera compute_settle_time_s antes de retornar. Retorna el
    resultado + el nuevo estado (para encadenar el siguiente waypoint)."""

def execute_trajectory(
    trajectory: ArmTrajectory, driver: ActuatorDriver, calibration: ActuatorCalibration,
    config: ActuatorConfig,
) -> ExecutionReport:
    """Punto de entrada único de chess_actuators para el ciclo de
    partida. Ejecuta cada ArmWaypoint en orden vía execute_waypoint. Si
    un waypoint agota los reintentos, aborta de inmediato (no ejecuta
    los waypoints restantes) y lanza TrajectoryExecutionError con el
    ExecutionReport parcial (ver §2.3, §4.2). Si todos los waypoints se
    ejecutan con éxito, retorna ExecutionReport con status=SUCCESS."""
```

### 5.5 `actuator_main.py` — CLI de producto

**Argumentos:**

| Argumento       | Requerido | Default | Descripción                                                                                      |
| --------------- | --------- | ------- | ------------------------------------------------------------------------------------------------ |
| `--port`        | Sí\*      | —       | Puerto Serial (p. ej. `COM3`). No requerido en modo `--simulate`.                                |
| `--calibration` | Sí        | —       | Ruta al YAML de `ActuatorCalibration` (§6)                                                       |
| `--trajectory`  | No        | —       | Ruta a una `ArmTrajectory` serializada de prueba, para ejecutar end-to-end                       |
| `--simulate`    | No        | `false` | Usa `SimulatedActuatorDriver` en vez de hardware real                                            |
| `--test-pulse`  | No        | —       | Modo diagnóstico: `--test-pulse <canal> <pulso_us>` para el protocolo de calibración manual (§6) |

Sin `--trajectory`, el CLI se conecta (PING/PONG), reporta el resultado, y
queda disponible en modo diagnóstico (`--test-pulse`) para el protocolo
de calibración física.

### 5.6 `__init__.py` — Superficie pública

```python
from chess_actuators.actuator_executor import execute_trajectory
from chess_actuators.actuator_calibration import (
    load_actuator_calibration, save_actuator_calibration,
)
from chess_actuators.actuator_driver import SerialActuatorDriver, SimulatedActuatorDriver
from chess_actuators.actuator_types import (
    ActuatorCalibration, ServoChannelCalibration, GripperCalibration, ActuatorConfig,
    ExecutionStatus, WaypointExecutionResult, ExecutionReport,
    ActuatorError, ActuatorConnectionError, ActuatorCalibrationNotFoundError,
    ServoAngleOutOfRangeError, TrajectoryExecutionError,
)
```

Igual que en los módulos anteriores, este es el único contrato que M9 y
el futuro Orquestador (M10) deberían asumir estable. El Orquestador debe
cargar `ActuatorCalibration` una vez al iniciar (no por sesión, ver
§2.4) y llamar `execute_trajectory` una vez por cada `ArmTrajectory` que
entregue M7.

## 6. Formato del archivo de calibración de servos (`--calibration`)

```yaml
# Calibración física de los 6 servos del brazo. Propiedad del hardware,
# no de la sesión de juego — se re-mide solo si se reemplaza/remonta un
# servo (ver M8_SPEC.md §2.4). Protocolo de medición: usar
# `actuator_main.py --test-pulse <canal> <pulso_us>` para barrer el
# rango de cada servo, anotar los pulsos en los límites mecánicos y
# medir el ángulo real (convención DH de M7) en cada extremo con
# goniómetro/transportador contra el cero del modelo.
joints:
  q1:
    {
      channel: 0,
      pulse_min_us: 500,
      pulse_max_us: 2500,
      angle_min_deg: -90.0,
      angle_max_deg: 90.0,
      reversed: false,
    }
  q2:
    {
      channel: 1,
      pulse_min_us: 500,
      pulse_max_us: 2500,
      angle_min_deg: -90.0,
      angle_max_deg: 90.0,
      reversed: false,
    }
  q3:
    {
      channel: 2,
      pulse_min_us: 500,
      pulse_max_us: 2500,
      angle_min_deg: -90.0,
      angle_max_deg: 90.0,
      reversed: true,
    }
  q4:
    {
      channel: 3,
      pulse_min_us: 500,
      pulse_max_us: 2500,
      angle_min_deg: -90.0,
      angle_max_deg: 90.0,
      reversed: false,
    }
  q5:
    {
      channel: 4,
      pulse_min_us: 500,
      pulse_max_us: 2500,
      angle_min_deg: -90.0,
      angle_max_deg: 90.0,
      reversed: false,
    }

gripper:
  channel: 5
  pulse_open_us: 1500
  pulse_closed_us: 900

pwm_frequency_hz: 50.0
```

Los valores mostrados son de ejemplo, no medidos — mismo criterio que el
YAML de ejemplo de `M0_SPEC.md` §7.

## 7. Estructura del proyecto

```structure
chess-robot-arm/
├── src/
│   ├── chess_brain/                   # M4-5 (implementado)
│   ├── chess_vision/                  # M2-3 (implementado)
│   ├── chess_planner/                 # M6 (implementado)
│   ├── chess_calibration/             # M0 (implementado)
│   ├── chess_kinematics/              # M7 (implementado)
│   └── chess_actuators/               # M8 (a implementar)
│       ├── __init__.py
│       ├── M8_SPEC.md
│       ├── actuator_types.py           # ActuatorCalibration, ExecutionReport, excepciones
│       ├── actuator_calibration.py     # ángulo <-> pulso, load/save
│       ├── actuator_protocol.py        # framing Serial (§3)
│       ├── actuator_driver.py          # SerialActuatorDriver + SimulatedActuatorDriver
│       ├── actuator_executor.py        # execute_trajectory
│       └── actuator_main.py            # CLI de producto
├── firmware/
│   └── chess_arm_controller/
│       └── chess_arm_controller.ino    # firmware Arduino — implementa el protocolo de §3.
│                                        # Fuera de src/: no es Python, no lo gestiona uv.
└── tests/
    ├── test_brain/
    ├── test_vision/
    ├── test_planner/
    ├── test_calibration/
    ├── test_kinematics/
    └── test_actuators/
        ├── __init__.py
        ├── test_actuator_calibration.py
        ├── test_actuator_protocol.py
        ├── test_actuator_driver.py      # contra SimulatedActuatorDriver, sin hardware real
        ├── test_actuator_executor.py
        └── fixtures/
            ├── __init__.py
            ├── sample_calibration.yaml   # ActuatorCalibration de prueba
            └── sample_trajectory.py      # ArmTrajectory de prueba (reusa fixtures de M7)
```

Nueva dependencia: `pyserial` (`uv add pyserial`). El resto usa
`dataclasses`, `enum` y `yaml` (ya presente desde M0).

## 8. Alternativas evaluadas y descartadas

| Alternativa                                                                              | Por qué se descartó para v1                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Streaming de interpolación fina desde el Host** (pasos intermedios a 50 Hz vía Serial) | Depende de una cadencia sostenida confiable sobre USB-Serial en Windows, no un SO de tiempo real — riesgo de jitter/movimiento entrecortado sin beneficio real, dado que el MG996R ya rampea internamente hacia el objetivo.                   |
| **Interpolación de trayectoria en el firmware del Arduino**                              | Movería lógica de negocio (perfiles de movimiento) fuera de Python/pytest, rompiendo el patrón de todo el proyecto de mantener la inteligencia testeable en el Host; firmware más complejo y más difícil de iterar.                            |
| **Recuperación automática tras fallo** (volver a TRANSIT seguro y reintentar)            | Requiere confiar en el mismo canal de comunicación que acaba de fallar, sin saber la causa; sin feedback de posición no hay forma de confirmar que el movimiento de "recuperación" fue seguro. Se prefiere congelar + escalar a humano (§2.3). |
| **`STOP`/`RESUME` como comandos de firmware en v1**                                      | El Host ya logra "congelar en sitio" simplemente dejando de enviar `SET`; agregar estado en el firmware no aporta valor sin un E-stop físico independiente que lo dispare (ver §9).                                                            |
| **ESP32 dedicado en vez de Arduino UNO + PCA9685**                                       | Sin ventaja clara para 6 canales PWM; agregaría WiFi innecesario para un enlace que ya es más determinístico por cable, y se apartaría del BOM ya definido sin una razón de peso.                                                              |

## 9. Pendiente (fuera de alcance de este SPEC)

- **Actualizar `README.md` y `GENERAL_SPEC.md`** para reflejar que el
  controlador físico SÍ está definido (Arduino UNO + PCA9685 + Serial,
  confirmado en este SPEC §2.1), resolviendo la inconsistencia con
  `BOM.md` §4 detectada al iniciar este documento.
- **Ejecutar el protocolo de calibración física de servos** (§6) sobre
  el hardware real — el mecanismo ya está definido, falta la medición,
  mismo patrón que M0/M7.
- **Validar `max_joint_speed_deg_s`, `gripper_settle_s` y
  `first_move_settle_s`** contra el comportamiento real de los MG996R
  bajo la carga del brazo (los placeholders de §4.1 son conservadores,
  no medidos).
- **Mitigar el auto-reset del Arduino UNO al abrir el puerto Serial**
  (§3): capacitor en la línea RESET o deshabilitar el auto-reset por
  software/hardware — relevante porque un reset a mitad de partida
  perdería el estado PWM de los 6 canales.
- **E-stop físico independiente del Host**: no contemplado en `BOM.md`
  ni en este SPEC v1. Si se agrega, es la justificación natural para
  incorporar `STOP`/`RESUME` al protocolo (§3, §8).
- **Posición de home/parking** al iniciar o finalizar una sesión de
  juego: no definida en este SPEC — decisión de producto para el
  Orquestador (M10), análoga a cómo M10 decide qué hacer ante
  `CalibrationSessionNotFoundError` (M0 §10).
- **Migración a servos con feedback de posición** (p. ej. "smart
  servos" tipo Dynamixel) si en el futuro se requiere recuperación
  automática real tras un fallo — mejora candidata, no v1. El contrato
  `ExecutionReport`/`ArmTrajectory` no debería cambiar, solo la
  implementación de `ActuatorDriver` (mismo principio que M0 §10 sobre
  migración a teach-mode/hand-eye).
- **Verificación cruzada** de que `ActuatorCalibration` corresponde al
  hardware realmente conectado (p. ej. Arduino en un puerto distinto, o
  una unidad de repuesto con calibración diferente): no hay chequeo en
  v1, más allá del handshake `PING`/`PONG`.
- **Contrato M8 → M9 (formato de estado físico verificado)**:
  `ExecutionReport` (§4.1) resuelve el pendiente de
  `GENERAL_SPEC.md` §4.2 en cuanto a "qué se intentó ejecutar", pero no
  reemplaza la verificación física real — M9 sigue siendo responsable
  de comparar el tablero físico contra el estado esperado vía visión.

## 10. Plan de pruebas

### 10.1 `test_actuator_calibration.py`

| Caso                                       | Verifica                                                            |
| ------------------------------------------ | ------------------------------------------------------------------- |
| `pulses_from_joint_angles` dentro de rango | Interpolación lineal correcta, incluyendo canal con `reversed=True` |
| `pulses_from_joint_angles` fuera de rango  | `ServoAngleOutOfRangeError`                                         |
| `gripper_pulse` para OPEN/CLOSE/HOLD       | Pulsos correctos; HOLD retorna `current_pulse_us` sin cambio        |
| Carga de YAML válido / round-trip          | `load_actuator_calibration` + `save_actuator_calibration`           |
| YAML con canal faltante (q1..q5 o gripper) | `ActuatorCalibrationNotFoundError`                                  |

### 10.2 `test_actuator_protocol.py`

| Caso                                        | Verifica                                                           |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `format_set` con múltiples canales          | Formato exacto `SET ch:pulse,...`, orden determinístico por canal  |
| `parse_response` para PONG/ACK/ERR/inválido | Retorno correcto en cada caso; `ValueError` en formato desconocido |

### 10.3 `test_actuator_driver.py`

| Caso                                                     | Verifica                                                              |
| -------------------------------------------------------- | --------------------------------------------------------------------- |
| `SimulatedActuatorDriver.send_set` sin fallos inyectados | Registra el comando, responde éxito                                   |
| `SimulatedActuatorDriver` con `fail_at` configurado      | Lanza el error esperado en la llamada indicada, éxito en las demás    |
| `SerialActuatorDriver.connect` sin respuesta PONG        | `ActuatorConnectionError` (vía mock de `pyserial`, sin hardware real) |

### 10.4 `test_actuator_executor.py`

| Caso                                                                 | Verifica                                                                                                                          |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `compute_settle_time_s`, primer waypoint (`previous=None`)           | Retorna `first_move_settle_s`                                                                                                     |
| `compute_settle_time_s`, waypoints subsecuentes                      | Proporcional al mayor delta angular; suma `gripper_settle_s` si `gripper_changed`                                                 |
| `execute_trajectory` end-to-end exitosa (driver simulado)            | `ExecutionReport.status == SUCCESS`, todos los waypoints con `attempts` correctos                                                 |
| `execute_trajectory` con fallo transitorio (1-2 fallos, luego éxito) | Reintenta hasta `max_retries`, `attempts > 1` en el resultado de ese waypoint, trayectoria continúa                               |
| `execute_trajectory` con fallo persistente (agota `max_retries`)     | Aborta de inmediato, `TrajectoryExecutionError` con `partial_report.failed_at_index` correcto, no ejecuta los waypoints restantes |

### 10.5 `test_actuator_main.py`

| Caso                                                  | Verifica                                                           |
| ----------------------------------------------------- | ------------------------------------------------------------------ |
| CLI en modo `--simulate` con `--trajectory` de prueba | Ejecuta end-to-end sin hardware real, código de salida 0           |
| CLI sin `--calibration`                               | Código de salida 1, error claro                                    |
| CLI en modo `--test-pulse`                            | Envía el comando `SET` de un único canal vía el driver configurado |
