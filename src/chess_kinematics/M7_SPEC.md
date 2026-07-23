# SPEC — chess_kinematics: Cinemática Inversa (M7)

> **Estado: implementado, 21/21 tests pasando.** Depende de tres decisiones
> de producto tomadas explícitamente para este SPEC: (1) el método de IK es
> **Evolución Diferencial (DE)**, reutilizando el algoritmo del notebook
> `chess_robot_arm_dk_ik.py` sin modificar su núcleo; (2) M7 es dueño de la
> **trayectoria fina completa** (waypoints, altura segura, secuencia de
> pinza), no solo de la IK punto a punto; (3) la orientación del efector es
> **vertical por defecto, con relajación controlada** en ubicaciones límite
> de alcance.

## 1. Alcance

Este documento cubre:

- **`kinematics_types.py`** (contratos internos de `chess_kinematics`)
- **`kinematics_ik.py`** (DK/IK puros, adaptados del notebook — sin
  plotting ni prints de progreso, que quedan fuera del contrato de
  producto)
- **`kinematics_map.py`** (construcción y persistencia de `JointMap`:
  IK resuelta una vez por sesión para las 68 ubicaciones de M0)
- **`kinematics_planner.py`** (traducción de `PhysicalPlan` (M6) +
  `JointMap` a `ArmTrajectory` — la trayectoria fina)
- **`__init__.py`** (superficie pública del paquete)

Arquitectura: módulo Python (`chess_kinematics`) importado por el
orquestador, mismo proceso, mismo criterio YAGNI que el resto del
proyecto. `chess_kinematics` depende de:

- `chess_calibration` (`ArmPoint`, `CalibrationMap`) — de dónde vienen
  los puntos a resolver.
- `chess_planner` (`PhysicalPlan`, `PieceTransfer`, `Zone`) — de dónde
  viene la secuencia de movimientos a traducir.
- `numpy` — ya usado en el notebook, sin dependencias nuevas.

**Lo que este módulo NO hace:** M7 no controla servos, no genera señales
PWM ni gestiona timing de ejecución real — eso es M8 (Control de
Actuadores). M7 entrega una secuencia de configuraciones articulares ya
resueltas y ordenadas; M8 decide cómo interpolar y ejecutar entre ellas.

**Aclaración de alcance crítica** (mismo espíritu que M6_SPEC §1 y
M0_SPEC §1): M7 tiene dos responsabilidades distintas que conviene no
confundir:

1. **Resolver IK** (`kinematics_ik.py` + `kinematics_map.py`): dado un
   punto cartesiano + una orientación deseada, encontrar los ángulos de
   articulación. Esto se ejecuta **una vez por sesión**, sobre las 68
   ubicaciones de `CalibrationMap` (y sus variantes de altura segura),
   nunca durante la partida en sí.
2. **Planificar trayectoria** (`kinematics_planner.py`): dado un
   `PhysicalPlan` de M6, traducir cada `PieceTransfer` a una secuencia
   de waypoints consultando el resultado ya cacheado del punto 1. Esto
   sí se ejecuta **por cada jugada**, pero es una operación barata
   (solo lookups + concatenación), no vuelve a invocar DE.

## 2. Enfoque técnico

### 2.1 Por qué precomputar por sesión (y no por jugada)

El algoritmo DE del notebook (`NP=150`, `G_max=2000`, convergencia
típica en cientos de generaciones) es correcto pero costoso en tiempo de
cómputo y no determinístico entre corridas — dos corridas sobre el mismo
punto objetivo pueden converger a configuraciones articulares distintas
(aunque equivalentes en error). Para una partida de ajedrez esto es
indeseable: no queremos que el brazo tome caminos distintos para la
misma casilla en dos jugadas sucesivas, ni pagar varios segundos de DE
en medio de una jugada.

Solución adoptada: resolver IK **una sola vez por sesión**, para las 68
ubicaciones de `CalibrationMap` × 2 variantes de altura (`grasp` y
`transit`, ver §2.2) = hasta 136 problemas de IK, inmediatamente después
de que M0 entrega su `CalibrationMap` y antes de que el Orquestador (M10)
arranque el ciclo de partida. El resultado (`JointMap`) se persiste a
sesión, igual que `CalibrationMap` en M0. Esto:

