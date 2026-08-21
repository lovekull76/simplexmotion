"""Register addresses and scalings for the SimplexMotion SE010A.

All addresses below are already -1-adjusted relative to the manual's
numbering (the manual counts from 1, the Modbus protocol from 0). Use
these constants directly against a :class:`~simplexmotion.transport.Transport`
-- no code outside this module should need to think about the offset.
"""

from __future__ import annotations

from enum import IntEnum

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

VER_PARAMETERS = 0
VER_FIRMWARE = 1
VER_HARDWARE = 2
MODEL_NAME = 9          # 10 registers, 20-character string
MODEL_NAME_LENGTH = 10
SERIAL_NUMBER = 19      # 10 registers, 20-character string
SERIAL_NUMBER_LENGTH = 10
ADDRESS = 49

# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------

SUPPLY = 99                # 0.01 V
TEMP_ELECTRONICS = 100     # 0.01 degC
TEMP_MOTOR = 101           # 0.01 degC
MOTOR_POSITION_MSB = 199   # int32, 4096 per revolution
MOTOR_SPEED = 201          # rpm = raw * SPEED_SCALE
MOTOR_TORQUE = 202         # mNm, int16
REG_ERROR = 307            # int16, +-8192
REG_OUTPUT = 309           # int16
RAMP_SPEED = 349           # same scaling as MOTOR_SPEED

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

SPEED_FILTER = 120
MOTOR_TORQUE_MAX = 203     # mNm
MOTOR_TORQUE_STOP = 204    # mNm
REG_KP = 299
REG_KI = 300
REG_KD = 301
REG_LIMIT = 302
REG_DELAY = 303
REG_FRICTION = 304
REG_INERTIA = 305
REG_DEADBAND = 306
REG_ERROR_MAX = 308
RAMP_SPEED_MAX = 350       # same scaling as TARGET_INPUT
RAMP_ACC_MAX = 352         # rpm/s * ACC_SCALE
RAMP_DEC_MAX = 353         # rpm/s * ACC_SCALE
MODE = 399
TARGET_RELATIVE_MSB = 447  # int32
TARGET_INPUT_MSB = 449     # int32, rpm * TARGET_SCALE
TARGET_SELECT = 451
TARGET_MIN_MSB = 455       # int32
TARGET_MAX_MSB = 457       # int32
TARGET_FILTER = 460
TARGET_PRESENT_MSB = 461   # int32
ROTARY_START_MSB = 469     # int32
ROTARY_STOP_MSB = 471      # int32
TIME_MSB = 419             # int32

# ---------------------------------------------------------------------------
# Status and protection
# ---------------------------------------------------------------------------

STATUS_FILTER = 408
STATUS = 409
STATUS_LATCHED = 410
MASK_QUICKSTOP = 412
MASK_SHUTDOWN = 413
ERROR = 414

# ---------------------------------------------------------------------------
# Recorder (headers only -- the data arrays themselves, 1000-4499, aren't
# handled by the core API; that's a job for the tuning tool)
# ---------------------------------------------------------------------------

REC_STATE = 899
REC_TRIGGER = 900
REC_PERIOD = 901
REC_PRECEDING = 902
REC_OFFSET = 903
REC_REGISTER = 904  # 4 registers, REC_REGISTER..REC_REGISTER+3

# ---------------------------------------------------------------------------
# 32-bit register pairs that need MSB/LSB handling (addresses per the manual,
# see the docstring at the top -- used by the transport layer to know which
# fields are double registers).
# ---------------------------------------------------------------------------

LONG_REGISTER_PAIRS = frozenset(
    {
        MOTOR_POSITION_MSB,
        TARGET_RELATIVE_MSB,
        TARGET_INPUT_MSB,
        TARGET_MIN_MSB,
        TARGET_MAX_MSB,
        TARGET_PRESENT_MSB,
        ROTARY_START_MSB,
        ROTARY_STOP_MSB,
        TIME_MSB,
    }
)


class Mode(IntEnum):
    """Values for the MODE register (399 / manual 400)."""

    OFF = 0
    RESET = 1
    FACTORY = 7
    RELOAD = 8
    STORE = 9
    SPEED_RAMP = 33


_STATUS_BITS = {
    "fail": 0,
    "communication": 1,
    "current": 2,
    "voltage": 3,
    "temperature": 4,
    "torque_limit": 5,
    "locked_shaft": 6,
    "regulator": 7,
    "moving": 8,
    "reverse": 9,
    "target": 10,
    "input_a": 12,
    "input_b": 13,
    "user1": 14,
    "user2": 15,
}


class Status:
    """Decoded view over a Status/StatusLatched register value."""

    __slots__ = ("raw",)

    def __init__(self, raw: int) -> None:
        self.raw = raw

    def __getattr__(self, name: str) -> bool:
        try:
            bit = _STATUS_BITS[name]
        except KeyError:
            raise AttributeError(name) from None
        return bool(self.raw & (1 << bit))

    def __repr__(self) -> str:
        active = [name for name in _STATUS_BITS if getattr(self, name)]
        return f"Status(raw={self.raw}, {'|'.join(active) or 'none'})"


# ---------------------------------------------------------------------------
# Scalings
# ---------------------------------------------------------------------------

# rpm = MotorSpeed raw * SPEED_SCALE  (same factor applies to RampSpeed)
# raw  = rpm / SPEED_SCALE            (same factor applies to TargetInput/RampSpeedMax)
SPEED_SCALE = 0.234375  # = 16 * 60 / 4096

# raw (RampAccMax / RampDecMax) = rpm_per_s * ACC_SCALE
ACC_SCALE = 0.26666666666667  # = 4096 / 256 / 60


def raw_to_rpm(raw: int) -> float:
    return raw * SPEED_SCALE


def rpm_to_raw(rpm: float) -> int:
    return round(rpm / SPEED_SCALE)


def raw_to_rpm_per_s(raw: int) -> float:
    return raw / ACC_SCALE


def rpm_per_s_to_raw(rpm_per_s: float) -> int:
    return round(rpm_per_s * ACC_SCALE)


def to_signed16(raw: int) -> int:
    raw &= 0xFFFF
    return raw - 0x10000 if raw & 0x8000 else raw


def to_unsigned16(value: int) -> int:
    return value & 0xFFFF


def combine_32(msb: int, lsb: int) -> int:
    """Combine two 16-bit words (MSB at the even address) into a signed 32-bit value."""
    raw = ((msb & 0xFFFF) << 16) | (lsb & 0xFFFF)
    return raw - 0x100000000 if raw & 0x80000000 else raw


def split_32(value: int) -> tuple[int, int]:
    """The inverse of :func:`combine_32`. Returns (msb, lsb) as unsigned 16-bit words."""
    raw = value & 0xFFFFFFFF
    return (raw >> 16) & 0xFFFF, raw & 0xFFFF
