import pytest

from chess_kinematics import kinematics_ik
from chess_kinematics.kinematics_planner import plan_trajectory, plan_transfer
from chess_kinematics.kinematics_types import (
    GripperAction,
    KinematicsError,
    WaypointKind,
)
from chess_planner.movement_types import PieceTransfer, Zone
from test_kinematics.fixtures.sample_joint_map import sample_joint_map


@pytest.fixture()
def joint_map():
    return sample_joint_map()


def test_normal_move_has_six_waypoints_in_order(joint_map):
    transfer = PieceTransfer(origin="e2", destination="e4", piece="P", color="w")
    trajectory = plan_transfer(transfer, joint_map)

    assert len(trajectory) == 6
    kinds = [wp.kind for wp in trajectory]
    assert kinds == [
        WaypointKind.TRANSIT,
        WaypointKind.GRASP,
        WaypointKind.TRANSIT,
        WaypointKind.TRANSIT,
        WaypointKind.GRASP,
        WaypointKind.TRANSIT,
    ]

    grippers = [wp.gripper for wp in trajectory]
    assert grippers == [
        GripperAction.HOLD,
        GripperAction.CLOSE,
        GripperAction.HOLD,
        GripperAction.HOLD,
        GripperAction.OPEN,
        GripperAction.HOLD,
    ]

    locations = [wp.location for wp in trajectory]
    assert locations == ["e2", "e2", "e2", "e4", "e4", "e4"]


def test_capture_concatenates_two_transfers_in_order(joint_map):
    physical_plan = [
        PieceTransfer(
            origin="e5", destination=Zone.DISCARD_BLACK.value, piece="P", color="b"
        ),
        PieceTransfer(origin="e4", destination="e5", piece="P", color="w"),
    ]
    trajectory = plan_trajectory(physical_plan, joint_map)

    # primer transfer: discard como destino -> 3 (origen) + 1 (discard) = 4
    # segundo transfer: normal -> 6
    assert len(trajectory) == 4 + 6
    assert trajectory[0].location == "e5"
    assert trajectory[3].location == Zone.DISCARD_BLACK.value
    assert trajectory[3].kind == WaypointKind.TRANSIT
    assert trajectory[4].location == "e4"


def test_destination_discard_zone_is_simplified(joint_map):
    transfer = PieceTransfer(
        origin="e4", destination=Zone.DISCARD_WHITE.value, piece="P", color="w"
    )
    trajectory = plan_transfer(transfer, joint_map)

    # origen: secuencia completa (3) + destino: solo TRANSIT+OPEN (1)
    assert len(trajectory) == 4
    last = trajectory[-1]
    assert last.location == Zone.DISCARD_WHITE.value
    assert last.kind == WaypointKind.TRANSIT
    assert last.gripper == GripperAction.OPEN


def test_origin_spare_zone_requires_full_grasp_sequence(joint_map):
    transfer = PieceTransfer(
        origin=Zone.SPARE_WHITE.value, destination="e8", piece="Q", color="w"
    )
    trajectory = plan_transfer(transfer, joint_map)

    # SPARE_* SÍ requiere grasp preciso (a diferencia de DISCARD_*): 3 + 3 = 6
    assert len(trajectory) == 6
    assert trajectory[0].location == Zone.SPARE_WHITE.value
    assert trajectory[1].kind == WaypointKind.GRASP
    assert trajectory[1].gripper == GripperAction.CLOSE


def test_missing_location_raises_kinematics_error(joint_map):
    transfer = PieceTransfer(origin="z9", destination="e4", piece="P", color="w")
    with pytest.raises(KinematicsError):
        plan_transfer(transfer, joint_map)


def test_plan_trajectory_never_invokes_ik(monkeypatch, joint_map):
    """El planner solo debe hacer lookups sobre el JointMap ya resuelto,
    nunca volver a invocar DE (ver M7_SPEC.md §4.3)."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError(
            "plan_trajectory no debería invocar differential_evolution_ik"
        )

    monkeypatch.setattr(kinematics_ik, "differential_evolution_ik", _fail_if_called)

    physical_plan = [
        PieceTransfer(origin="e2", destination="e4", piece="P", color="w"),
        PieceTransfer(origin="e7", destination="e5", piece="P", color="b"),
    ]
    trajectory = plan_trajectory(physical_plan, joint_map)

    assert len(trajectory) == 12
