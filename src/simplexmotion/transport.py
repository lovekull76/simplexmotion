"""Transport layer: everything that speaks Modbus RTU in/out, no
interpretation of what the registers mean. See :class:`Transport` for the
protocol consumers can implement for their own hardware.
"""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Protocol

from . import registers as regs


class Transport(Protocol):
    """Minimal protocol a Modbus transport must satisfy.

    ``unit`` (the slave address) belongs to the call, not to the transport
    object, since several motors may share the same bus.
    """

    def read_registers(self, address: int, count: int, unit: int) -> list[int]: ...

    def write_register(self, address: int, value: int, unit: int) -> None: ...

    def write_registers(self, address: int, values: list[int], unit: int) -> None: ...


class PymodbusTransport:
    """Default transport, based on ``pymodbus`` (FC03 / FC06 / FC16).

    Owns the serial port. A single instance is shared between all
    :class:`~simplexmotion.motor.Motor` objects on the same bus -- an
    internal lock serializes access, since Modbus RTU is half duplex and
    cannot tolerate overlapping transactions.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 57600,
        parity: str = "E",
        bytesize: int = 8,
        stopbits: int = 1,
        timeout: float = 1.0,
    ) -> None:
        from pymodbus.client import ModbusSerialClient

        self._lock = threading.Lock()
        self._client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            bytesize=bytesize,
            stopbits=stopbits,
            timeout=timeout,
        )
        if not self._client.connect():
            raise ConnectionError(f"Could not open {port}")

    def close(self) -> None:
        self._client.close()

    def open(self) -> None:
        """Reopen the port after a :meth:`close`."""
        if not self._client.connect():
            raise ConnectionError("Could not reopen the port")

    def read_registers(self, address: int, count: int, unit: int) -> list[int]:
        with self._lock:
            result = self._client.read_holding_registers(address, count=count, slave=unit)
        if result.isError():
            raise IOError(f"Modbus read failed at {address} (unit {unit}): {result}")
        return list(result.registers)

    def write_register(self, address: int, value: int, unit: int) -> None:
        with self._lock:
            result = self._client.write_register(address, regs.to_unsigned16(value), slave=unit)
        if result.isError():
            raise IOError(f"Modbus write failed at {address} (unit {unit}): {result}")

    def write_registers(self, address: int, values: list[int], unit: int) -> None:
        raw = [regs.to_unsigned16(v) for v in values]
        with self._lock:
            result = self._client.write_registers(address, raw, slave=unit)
        if result.isError():
            raise IOError(f"Modbus write failed at {address} (unit {unit}): {result}")


class FakeTransport:
    """Plays back/holds registers in memory -- no connected motor required.

    Useful for development and testing. Several ``unit`` addresses can be
    seeded independently within the same instance.
    """

    def __init__(self) -> None:
        self._registers: dict[int, dict[int, int]] = {}

    def _bank(self, unit: int) -> dict[int, int]:
        return self._registers.setdefault(unit, {})

    def seed(self, values: dict[int, int], unit: int = 1) -> None:
        """Set raw data directly, address -> 16-bit word (already 0-based address)."""
        bank = self._bank(unit)
        for address, value in values.items():
            bank[address] = regs.to_unsigned16(value)

    def read_registers(self, address: int, count: int, unit: int) -> list[int]:
        bank = self._bank(unit)
        return [bank.get(address + i, 0) for i in range(count)]

    def write_register(self, address: int, value: int, unit: int) -> None:
        self._bank(unit)[address] = regs.to_unsigned16(value)

    def write_registers(self, address: int, values: list[int], unit: int) -> None:
        bank = self._bank(unit)
        for i, value in enumerate(values):
            bank[address + i] = regs.to_unsigned16(value)

    @classmethod
    def from_config_csv(cls, path: str | Path, unit: int = 1) -> "FakeTransport":
        """Seed an instance from a register dump in Simplex Motion Tool's format
        (``#modbus_register;register_name;data_type;value``, manual numbering).

        int32 fields are written as MSB/LSB pairs (manual_address, manual_address + 1).
        String fields are only handled for the fields whose length we know
        (ModelName, SerialNumber) -- other string rows are skipped.
        """
        transport = cls()
        bank: dict[int, int] = {}

        string_fields = {
            "ModelName": (regs.MODEL_NAME, regs.MODEL_NAME_LENGTH),
            "SerialNumber": (regs.SERIAL_NUMBER, regs.SERIAL_NUMBER_LENGTH),
        }

        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter=";")
            for row in reader:
                manual_address = int(row["#modbus_register"])
                name = row["register_name"]
                data_type = row["data_type"]
                raw_value = row["value"]
                zero_based = manual_address - 1

                if data_type == "str":
                    if name not in string_fields:
                        continue
                    base, length = string_fields[name]
                    for i, word in enumerate(_encode_string(raw_value, length)):
                        bank[base + i] = word
                elif data_type == "int32":
                    value = int(raw_value)
                    msb, lsb = regs.split_32(value)
                    bank[zero_based] = msb
                    bank[zero_based + 1] = lsb
                else:  # uns16 / int16
                    bank[zero_based] = regs.to_unsigned16(int(raw_value))

        transport.seed(bank, unit=unit)
        return transport


def _encode_string(text: str, num_registers: int) -> list[int]:
    """Pack an ASCII string into 16-bit words, 2 characters per register.
    Verified against real SE010A hardware: the first character of each pair
    sits in the low byte, the second in the high byte (i.e. the opposite of
    what you'd otherwise expect from Modbus strings)."""
    data = text.encode("ascii", errors="replace")
    data = data.ljust(num_registers * 2, b"\x00")
    return [
        data[i] | (data[i + 1] << 8)
        for i in range(0, num_registers * 2, 2)
    ]


def decode_string(words: list[int]) -> str:
    data = bytearray()
    for word in words:
        data.append(word & 0xFF)
        data.append((word >> 8) & 0xFF)
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace")