- Aísla el costo de DE a un paso de preparación (como ya lo es la
  calibración manual de M0), donde unos minutos de cómputo son
  aceptables.
- Hace determinística la ejecución durante la partida: mismos ángulos
  para la misma ubicación, todas las veces.
- Permite detectar ubicaciones no alcanzables **antes** de que empiece
  la partida, no a mitad de una jugada.

### 2.2 Altura segura de tránsito (`transit`) y colisión con otras piezas

`M6_SPEC.md` §7 dejó pendiente "evitar colisión con otras piezas al
pasar por encima del tablero", sin resolver si es responsabilidad de M7
o M8. Este SPEC la resuelve así: para cada ubicación se calculan **dos**
configuraciones articulares, no una:

- **`grasp`**: en la altura real de la pieza/zona (`z_mm` tal cual viene
  de `CalibrationMap`).
- **`transit`**: en la misma `(x, y)`, pero a `z_mm + SAFE_TRAVEL_HEIGHT_MM`
  — una altura por encima de la pieza más alta del set.

Toda transferencia entre dos ubicaciones se hace **siempre** pasando por
`transit` en origen y destino (ver §4.3), nunca en línea recta a la
altura de la pieza. Esto resuelve la colisión con otras piezas del
tablero con un modelo simple (una altura de vuelo uniforme), sin
necesitar modelar obstáculos por pieza — suficiente para un tablero
donde todas las piezas están en un plano y su única variable relevante
es la altura.

> (!) `SAFE_TRAVEL_HEIGHT_MM` no puede fijarse a ciegas: depende de la
> pieza más alta del set físico real (típicamente el Rey). Es un valor
> **a medir**, no un dato de catálogo — ver §7 (Pendiente) y considerar
> agregarlo al protocolo de medición de `M0_SPEC.md` §4.

### 2.3 Orientación: vertical con relajación controlada

`CalibrationMap` (M0) solo da posición, no orientación — es una decisión
de M7 definir la pose objetivo completa. Se adopta:

- **Por defecto**, el eje de aproximación del efector es vertical (eje Z
  de la pinza alineado con -Z del mundo): toma cenital, consistente con
  que las piezas son simétricas y no requieren un ángulo de agarre
  particular.
- **Error de orientación con invariancia de roll**: el `_orientation_error`
  del notebook compara la matriz de rotación completa (3 grados de
  libertad). Para este caso de uso eso es más estricto de lo necesario:
  la pinza es simétrica sobre una pieza redonda, así que el giro de
  muñeca (`q5`) es un grado de libertad libre que **no debería
  penalizarse**. Se reemplaza por una métrica que solo compara la
  dirección del eje de aproximación (2 DOF de orientación), ignorando
  rotación alrededor de ese eje. Esto amplía el conjunto de soluciones
  válidas frente al costo original del notebook, sin tocar el algoritmo
  DE en sí.
- **Relajación en casos límite**: si ni `grasp` ni `transit` de una
  ubicación convergen dentro de tolerancia con verticalidad estricta
  (posible cerca del borde del alcance de 355 mm, dado que las
  articulaciones están limitadas a ±90° y no a 180° completos — ver
  `chess_robot_arm_dk_ik.py`), se reintenta permitiendo una inclinación
  progresiva (ver tabla en §4.2) hasta un máximo configurable. Si ninguna
  inclinación converge, se lanza `UnreachableLocationError` — **al
  construir el `JointMap`**, no durante la partida.

## 3. Contrato de datos

### 3.1 Tipos base

