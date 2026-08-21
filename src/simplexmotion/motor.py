"""API-lagret: det som faktiskt används av konsumentkod.

    motor = Motor(transport, address=1)
    motor.mode = Mode.SPEED_RAMP
    motor.speed_rpm = 200
    motor.pid.kp = 500
    print(motor.status.locked_shaft)
"""

from __future__ import annotations

from dataclasses import dataclass

from . import registers as regs
from .registers import Mode, Status
from .transport import Transport, decode_string


@dataclass
class Pid:
    """Vy över PID/reglerparametrarna (register 300-309)."""

    _motor: "Motor"

    @property
    def kp(self) -> int:
        return self._motor._read(regs.REG_KP)

    @kp.setter
    def kp(self, value: int) -> None:
        self._motor._write(regs.REG_KP, value)

    @property
    def ki(self) -> int:
        return self._motor._read(regs.REG_KI)

    @ki.setter
    def ki(self, value: int) -> None:
        self._motor._write(regs.REG_KI, value)

    @property
    def kd(self) -> int:
        return self._motor._read(regs.REG_KD)

    @kd.setter
    def kd(self, value: int) -> None:
        self._motor._write(regs.REG_KD, value)

    @property
    def limit(self) -> int:
        return self._motor._read(regs.REG_LIMIT)

    @limit.setter
    def limit(self, value: int) -> None:
        self._motor._write(regs.REG_LIMIT, value)

    @property
    def delay(self) -> int:
        return self._motor._read(regs.REG_DELAY)

    @delay.setter
    def delay(self, value: int) -> None:
        self._motor._write(regs.REG_DELAY, value)

    @property
    def friction(self) -> int:
        return self._motor._read(regs.REG_FRICTION)

    @friction.setter
    def friction(self, value: int) -> None:
        self._motor._write(regs.REG_FRICTION, value)

    @property
    def inertia(self) -> int:
        return self._motor._read(regs.REG_INERTIA)

    @inertia.setter
    def inertia(self, value: int) -> None:
        self._motor._write(regs.REG_INERTIA, value)

    @property
    def deadband(self) -> int:
        return self._motor._read(regs.REG_DEADBAND)

    @deadband.setter
    def deadband(self, value: int) -> None:
        self._motor._write(regs.REG_DEADBAND, value)

    @property
    def error_max(self) -> int:
        return self._motor._read(regs.REG_ERROR_MAX)

    @error_max.setter
    def error_max(self, value: int) -> None:
        self._motor._write(regs.REG_ERROR_MAX, value)


