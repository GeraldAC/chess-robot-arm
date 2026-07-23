import json
import os

from chess_actuators.actuator_main import main

FIXTURE_CALIBRATION = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_calibration.yaml"
)


def _write_trajectory_json(tmp_path) -> str:
    trajectory = [
        {
            "location": "e2",
            "joint_angles": {
                "q1_deg": 0,
                "q2_deg": 10,
                "q3_deg": 20,
                "q4_deg": 0,
                "q5_deg": 0,
            },
            "gripper": "HOLD",
            "kind": "TRANSIT",
        },
        {
            "location": "e2",
            "joint_angles": {
                "q1_deg": 0,
                "q2_deg": 30,
                "q3_deg": 40,
                "q4_deg": 0,
                "q5_deg": 0,
            },
            "gripper": "CLOSE",
            "kind": "GRASP",
        },
    ]
    path = tmp_path / "trajectory.json"
    path.write_text(json.dumps(trajectory))
    return str(path)


def test_cli_simulate_with_trajectory_success(tmp_path, capsys):
    trajectory_path = _write_trajectory_json(tmp_path)

    exit_code = main(
        [
            "--simulate",
            "--calibration",
            FIXTURE_CALIBRATION,
            "--trajectory",
            trajectory_path,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ejecución exitosa" in captured.out


def test_cli_missing_calibration_returns_1(capsys):
    exit_code = main(["--simulate"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--calibration" in captured.err


def test_cli_test_pulse_mode(capsys):
    exit_code = main(
        [
            "--simulate",
            "--calibration",
            FIXTURE_CALIBRATION,
            "--test-pulse",
            "0",
            "1500",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "SET 0:1500" in captured.out
