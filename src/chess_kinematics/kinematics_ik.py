"""Cinemática directa e inversa del ROT3U — núcleo headless.

Adaptado de chess_robot_arm_dk_ik.py (notebook original). El algoritmo de
Evolución Diferencial (DE/rand/1/bin) NO se modifica; lo que cambia
respecto al notebook:

- Se retiran plotting/prints de progreso (quedan fuera del contrato de
  producto de M7 — ver M7_SPEC.md §4.1).
- La función de costo usa `orientation_error_roll_invariant` en vez de
  la comparación de matriz de rotación completa: el agarre es simétrico
  (pinza sobre pieza redonda), así que el giro de muñeca (q5) es un
  grado de libertad libre que no debe penalizarse (ver M7_SPEC.md §2.3).
- Los puntos objetivo llegan en milímetros (ArmPoint de chess_calibration);
  la conversión a metros (unidad del DH del notebook) es explícita en
  `mm_to_m`, para evitar el error de unidades silencioso.

(!) ASUNCIÓN A VALIDAR (no verificable sin el hardware/código de montaje
real): se asume que el eje Z local del frame 6 (según la convención D-H
de este módulo) es el eje de aproximación de la pinza. Si el montaje
físico real de la pinza sobre el efector no coincide con esa
convención, hay que agregar una matriz de corrección fija de montaje en
`build_target_pose` antes de usar este módulo con el brazo real.
"""

from __future__ import annotations

import numpy as np

from chess_calibration.calibration_types import ArmPoint
from chess_kinematics.kinematics_types import DEConfig

# ---------------------------------------------------------------------------
# Parámetros D-H y límites articulares (idénticos a chess_robot_arm_dk_ik.py)
# ---------------------------------------------------------------------------

DH_PARAMS_DEG = {
    "d": [0.090, 0.000, 0.000, 0.000, 0.085, 0.000],
    "a": [0.000, 0.150, 0.120, 0.000, 0.000, 0.000],
    "alpha": [90.0, 0.0, 0.0, 90.0, 0.0, 0.0],
}

JOINT_LIMITS_DEG = [
    (-90.0, 90.0),  # q1: Base (Yaw)
    (-90.0, 90.0),  # q2: Hombro (Pitch)
    (-90.0, 90.0),  # q3: Codo (Pitch)
    (-90.0, 90.0),  # q4: Flexión de Muñeca (Pitch)
    (-90.0, 90.0),  # q5: Giro de Muñeca (Roll)
    (0.0, 0.0),  # q6: Pinza (fijo, no participa en la cinemática de posición)
]

ACTIVE_JOINTS = [0, 1, 2, 3, 4]
FIXED_JOINTS_DEG = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

DH_PARAMS = {
    "d": DH_PARAMS_DEG["d"],
    "a": DH_PARAMS_DEG["a"],
    "alpha": [np.deg2rad(a) for a in DH_PARAMS_DEG["alpha"]],
}
JOINT_LIMITS = [(np.deg2rad(lo), np.deg2rad(hi)) for lo, hi in JOINT_LIMITS_DEG]


# ---------------------------------------------------------------------------
# Cinemática directa (idéntica al notebook)
# ---------------------------------------------------------------------------


def compute_dh_matrix(theta: float, d: float, a: float, alpha: float) -> np.ndarray:
    """Matriz de transformación homogénea local A_{i,i+1} (4x4), D-H clásico."""
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = np.cos(alpha), np.sin(alpha)
    return np.array(
        [
            [ct, -st * ca, st * sa, a * ct],
            [st, ct * ca, -ct * sa, a * st],
            [0, sa, ca, d],
            [0, 0, 0, 1],
        ],
        dtype=float,
    )


def _full_thetas_rad(
    active_thetas_deg: list | np.ndarray,
    active_joints: list = ACTIVE_JOINTS,
    fixed_deg: list = FIXED_JOINTS_DEG,
) -> np.ndarray:
    """Reconstruye el vector completo de 6 ángulos [rad] combinando las
    articulaciones activas con los valores fijos de las congeladas."""
    full_deg = np.array(fixed_deg, dtype=float)
    for k, idx in enumerate(active_joints):
        full_deg[idx] = active_thetas_deg[k]
    return np.deg2rad(full_deg)


def compute_joint_transforms(
    thetas_rad: list | np.ndarray, dh: dict = DH_PARAMS
) -> list[np.ndarray]:
    """Matrices homogéneas acumuladas T_{0,i} para cada articulación
    (incluyendo la base). Retorna 7 matrices 4x4: [T_00, ..., T_06]."""
    T = np.eye(4)
    transforms = [T.copy()]
    for i in range(6):
        A_i = compute_dh_matrix(thetas_rad[i], dh["d"][i], dh["a"][i], dh["alpha"][i])
        T = T @ A_i
        transforms.append(T.copy())
    return transforms