class Motor:
    """En SimplexMotion-servo på en given Modbus-adress.

    Transporten äger porten (och, för :class:`~simplexmotion.transport.PymodbusTransport`,
    serialiseringen mellan flera motorer). ``Motor`` äger bara adressen.
    """

    def __init__(self, transport: Transport, address: int) -> None:
        self.transport = transport
        self.address = address
        self.pid = Pid(self)

    def _read(self, register: int, signed: bool = True) -> int:
        raw = self.transport.read_registers(register, 1, self.address)[0]
        return regs.to_signed16(raw) if signed else raw

    def _write(self, register: int, value: int) -> None:
        self.transport.write_register(register, value, self.address)

    def _read_long(self, msb_register: int) -> int:
        words = self.transport.read_registers(msb_register, 2, self.address)
        return regs.combine_32(words[0], words[1])

    def _write_long(self, msb_register: int, value: int) -> None:
        msb, lsb = regs.split_32(value)
        self.transport.write_registers(msb_register, [msb, lsb], self.address)

    def _read_string(self, base_register: int, length: int) -> str:
        words = self.transport.read_registers(base_register, length, self.address)
        return decode_string(words)

    # -- Identitet --------------------------------------------------------

    @property
    def model_name(self) -> str:
        return self._read_string(regs.MODEL_NAME, regs.MODEL_NAME_LENGTH)

    @property
    def serial_number(self) -> str:
        return self._read_string(regs.SERIAL_NUMBER, regs.SERIAL_NUMBER_LENGTH)

    @property
    def ver_firmware(self) -> int:
        return self._read(regs.VER_FIRMWARE, signed=False)

    @property
    def ver_hardware(self) -> int:
        return self._read(regs.VER_HARDWARE, signed=False)

    # -- Styrning -----------------------------------------------------------

    @property
    def mode(self) -> Mode:
        return Mode(self._read(regs.MODE, signed=False))

    @mode.setter
    def mode(self, value: Mode) -> None:
        self._write(regs.MODE, int(value))

    @property
    def speed_rpm(self) -> float:
        return regs.raw_to_rpm(self._read_long(regs.TARGET_INPUT_MSB))

    @speed_rpm.setter
    def speed_rpm(self, rpm: float) -> None:
        self._write_long(regs.TARGET_INPUT_MSB, regs.rpm_to_raw(rpm))

    @property
    def ramp_speed_max_rpm(self) -> float:
        return regs.raw_to_rpm(self._read(regs.RAMP_SPEED_MAX))

    @ramp_speed_max_rpm.setter
    def ramp_speed_max_rpm(self, rpm: float) -> None:
        self._write(regs.RAMP_SPEED_MAX, regs.rpm_to_raw(rpm))

    @property
    def ramp_acc_max(self) -> float:
        return regs.raw_to_rpm_per_s(self._read(regs.RAMP_ACC_MAX, signed=False))

    @ramp_acc_max.setter
    def ramp_acc_max(self, rpm_per_s: float) -> None:
        self._write(regs.RAMP_ACC_MAX, regs.rpm_per_s_to_raw(rpm_per_s))

    @property
    def ramp_dec_max(self) -> float:
        return regs.raw_to_rpm_per_s(self._read(regs.RAMP_DEC_MAX, signed=False))

    @ramp_dec_max.setter
    def ramp_dec_max(self, rpm_per_s: float) -> None:
        self._write(regs.RAMP_DEC_MAX, regs.rpm_per_s_to_raw(rpm_per_s))

    @property
    def speed_filter(self) -> int:
        return self._read(regs.SPEED_FILTER, signed=False)

    @speed_filter.setter
    def speed_filter(self, value: int) -> None:
        self._write(regs.SPEED_FILTER, value)

    @property
    def target_filter(self) -> int:
        return self._read(regs.TARGET_FILTER, signed=False)

    @target_filter.setter
    def target_filter(self, value: int) -> None:
        self._write(regs.TARGET_FILTER, value)

    @property
    def torque_max(self) -> int:
        return self._read(regs.MOTOR_TORQUE_MAX)

    @torque_max.setter
    def torque_max(self, mnm: int) -> None:
        self._write(regs.MOTOR_TORQUE_MAX, mnm)

    @property
    def torque_stop(self) -> int:
        return self._read(regs.MOTOR_TORQUE_STOP)

    @torque_stop.setter
    def torque_stop(self, mnm: int) -> None:
        self._write(regs.MOTOR_TORQUE_STOP, mnm)

    # -- Mätvärden (skrivskyddade) -------------------------------------------

    @property
    def supply_voltage(self) -> float:
        return self._read(regs.SUPPLY, signed=False) * 0.01

    @property
    def temp_electronics(self) -> float:
        return self._read(regs.TEMP_ELECTRONICS) * 0.01

    @property
    def temp_motor(self) -> float:
        return self._read(regs.TEMP_MOTOR) * 0.01

    @property
    def motor_speed_rpm(self) -> float:
        return regs.raw_to_rpm(self._read(regs.MOTOR_SPEED))

    @property
    def motor_torque(self) -> int:
        return self._read(regs.MOTOR_TORQUE)

    @property
    def reg_error(self) -> int:
        return self._read(regs.REG_ERROR)

    @property
    def reg_output(self) -> int:
        return self._read(regs.REG_OUTPUT)

    @property
    def ramp_speed_rpm(self) -> float:
        return regs.raw_to_rpm(self._read(regs.RAMP_SPEED))

    # -- Status ---------------------------------------------------------------

    @property
    def status(self) -> Status:
        return Status(self._read(regs.STATUS, signed=False))

    @property
    def status_latched(self) -> Status:
        return Status(self._read(regs.STATUS_LATCHED, signed=False))

    # -- Icke-flyktigt minne ---------------------------------------------------

    def store(self) -> None:
        """Spara nuvarande registervärden till icke-flyktigt minne (Mode = 9)."""
        self._write(regs.MODE, int(Mode.STORE))

    def reload(self) -> None:
        """Kasta osparade ändringar, läs tillbaka sparade värden (Mode = 8)."""
        self._write(regs.MODE, int(Mode.RELOAD))

    def factory_reset(self) -> None:
        """Återställ allt inklusive adress och kommunikationsinställningar (Mode = 7)."""
        self._write(regs.MODE, int(Mode.FACTORY))
