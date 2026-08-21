"""Transportlager: allt som pratar Modbus RTU in/ut, ingen tolkning av vad
registren betyder. Se :class:`Transport` för det protokoll konsumenter kan
implementera för egen hårdvara.
"""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Protocol

from . import registers as regs


class Transport(Protocol):
    """Minimalt protokoll en Modbus-transport måste uppfylla.

    ``unit`` (slavadressen) hör till anropet, inte till transportobjektet,
    eftersom flera motorer kan dela samma buss.
    """

    def read_registers(self, address: int, count: int, unit: int) -> list[int]: ...

    def write_register(self, address: int, value: int, unit: int) -> None: ...

    def write_registers(self, address: int, values: list[int], unit: int) -> None: ...


class PymodbusTransport:
    """Standardtransport, baserad på ``pymodbus`` (FC03 / FC06 / FC16).

    Äger den seriella porten. En instans delas mellan alla :class:`~simplexmotion.motor.Motor`
    på samma buss -- ett internt lås serialiserar åtkomsten, eftersom Modbus RTU
    är half duplex och inte tål överlappande transaktioner.
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
            raise ConnectionError(f"Kunde inte öppna {port}")

    def close(self) -> None:
        self._client.close()

    def open(self) -> None:
        """Återöppna porten efter ett :meth:`close`."""
        if not self._client.connect():
            raise ConnectionError("Kunde inte återöppna porten")

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
    """Spelar upp/håller register i minnet -- ingen ansluten motor krävs.

    Användbar för utveckling och test. Flera ``unit``-adresser kan seedas
    oberoende av varandra i samma instans.
    """

    def __init__(self) -> None:
        self._registers: dict[int, dict[int, int]] = {}

    def _bank(self, unit: int) -> dict[int, int]:
        return self._registers.setdefault(unit, {})

    def seed(self, values: dict[int, int], unit: int = 1) -> None:
        """Sätt rådata direkt, adress -> 16-bitars ord (redan 0-baserad adress)."""
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
        """Seeda en instans från en registerdump i Simplex Motion Tools format
        (``#modbus_register;register_name;data_type;value``, manual-numrering).

        int32-fält skrivs som MSB/LSB-par (manual_adress, manual_adress + 1).
        Strängfält hanteras bara för de fält vi känner längden på
        (ModelName, SerialNumber) -- övriga sträng-rader hoppas över.
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
    """Packa en ASCII-sträng till 16-bitars ord, 2 tecken per register.
    Verifierat mot riktig SE010A-hårdvara: första tecknet i paret ligger i
    lågbyte, andra i högbyte (dvs. omvänt mot vad man annars förväntar sig
    av Modbus-strängar)."""
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
