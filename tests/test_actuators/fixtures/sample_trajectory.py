"""ArmTrajectory y ActuatorCalibration de prueba, sin depender de M0/M7
reales -- mismo espíritu que sample_joint_map.py en M7."""
from chess_kinematics import ArmWaypoint, GripperAction, JointAngles, WaypointKind

from chess_actuators.actuator_types import (
    ActuatorCalibration,
    GripperCalibration,
    ServoChannelCalibration,
)


def build_sample_calibration() -> ActuatorCalibration:
    joints = {
        key: ServoChannelCalibration(
            channel=i,
            pulse_min_us=500.0,
            pulse_max_us=2500.0,
            angle_min_deg=-90.0,
            angle_max_deg=90.0,
            reversed=(key == "q3"),
        )
        for i, key in enumerate(("q1", "q2", "q3", "q4", "q5"))
    }
    gripper = GripperCalibration(channel=5, pulse_open_us=1500.0, pulse_closed_us=900.0)
    return ActuatorCalibration(joints=joints, gripper=gripper)


def _angles(q1: float, q2: float, q3: float, q4: float, q5: float) -> JointAngles:
    return JointAngles(q1_deg=q1, q2_deg=q2, q3_deg=q3, q4_deg=q4, q5_deg=q5)


def build_sample_trajectory() -> list[ArmWaypoint]:
    """Movimiento normal simplificado: TRANSIT/GRASP+CLOSE/TRANSIT
    (origen) + TRANSIT/GRASP+OPEN/TRANSIT (destino) -- 6 waypoints,
    mismo patrón que test_kinematics_planner.py (M7)."""
    return [
        ArmWaypoint("e2", _angles(0, 10, 20, 0, 0), GripperAction.HOLD, WaypointKind.TRANSIT),
        ArmWaypoint("e2", _angles(0, 30, 40, 0, 0), GripperAction.CLOSE, WaypointKind.GRASP),
        ArmWaypoint("e2", _angles(0, 10, 20, 0, 0), GripperAction.HOLD, WaypointKind.TRANSIT),
        ArmWaypoint("e4", _angles(20, 10, 20, 0, 0), GripperAction.HOLD, WaypointKind.TRANSIT),
        ArmWaypoint("e4", _angles(20, 30, 40, 0, 0), GripperAction.OPEN, WaypointKind.GRASP),
        ArmWaypoint("e4", _angles(20, 10, 20, 0, 0), GripperAction.HOLD, WaypointKind.TRANSIT),
    ]
