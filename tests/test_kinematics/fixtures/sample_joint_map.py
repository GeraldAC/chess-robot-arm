"""JointMap sintético para pruebas de kinematics_planner.

No corre DE — son ángulos arbitrarios, solo para verificar que
plan_trajectory arma la secuencia de waypoints correcta a partir de un
JointMap ya resuelto (que es la única entrada que el planner consume).
"""

from chess_kinematics.kinematics_types import JointAngles, LocationSolution
from chess_planner.movement_types import Zone


def _solution(seed: float) -> LocationSolution:
    return LocationSolution(
        grasp=JointAngles(seed, seed + 1, seed + 2, seed + 3, seed + 4),
        transit=JointAngles(seed, seed + 1, seed + 2, seed + 3 + 20, seed + 4),
        orientation_relaxed=False,
    )


def sample_joint_map() -> dict:
    locations = [
        "e2", "e4", "e5", "e7", "e8",
        Zone.DISCARD_WHITE.value,
        Zone.DISCARD_BLACK.value,
        Zone.SPARE_WHITE.value,
        Zone.SPARE_BLACK.value,
    ]
    return {loc: _solution(seed=i * 10.0) for i, loc in enumerate(locations)}