```python
Location = str
# Reutiliza la misma noción que chess_planner/chess_calibration: casilla
# algebraica ("a1".."h8") o Zone.value.

@dataclass(frozen=True)
class JointAngles:
    """Ángulos de las 5 articulaciones activas, en grados, en el mismo
    orden y convención que JOINT_LIMITS_DEG del notebook. No incluye q6
    (pinza): el gripper es un actuador independiente, desacoplado de la
    cinemática de posición (igual que en el notebook, donde q6 está
    fijo y no participa en forward_kinematics)."""
    q1_deg: float  # Base (yaw)
    q2_deg: float  # Hombro
    q3_deg: float  # Codo
    q4_deg: float  # Flexión de muñeca (pitch)
    q5_deg: float  # Giro de muñeca (roll) — libre para agarre simétrico

class GripperAction(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    HOLD = "HOLD"   # sin cambio (usado en waypoints de tránsito)

class WaypointKind(str, Enum):
    TRANSIT = "TRANSIT"  # altura segura, sin contacto con pieza/zona
    GRASP = "GRASP"       # altura real de la pieza/zona

@dataclass(frozen=True)
class ArmWaypoint:
    """Una única configuración articular a alcanzar, con la acción de
    pinza asociada. `location` se conserva solo para trazabilidad/log,
    M8 no debería necesitarlo para controlar el brazo."""
    location: Location
    joint_angles: JointAngles
    gripper: GripperAction
    kind: WaypointKind

ArmTrajectory = list[ArmWaypoint]
# Secuencia ORDENADA de waypoints. El orden importa, igual que en
# PhysicalPlan (M6): debe ejecutarse tal cual para llegar al estado
# físico correcto.

@dataclass(frozen=True)
class LocationSolution:
    """Resultado de IK para una Location, ya resuelto y cacheado."""
    grasp: JointAngles
    transit: JointAngles
    orientation_relaxed: bool
    # True si tuvo que relajarse la verticalidad estricta para converger
    # (grasp y/o transit). El Orquestador debería poder loguear/advertir
    # sobre esto al construir la sesión, no descartarlo silenciosamente.

JointMap = dict[Location, LocationSolution]
# 68 entradas, mismas claves que CalibrationMap (M0).
```

### 3.2 Configuración de IK

```python
@dataclass(frozen=True)
class DEConfig:
    """Parámetros de differential_evolution_ik, expuestos como
    configuración en vez de constantes fijas del notebook. Los valores
    por defecto son los del notebook (NP=150, G_max=2000, F=0.7,
    CR=0.85, tol=1e-4); ajustar requiere revalidar tiempos de cómputo.
    W_p/W_o pesan el error de posición vs. orientación en la función de
    costo (ver cost_function_grasp); seed fija el generador aleatorio
    de differential_evolution_ik para que la resolución sea
    determinística dentro de una misma sesión (ver §2.1)."""
    NP: int = 150
    G_max: int = 2000
    F: float = 0.7
    CR: float = 0.85
    tol: float = 1e-4
    W_p: float = 1.0
    W_o: float = 0.05
    seed: int | None = None

# Tolerancia de posición aceptada para considerar una solución válida,
# en mm. Distinta de DEConfig.tol (que es el umbral de PARADA del
# algoritmo, en unidades de la función de costo combinada).
POSITION_TOLERANCE_MM: float = 2.0  # a validar físicamente, ver §7

# Pasos de inclinación a reintentar si la verticalidad estricta no
# converge, en grados sexagesimales respecto a la vertical.
TILT_RETRY_STEPS_DEG: list[float] = [0.0, 10.0, 20.0, 30.0]
MAX_TILT_DEG: float = 30.0  # a validar contra geometría real de pinza/pieza

SAFE_TRAVEL_HEIGHT_MM: float = 80.0  # PLACEHOLDER — ver §7, medir con set real
```

### 3.3 Errores

```python
class KinematicsError(Exception):
    """Clase base de errores de contrato de chess_kinematics."""

class UnreachableLocationError(KinematicsError):
    """Ninguna orientación (vertical estricta ni las inclinaciones de
    TILT_RETRY_STEPS_DEG) permitió converger dentro de
    POSITION_TOLERANCE_MM, para `grasp` y/o `transit` de esta Location.
    Se lanza al construir el JointMap, nunca durante la partida."""

class JointMapSessionNotFoundError(KinematicsError):
    """Análogo a CalibrationSessionNotFoundError (M0): no existe un
    JointMap de sesión válido para la partida actual."""
```

## 4. Diseño interno

### 4.1 `kinematics_ik.py` — DK/IK puros (adaptado del notebook)

