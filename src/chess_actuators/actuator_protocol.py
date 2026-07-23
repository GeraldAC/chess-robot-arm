"""Framing y parsing del protocolo Serial Host <-> Arduino.

Ver M8_SPEC.md §3 para la tabla completa de comandos/respuestas.
Framing: texto ASCII, un comando por línea terminada en '\\n'.
"""

from __future__ import annotations


def format_ping() -> str:
    """Comando de handshake, usado por el driver antes de aceptar la
    conexión como válida."""
    return "PING\n"


def format_set(pulses: dict[int, int]) -> str:
    """Construye 'SET ch:pulse,ch:pulse,...\\n' a partir de un dict
    {canal: pulso_us}. Orden determinístico (canal ascendente) para
    reproducibilidad en logs/tests."""
    if not pulses:
        raise ValueError("format_set requiere al menos un canal")
    pairs = ",".join(f"{channel}:{pulses[channel]}" for channel in sorted(pulses))
    return f"SET {pairs}\n"


def parse_response(raw_line: str) -> tuple[bool, str | None]:
    """Interpreta una línea de respuesta del Arduino.

    Retorna (True, None) para 'PONG'/'ACK'; (False, código) para
    'ERR <code>'. Lanza ValueError si la línea no matchea ningún
    formato conocido (incluye el caso de línea vacía / timeout de
    lectura, que el llamador debe distinguir ANTES de invocar esto —
    ver actuator_driver.py).
    """
    line = raw_line.strip()
    if line in ("PONG", "ACK"):
        return True, None
    if line.startswith("ERR"):
        parts = line.split(maxsplit=1)
        code = parts[1] if len(parts) > 1 else ""
        return False, code
    raise ValueError(f"Respuesta del microcontrolador no reconocida: {raw_line!r}")
