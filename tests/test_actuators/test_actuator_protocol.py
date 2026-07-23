import pytest

from chess_actuators.actuator_protocol import format_ping, format_set, parse_response


def test_format_ping():
    assert format_ping() == "PING\n"


def test_format_set_single_channel():
    assert format_set({0: 1500}) == "SET 0:1500\n"


def test_format_set_multiple_channels_deterministic_order():
    # Se pasan fuera de orden a propósito -- el formato debe salir
    # siempre ordenado por canal ascendente.
    pulses = {5: 900, 0: 1500, 3: 2000}
    assert format_set(pulses) == "SET 0:1500,3:2000,5:900\n"


def test_format_set_empty_raises():
    with pytest.raises(ValueError):
        format_set({})


@pytest.mark.parametrize("raw", ["PONG\n", "PONG\r\n", "PONG"])
def test_parse_response_pong(raw):
    assert parse_response(raw) == (True, None)


@pytest.mark.parametrize("raw", ["ACK\n", "ACK"])
def test_parse_response_ack(raw):
    assert parse_response(raw) == (True, None)


def test_parse_response_err_with_code():
    assert parse_response("ERR 2\n") == (False, "2")


def test_parse_response_err_without_code():
    assert parse_response("ERR\n") == (False, "")


def test_parse_response_unknown_raises():
    with pytest.raises(ValueError):
        parse_response("GARBAGE\n")


def test_parse_response_empty_raises():
    # Una línea vacía (timeout de lectura) NO es un formato conocido:
    # el llamador (actuator_driver.py) debe distinguir el timeout ANTES
    # de invocar parse_response, ver M8_SPEC.md §5.2.
    with pytest.raises(ValueError):
        parse_response("")
