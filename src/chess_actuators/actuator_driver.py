"""Driver Serial: interfaz común + implementación real (pyserial) +
implementación simulada para tests y CLI sin hardware.

Ver M8_SPEC.md §5.3. El reintento ante fallos NO es responsabilidad de
este módulo (ver actuator_executor.py) — send_set aquí falla rápido,
sin reintentar.
"""

from __future__ import annotations

from typing import Protocol

from chess_actuators.actuator_protocol import format_ping, format_set, parse_response
from chess_actuators.actuator_types import ActuatorConfig, ActuatorConnectionError


class ActuatorDriver(Protocol):
    """Interfaz común entre el driver real y el simulado — permite que
    actuator_executor.py y los tests no dependan de pyserial ni de
    hardware conectado."""

    def connect(self) -> None: ...

    def send_set(self, pulses: dict[int, int]) -> None:
        """Envía un comando SET y espera ACK dentro de ack_timeout_s.
        Lanza ActuatorConnectionError en timeout/desconexión, ValueError
        si el firmware responde ERR. No reintenta."""
        ...

    def close(self) -> None: ...


class SerialActuatorDriver:
    """Implementación real sobre pyserial."""

    def __init__(self, config: ActuatorConfig) -> None:
        self._config = config
        self._serial = None  # type: ignore[var-annotated]

    def connect(self) -> None:
        # Import diferido: pyserial solo es necesario si de verdad se va
        # a hablar con hardware real (SimulatedActuatorDriver no lo
        # requiere, ver M8_SPEC.md §5.3).
        import serial  # noqa: PLC0415

        try:
            self._serial = serial.Serial(
                port=self._config.serial_port,
                baudrate=self._config.baudrate,
                timeout=self._config.ack_timeout_s,
            )
        except serial.SerialException as exc:
            raise ActuatorConnectionError(
                f"No se pudo abrir el puerto {self._config.serial_port}: {exc}"
            ) from exc

        self._serial.write(format_ping().encode("ascii"))
        raw = self._serial.readline().decode("ascii", errors="replace")
        if not raw:
            raise ActuatorConnectionError(
                f"Sin respuesta PONG del microcontrolador en {self._config.serial_port} "
                f"dentro de {self._config.ack_timeout_s}s"
            )
        success, _ = parse_response(raw)
        if not success:
            raise ActuatorConnectionError(f"Handshake PING falló: respuesta {raw!r}")

    def send_set(self, pulses: dict[int, int]) -> None:
        if self._serial is None:
            raise ActuatorConnectionError("send_set llamado antes de connect()")

        self._serial.write(format_set(pulses).encode("ascii"))
        raw = self._serial.readline().decode("ascii", errors="replace")
        if not raw:
            raise ActuatorConnectionError(
                f"Timeout esperando ACK/ERR ({self._config.ack_timeout_s}s)"
            )
        success, code = parse_response(raw)
        if not success:
            raise ValueError(f"Arduino reportó error: ERR {code}")

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None


class SimulatedActuatorDriver:
    """Implementación en memoria, sin hardware.

    Registra cada send_set en `sent_commands` (para asserts en tests) y
    responde con éxito inmediato salvo que el índice de la llamada (0
    based, contando solo llamadas a send_set) esté en `fail_at` — usado
    para testear la lógica de reintentos de actuator_executor.py sin
    hardware real, mismo espíritu que el simulador de Visión (M2/M3).
    """

    def __init__(self, fail_at: set[int] | None = None) -> None:
        self._fail_at = fail_at or set()
        self._call_count = 0
        self.connected = False
        self.sent_commands: list[dict[int, int]] = []

    def connect(self) -> None:
        self.connected = True

    def send_set(self, pulses: dict[int, int]) -> None:
        index = self._call_count
        self._call_count += 1
        if index in self._fail_at:
            raise ActuatorConnectionError(f"Fallo simulado en la llamada #{index}")
        self.sent_commands.append(dict(pulses))

    def close(self) -> None:
        self.connected = False
