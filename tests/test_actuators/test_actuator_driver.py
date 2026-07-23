from unittest.mock import MagicMock, patch

import pytest

from chess_actuators.actuator_driver import (
    SerialActuatorDriver,
    SimulatedActuatorDriver,
)
from chess_actuators.actuator_types import ActuatorConfig, ActuatorConnectionError


def test_simulated_driver_send_set_no_failures():
    driver = SimulatedActuatorDriver()
    driver.connect()

    driver.send_set({0: 1500, 5: 900})

    assert driver.connected is True
    assert driver.sent_commands == [{0: 1500, 5: 900}]


def test_simulated_driver_fail_at_specific_call():
    driver = SimulatedActuatorDriver(
        fail_at={1}
    )  # falla solo en la 2da llamada (índice 1)
    driver.connect()

    driver.send_set({0: 1500})  # llamada 0: éxito
    with pytest.raises(ActuatorConnectionError):
        driver.send_set({0: 1600})  # llamada 1: fallo simulado
    driver.send_set({0: 1700})  # llamada 2: éxito

    assert driver.sent_commands == [{0: 1500}, {0: 1700}]


def test_serial_driver_connect_no_pong_raises():
    config = ActuatorConfig(serial_port="COM_TEST", ack_timeout_s=0.1)
    driver = SerialActuatorDriver(config)

    fake_serial_instance = MagicMock()
    fake_serial_instance.readline.return_value = b""  # timeout: sin respuesta

    fake_serial_module = MagicMock()
    fake_serial_module.Serial.return_value = fake_serial_instance
    fake_serial_module.SerialException = Exception

    with patch.dict("sys.modules", {"serial": fake_serial_module}):
        with pytest.raises(ActuatorConnectionError):
            driver.connect()


def test_serial_driver_connect_success_then_send_set():
    config = ActuatorConfig(serial_port="COM_TEST", ack_timeout_s=0.1)
    driver = SerialActuatorDriver(config)

    fake_serial_instance = MagicMock()
    fake_serial_instance.readline.side_effect = [b"PONG\n", b"ACK\n"]

    fake_serial_module = MagicMock()
    fake_serial_module.Serial.return_value = fake_serial_instance
    fake_serial_module.SerialException = Exception

    with patch.dict("sys.modules", {"serial": fake_serial_module}):
        driver.connect()
        driver.send_set({0: 1500})

    fake_serial_instance.write.assert_any_call(b"PING\n")
    fake_serial_instance.write.assert_any_call(b"SET 0:1500\n")


def test_serial_driver_send_set_err_raises_value_error():
    config = ActuatorConfig(serial_port="COM_TEST", ack_timeout_s=0.1)
    driver = SerialActuatorDriver(config)

    fake_serial_instance = MagicMock()
    fake_serial_instance.readline.side_effect = [b"PONG\n", b"ERR 2\n"]

    fake_serial_module = MagicMock()
    fake_serial_module.Serial.return_value = fake_serial_instance
    fake_serial_module.SerialException = Exception

    with patch.dict("sys.modules", {"serial": fake_serial_module}):
        driver.connect()
        with pytest.raises(ValueError):
            driver.send_set({0: 9999})