```python
# Reutilizados del notebook SIN CAMBIOS en el algoritmo:
#   compute_dh_matrix, _full_thetas_rad, compute_joint_transforms,
#   forward_kinematics, differential_evolution_ik (DE/rand/1/bin)
#
# Se retiran del contrato de producto (quedan como utilidades de
# desarrollo/debug, no parte de este SPEC): plot_robot, print_dh_table,
# print_fk_results, print_ik_results, plot_convergence — no aportan al
# pipeline headless de sesión.

def mm_to_m(point: ArmPoint) -> np.ndarray:
    """Conversión explícita de unidades: CalibrationMap está en mm,
    DH_PARAMS del notebook está en metros. Punto de conversión único
    para evitar el error de unidades silencioso."""

def build_target_pose(point: ArmPoint, tilt_deg: float = 0.0) -> np.ndarray:
    """Construye T_des (4x4): posición desde mm_to_m(point); orientación
    vertical (eje Z del efector hacia -Z mundo) inclinada `tilt_deg`
    grados respecto a la vertical (0.0 = estrictamente vertical)."""

def orientation_error_roll_invariant(T_des: np.ndarray, T_curr: np.ndarray) -> float:
    """Reemplaza _orientation_error del notebook para este caso de uso:
    compara solo la dirección del eje Z del efector (2 DOF), ignorando
    rotación alrededor de ese eje. Ver §2.3."""

def cost_function_grasp(...) -> float:
    """Igual estructura que cost_function del notebook, pero usando
    orientation_error_roll_invariant en vez de _orientation_error."""

def solve_ik(
    point: ArmPoint, tilt_deg: float, de_config: DEConfig,
) -> tuple[JointAngles, float]:
    """Envuelve differential_evolution_ik del notebook (algoritmo DE sin
    modificar) con build_target_pose y cost_function_grasp. Retorna los
    5 ángulos activos + el error final de la función de costo."""
```

### 4.2 `kinematics_map.py` — construcción y persistencia del `JointMap`

```python
def solve_location(
    location: Location,
    point: ArmPoint,
    safe_travel_height_mm: float = SAFE_TRAVEL_HEIGHT_MM,
    de_config: DEConfig = DEConfig(),
    position_tolerance_mm: float = POSITION_TOLERANCE_MM,
    tilt_steps_deg: tuple[float, ...] = TILT_RETRY_STEPS_DEG,
) -> LocationSolution:
    # location se agregó para identificar la ubicación en el mensaje de
    # UnreachableLocationError; tuple en vez de list para el default,
    # evitando el antipatrón de argumento por defecto mutable.
    """Resuelve grasp y transit para un punto. Para cada uno, prueba
    tilt_steps_deg en orden hasta que el error de posición esté dentro
    de position_tolerance_mm; si ninguna inclinación converge, propaga
    UnreachableLocationError. orientation_relaxed=True si tilt_deg > 0
    en cualquiera de los dos."""

def build_joint_map(
    calibration_map: CalibrationMap,
    safe_travel_height_mm: float = SAFE_TRAVEL_HEIGHT_MM,
    de_config: DEConfig = DEConfig(),
    position_tolerance_mm: float = POSITION_TOLERANCE_MM,
    tilt_steps_deg: tuple[float, ...] = TILT_RETRY_STEPS_DEG,
) -> JointMap:
    """Punto de entrada único de este archivo. Itera las 68 Locations de
    calibration_map, llama solve_location por cada una. Se ejecuta UNA
    VEZ por sesión de juego, inmediatamente después de M0 y antes de que
    el Orquestador (M10) arranque el ciclo de partida — mismo rol que
    calibration_main.py, pero para ángulos articulares.
    Tiempo esperado: del orden de minutos en el hardware del BOM (CPU
    del Host, sin necesitar la GPU reservada para Visión) — aceptable
    por ser un paso de preparación de sesión, no de tiempo real.
    Nota de diseño (no v1): los 68 problemas de IK son independientes
    entre sí y paralelizables (multiprocessing) si el tiempo de
    preparación resulta impráctico — ver §7."""

def save_joint_map_session(joint_map: JointMap, path: str) -> None:
    """Persiste el JointMap resuelto a JSON, análogo a
    save_calibration_session (M0)."""

def load_joint_map_session(path: str) -> JointMap:
    """Carga un JointMap ya resuelto. Lanza JointMapSessionNotFoundError
    si el archivo no existe o está incompleto (< 68 claves)."""
```

