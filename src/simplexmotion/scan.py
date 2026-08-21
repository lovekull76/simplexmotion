"""Bus scanning: find which SimplexMotion motors respond on a bus."""

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
    """Read ModelName/SerialNumber at every address in ``addresses``.

    Addresses that don't respond (timeout, malformed response) are silently
    skipped -- a full scan of 1-31 is already a long wait in the worst case
    if the transport has a high timeout, so keep the timeout short at the
    transport level.
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
