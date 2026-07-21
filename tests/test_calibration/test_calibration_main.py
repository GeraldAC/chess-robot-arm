import json
from pathlib import Path

from chess_calibration.calibration_main import run

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURES_DIR / "sample_calibration.yaml"


class TestCalibrationMainCLI:
    def test_end_to_end_success_writes_session_file(self, tmp_path, capsys):
        output_path = tmp_path / "calibration_session.json"

        exit_code = run(
            [
                "--input",
                str(SAMPLE_YAML),
                "--square-size-mm",
                "40.0",
                "--output",
                str(output_path),
            ]
        )

        assert exit_code == 0
        assert output_path.exists()

        session = json.loads(output_path.read_text())
        assert len(session) == 68

        captured = capsys.readouterr()
        assert "CalibrationMap resuelto: 68 entradas" in captured.out
        assert "Sesión de calibración guardada en" in captured.out

    def test_invalid_geometry_returns_error_exit_code(self, tmp_path, capsys):
        output_path = tmp_path / "calibration_session.json"

        exit_code = run(
            [
                "--input",
                str(SAMPLE_YAML),
                "--square-size-mm",
                "100.0",  # no coincide con la geometría real del fixture
                "--output",
                str(output_path),
            ]
        )

        assert exit_code == 1
        assert not output_path.exists()

        captured = capsys.readouterr()
        assert "Error de calibración" in captured.err

    def test_missing_input_file_returns_error_exit_code(self, tmp_path):
        exit_code = run(
            [
                "--input",
                str(tmp_path / "no_existe.yaml"),
                "--square-size-mm",
                "40.0",
            ]
        )
        assert exit_code == 1