### 4.3 `kinematics_planner.py` — de `PhysicalPlan` a `ArmTrajectory`

```python
def _is_discard_zone(location: Location) -> bool:
    """True si location es Zone.DISCARD_WHITE/BLACK. Estas zonas no
    requieren descenso preciso (BOM §5: la pieza se libera por caída en
    bandeja) — se simplifican a un único waypoint TRANSIT + OPEN, sin
    pasar por GRASP."""

def _location_release_sequence(
    location: Location, solution: LocationSolution, gripper_action: GripperAction,
) -> list[ArmWaypoint]:
    """Para una casilla o Zone.SPARE_*: [TRANSIT+HOLD, GRASP+gripper_action,
    TRANSIT+HOLD]. Para Zone.DISCARD_*: [TRANSIT+gripper_action] (ver
    _is_discard_zone)."""

def plan_transfer(transfer: PieceTransfer, joint_map: JointMap) -> ArmTrajectory:
    """Traduce un único PieceTransfer a su secuencia de waypoints:
    _location_release_sequence(origin, ..., CLOSE) +
    _location_release_sequence(destination, ..., OPEN).
    NO vuelve a invocar IK: solo consulta joint_map[location]."""

def plan_trajectory(physical_plan: PhysicalPlan, joint_map: JointMap) -> ArmTrajectory:
    """Punto de entrada único de chess_kinematics para el ciclo de
    partida. Concatena plan_transfer(transfer, joint_map) para cada
    PieceTransfer del PhysicalPlan, en orden. Este es el contrato de
    salida hacia M8 (resuelve el pendiente de GENERAL_SPEC.md §4.2:
    'M7 → M8: formato de ángulos de articulación / trayectoria')."""
```

### 4.4 `__init__.py` — Superficie pública

```python
from chess_kinematics.kinematics_map import (
    build_joint_map, save_joint_map_session, load_joint_map_session,
)
from chess_kinematics.kinematics_planner import plan_trajectory
from chess_kinematics.kinematics_types import (
    JointAngles, GripperAction, WaypointKind, ArmWaypoint, ArmTrajectory,
    LocationSolution, JointMap, DEConfig,
    KinematicsError, UnreachableLocationError, JointMapSessionNotFoundError,
)
```

Igual que en los módulos anteriores, este es el único contrato que M8 y
el futuro Orquestador (M10) deberían asumir estable. El Orquestador debe
llamar `build_joint_map` una vez por sesión (después de M0, antes de la
partida) y `plan_trajectory` una vez por cada `MoveResult` del motor
(después de M6).

## 5. Estructura del proyecto

```structure
chess-robot-arm/
├── src/
│   ├── chess_brain/                   # M4-5 (implementado)
│   ├── chess_vision/                  # M2-3 (implementado)
│   ├── chess_planner/                 # M6 (implementado)
│   ├── chess_calibration/             # M0 (implementado)
│   └── chess_kinematics/              # M7 (a implementar)
│       ├── __init__.py
│       ├── M7_SPEC.md
│       ├── kinematics_types.py         # JointAngles, ArmWaypoint, JointMap, DEConfig, excepciones
│       ├── kinematics_ik.py            # DK/IK (adaptado de chess_robot_arm_dk_ik.py)
│       ├── kinematics_map.py           # build_joint_map, save/load session
│       └── kinematics_planner.py       # plan_trajectory
└── tests/
    ├── test_brain/
    ├── test_vision/
    ├── test_planner/
    ├── test_calibration/
    └── test_kinematics/
        ├── __init__.py
        ├── test_kinematics_ik.py
        ├── test_kinematics_map.py
        ├── test_kinematics_planner.py
        └── fixtures/
            ├── __init__.py
            └── sample_joint_map.py      # JointMap de prueba, sin correr DE real
```

No se requieren dependencias nuevas más allá de `numpy` (ya usado en el
notebook). El notebook `chess_robot_arm_dk_ik.py` deja de ser un
artefacto standalone y se convierte en la base de `kinematics_ik.py`,
depurado de las partes de visualización/CLI que no son parte del
contrato de producto (ver §4.1).

