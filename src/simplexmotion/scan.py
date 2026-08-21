"""Busgenomsökning: hitta vilka SimplexMotion-motorer som svarar på en buss."""

from __future__ import annotations

from dataclasses import dataclass

from . import registers as regs
from .transport import Transport, decode_string


@dataclass
class MotorInfo:
    address: int
    model_name: str
    serial_number: str


def scan_bus(transport: Transport, addresses: range = range(1, 32)) -> list[MotorInfo]:
    """Läs ModelName/SerialNumber på varje adress i ``addresses``.

    Adresser som inte svarar (timeout, felaktigt svar) hoppas tyst över --
    en full genomsökning av 1-31 innebär redan värsta fall en lång väntan om
    transporten har hög timeout, så håll timeouten kort på transportnivå.
    """
    found: list[MotorInfo] = []
    for address in addresses:
        try:
            model_words = transport.read_registers(regs.MODEL_NAME, regs.MODEL_NAME_LENGTH, address)
            serial_words = transport.read_registers(
                regs.SERIAL_NUMBER, regs.SERIAL_NUMBER_LENGTH, address
            )
        except Exception:
            continue
        found.append(
            MotorInfo(
                address=address,
                model_name=decode_string(model_words),
                serial_number=decode_string(serial_words),
            )
        )
    return found