def forward_kinematics(
    thetas_deg: list | np.ndarray,
    dh: dict = DH_PARAMS,
    active_joints: list = ACTIVE_JOINTS,
    fixed_deg: list = FIXED_JOINTS_DEG,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Cinemática directa completa.

    Retorna (T_0_6, local_transforms): pose 4x4 del efector y la lista
    de las 6 matrices locales A_{i,i+1}.
    """
    thetas_rad = _full_thetas_rad(thetas_deg, active_joints, fixed_deg)
    T = np.eye(4)
    local_transforms = []
    for i in range(6):
        A_i = compute_dh_matrix(thetas_rad[i], dh["d"][i], dh["a"][i], dh["alpha"][i])
        local_transforms.append(A_i.copy())
        T = T @ A_i
    return T, local_transforms


# ---------------------------------------------------------------------------
# Conversión de unidades y pose objetivo
# ---------------------------------------------------------------------------


def mm_to_m(point: ArmPoint) -> np.ndarray:
    """Convierte un ArmPoint (mm, de chess_calibration) a un vector
    posición en metros (unidad de DH_PARAMS). Punto de conversión único
    para evitar mezclar mm/m en el resto del módulo."""
    return np.array([point.x_mm, point.y_mm, point.z_mm], dtype=float) / 1000.0


def _rodrigues_rotate(v: np.ndarray, axis: np.ndarray, angle_rad: float) -> np.ndarray:
    """Rota el vector v un ángulo angle_rad alrededor de axis (unitario),
    fórmula de rotación de Rodrigues."""
    axis = axis / np.linalg.norm(axis)
    return (
        v * np.cos(angle_rad)
        + np.cross(axis, v) * np.sin(angle_rad)
        + axis * np.dot(axis, v) * (1.0 - np.cos(angle_rad))
    )


def build_target_pose(point: ArmPoint, tilt_deg: float = 0.0) -> np.ndarray:
    """Construye T_des (4x4): posición desde mm_to_m(point); orientación
    de aproximación vertical (eje Z del efector hacia -Z mundo), inclinada
    `tilt_deg` grados respecto a la vertical.

    La inclinación se aplica en el plano vertical que contiene la
    dirección radial base->punto (la única dirección en la que este
    brazo puede relajar la verticalidad dado que q1 controla el acimut y
    q2+q3+q4 controlan la postura en ese plano — ver M7_SPEC.md §2.3).
    El giro alrededor del propio eje de aproximación (roll) queda libre
    y no se fuerza a ningún valor particular: solo se calcula un marco
    ortonormal válido, no necesariamente el mismo que produce la IK.
    """
    p = mm_to_m(point)

    horizontal_radius = np.linalg.norm(p[:2])
    if horizontal_radius < 1e-9:
        radial_dir = np.array([1.0, 0.0, 0.0])
    else:
        radial_dir = np.array([p[0], p[1], 0.0]) / horizontal_radius

    tangential_dir = np.array([-radial_dir[1], radial_dir[0], 0.0])

    nominal_down = np.array([0.0, 0.0, -1.0])
    z_axis_des = _rodrigues_rotate(nominal_down, tangential_dir, np.deg2rad(tilt_deg))
    z_axis_des = z_axis_des / np.linalg.norm(z_axis_des)

    x_axis_des = radial_dir - np.dot(radial_dir, z_axis_des) * z_axis_des
    if np.linalg.norm(x_axis_des) < 1e-9:
        # radial_dir casi paralelo a z_axis_des (caso degenerado): usar
        # tangential_dir como base alternativa para el marco.
        x_axis_des = tangential_dir - np.dot(tangential_dir, z_axis_des) * z_axis_des
    x_axis_des = x_axis_des / np.linalg.norm(x_axis_des)

    y_axis_des = np.cross(z_axis_des, x_axis_des)
    y_axis_des = y_axis_des / np.linalg.norm(y_axis_des)
    x_axis_des = np.cross(y_axis_des, z_axis_des)

    R_des = np.column_stack([x_axis_des, y_axis_des, z_axis_des])

    T_des = np.eye(4)
    T_des[:3, :3] = R_des
    T_des[:3, 3] = p
    return T_des


# ---------------------------------------------------------------------------
# Función de costo (posición + orientación con invariancia de roll)
# ---------------------------------------------------------------------------


def _position_error(p_des: np.ndarray, p_curr: np.ndarray) -> float:
    return float(np.linalg.norm(p_des - p_curr))


def orientation_error_roll_invariant(T_des: np.ndarray, T_curr: np.ndarray) -> float:
    """Error angular [rad] entre el eje Z (dirección de aproximación) de
    T_des y T_curr, ignorando la rotación alrededor de ese eje (roll).

    Reemplaza a la comparación de matriz de rotación completa del
    notebook original para este caso de uso: el agarre es simétrico, así
    que penalizar el roll solo reduce artificialmente el conjunto de
    soluciones válidas sin aportar nada al agarre real.
    """
    z_des = T_des[:3, 2]
    z_curr = T_curr[:3, 2]
    cos_angle = np.clip(np.dot(z_des, z_curr), -1.0, 1.0)
    return float(np.arccos(cos_angle))


def cost_function_grasp(
    active_thetas_deg: np.ndarray,
    T_des: np.ndarray,
    active_limits_rad: list,
    active_joints: list = ACTIVE_JOINTS,
    fixed_deg: list = FIXED_JOINTS_DEG,
    W_p: float = 1.0,
    W_o: float = 0.05,
) -> float:
    """Costo de una configuración articular respecto a la pose deseada.

    Misma estructura que cost_function del notebook (penalización 1e6 si
    viola límites articulares, W_p * error_posición + W_o *
    error_orientación_normalizado), pero con
    orientation_error_roll_invariant en vez de _orientation_error.
    """
    thetas_rad = np.deg2rad(active_thetas_deg)
    for k, (lo, hi) in enumerate(active_limits_rad):
        if thetas_rad[k] < lo or thetas_rad[k] > hi:
            return 1e6

    T_curr, _ = forward_kinematics(
        active_thetas_deg, DH_PARAMS, active_joints, fixed_deg
    )

    e_pos = _position_error(T_des[:3, 3], T_curr[:3, 3])
    e_ori = orientation_error_roll_invariant(T_des, T_curr)
    e_ori_norm = e_ori / np.pi

    return W_p * e_pos + W_o * e_ori_norm


# ---------------------------------------------------------------------------
# Evolución Diferencial (DE/rand/1/bin) — mismo algoritmo del notebook
# ---------------------------------------------------------------------------


def differential_evolution_ik(
    T_des: np.ndarray,
    de_config: DEConfig = DEConfig(),
    active_joints: list = ACTIVE_JOINTS,
    fixed_deg: list = FIXED_JOINTS_DEG,
) -> tuple[np.ndarray, float, list[float]]:
    """Resuelve la IK mediante Evolución Diferencial (DE/rand/1/bin).

    Mismo algoritmo que chess_robot_arm_dk_ik.py; headless (sin prints),
    parametrizado vía DEConfig, con generador aleatorio local (no usa
    np.random global) para no tener efectos colaterales entre llamadas.

    Retorna (best_active_deg, best_cost, history).
    """
    rng = np.random.default_rng(de_config.seed)

    for i, val in enumerate(fixed_deg):
        if i not in active_joints:
            lo, hi = JOINT_LIMITS_DEG[i]
            if val < lo or val > hi:
                raise ValueError(
                    f"El valor fijo de la articulación {i + 1} ({val}°) "
                    f"está fuera de sus límites ({lo}°, {hi}°)."
                )

    D = len(active_joints)
    active_limits_deg = [JOINT_LIMITS_DEG[j] for j in active_joints]
    active_limits_rad = [JOINT_LIMITS[j] for j in active_joints]

    pop = np.column_stack(
        [
            rng.uniform(active_limits_deg[k][0], active_limits_deg[k][1], de_config.NP)
            for k in range(D)
        ]
    )

    def _cost(ind: np.ndarray) -> float:
        return cost_function_grasp(
            ind,
            T_des,
            active_limits_rad,
            active_joints,
            fixed_deg,
            de_config.W_p,
            de_config.W_o,
        )

    fitness = np.array([_cost(ind) for ind in pop])
    best_idx = int(np.argmin(fitness))
    best_vector = pop[best_idx].copy()
    best_cost = float(fitness[best_idx])
    history = [best_cost]

    for _ in range(1, de_config.G_max + 1):
        for i in range(de_config.NP):
            candidates = [idx for idx in range(de_config.NP) if idx != i]
            r1, r2, r3 = rng.choice(candidates, 3, replace=False)

            v = pop[r1] + de_config.F * (pop[r2] - pop[r3])

            j_rand = rng.integers(D)
            mask = rng.random(D) <= de_config.CR
            mask[j_rand] = True
            trial = np.where(mask, v, pop[i])

            trial_cost = _cost(trial)
            if trial_cost <= fitness[i]:
                pop[i] = trial
                fitness[i] = trial_cost
                if trial_cost < best_cost:
                    best_cost = trial_cost
                    best_vector = trial.copy()

        history.append(best_cost)
        if best_cost < de_config.tol:
            break

    return best_vector, best_cost, history


# ---------------------------------------------------------------------------
# Punto de entrada de IK para un único punto cartesiano
# ---------------------------------------------------------------------------


def solve_ik(
    point: ArmPoint,
    tilt_deg: float = 0.0,
    de_config: DEConfig = DEConfig(),
):
    """Resuelve IK para un punto cartesiano (mm) con la inclinación dada.

    Retorna (JointAngles, position_error_mm). `position_error_mm` es el
    error de posición REAL (no el costo combinado de DE) — es lo que
    kinematics_map compara contra POSITION_TOLERANCE_MM para decidir si
    la solución es aceptable.
    """
    from chess_kinematics.kinematics_types import JointAngles  # evita import circular

    T_des = build_target_pose(point, tilt_deg)
    best_active_deg, _best_cost, _history = differential_evolution_ik(T_des, de_config)

    T_found, _ = forward_kinematics(best_active_deg)
    position_error_mm = float(np.linalg.norm(T_des[:3, 3] - T_found[:3, 3]) * 1000.0)

    joint_angles = JointAngles(*[float(v) for v in best_active_deg])
    return joint_angles, position_error_mm