## 6. Plan de pruebas

### 6.1 `test_kinematics_ik.py`

| Caso                                                                | Verifica                                                                                       |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `mm_to_m` / conversión de unidades                                  | No hay mezcla mm/m en `build_target_pose`                                                      |
| `orientation_error_roll_invariant` vs `_orientation_error` original | Ignora rotación alrededor del eje de aproximación, no ignora inclinación real                  |
| FK ∘ IK converge (round-trip) sobre puntos conocidos                | Error de posición < `POSITION_TOLERANCE_MM`, reutilizando ejemplo del notebook (T_fk conocido) |
| IK sobre punto fuera de alcance (> 355 mm)                          | No converge dentro de tolerancia con ninguna inclinación                                       |

### 6.2 `test_kinematics_map.py`

| Caso                                                | Verifica                                                                           |
| --------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `solve_location` converge en vertical estricta      | `orientation_relaxed=False`                                                        |
| `solve_location` requiere inclinación               | Prueba con punto sintético cerca del borde de alcance → `orientation_relaxed=True` |
| `solve_location` no converge en ninguna inclinación | `UnreachableLocationError`                                                         |
| `build_joint_map` produce 68 entradas               | A partir de un `CalibrationMap` de prueba (fixture, no medición real)              |
| Round-trip de sesión JSON                           | `save_joint_map_session` + `load_joint_map_session`                                |
| Sesión faltante/incompleta                          | `JointMapSessionNotFoundError`                                                     |

### 6.3 `test_kinematics_planner.py`

| Caso                                           | Verifica                                                                                 |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Movimiento normal (sin captura)                | 6 waypoints: TRANSIT/GRASP+CLOSE/TRANSIT (origen) + TRANSIT/GRASP+OPEN/TRANSIT (destino) |
| Captura simple                                 | Secuencia para 2 `PieceTransfer` concatenada en orden                                    |
| Transfer con destino `Zone.DISCARD_*`          | Secuencia simplificada (sin GRASP), solo TRANSIT+OPEN                                    |
| Transfer con origen `Zone.SPARE_*` (promoción) | Secuencia completa (SÍ requiere GRASP, a diferencia de DISCARD)                          |
| `plan_trajectory` no invoca IK                 | Verificar (mock/spy) que no se llama `solve_ik` — solo lookups a `joint_map`             |

## 7. Pendiente (fuera de alcance de este SPEC)

- **Medir `SAFE_TRAVEL_HEIGHT_MM` real**: el valor de este SPEC es un
  placeholder. Depende de la pieza más alta del set físico (típicamente
  el Rey) + margen. Candidato a incorporarse al protocolo de medición
  manual de `M0_SPEC.md` §4, ya que es una medición física del mismo
  tipo (regla/calibre) que las demás.
- **Validar `POSITION_TOLERANCE_MM`, `TILT_RETRY_STEPS_DEG` y
  `MAX_TILT_DEG`** contra la geometría real de la pinza (apertura máx.
  55 mm, BOM §3) y el tamaño de base de las piezas — no derivados de
  ninguna medición en este SPEC.
- **Paralelización de `build_joint_map`**: los 136 problemas de IK son
  independientes; si el tiempo de preparación de sesión resulta
  impráctico en el hardware real, paralelizar con `multiprocessing` es
  una mejora natural, no incluida en v1 (YAGNI hasta medir el tiempo
  real).
- **Contrato M7 → M8**: este SPEC entrega `ArmTrajectory`
  (`kinematics_planner.plan_trajectory`); queda para el SPEC de M8
  decidir cómo interpolar/temporizar entre waypoints consecutivos y qué
  hacer si la ejecución física falla a mitad de una `ArmTrajectory`.
- **Invalidación de `JointMap` ante recalibración**: si M0 recalibra a
  mitad de sesión (no debería ocurrir por diseño, pero no está impedido
  por software), el `JointMap` cacheado quedaría desincronizado — no
  hay verificación cruzada en v1.
- **Gestión de inventario de piezas de repuesto** (`SPARE_*`): sigue sin
  resolver, ya señalado como pendiente en `M6_SPEC.md` §7 — no cambia
  con este SPEC.
