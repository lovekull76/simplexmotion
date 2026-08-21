"""Registeradresser och skalningar för SimplexMotion SE010A.

Alla adresser nedan är redan -1-justerade relativt manualens numrering
(manualen räknar 1-baserat, Modbus-protokollet 0-baserat). Använd dessa
konstanter direkt mot en :class:`~simplexmotion.transport.Transport` --
ingen kod utanför den här modulen ska behöva tänka på offsetten.
"""

from __future__ import annotations

from enum import IntEnum

# ---------------------------------------------------------------------------
# Identitet
# ---------------------------------------------------------------------------

VER_PARAMETERS = 0
VER_FIRMWARE = 1
VER_HARDWARE = 2
MODEL_NAME = 9          # 10 register, 20-teckens sträng
MODEL_NAME_LENGTH = 10
SERIAL_NUMBER = 19      # 10 register, 20-teckens sträng
SERIAL_NUMBER_LENGTH = 10
ADDRESS = 49

# ---------------------------------------------------------------------------
# Mätvärden
# ---------------------------------------------------------------------------

SUPPLY = 99                # 0,01 V
TEMP_ELECTRONICS = 100     # 0,01 degC
TEMP_MOTOR = 101           # 0,01 degC
MOTOR_POSITION_MSB = 199   # int32, 4096 per varv
MOTOR_SPEED = 201          # rpm = raw * SPEED_SCALE
MOTOR_TORQUE = 202         # mNm, int16
REG_ERROR = 307            # int16, +-8192
REG_OUTPUT = 309           # int16
RAMP_SPEED = 349           # samma skalning som MOTOR_SPEED

# ---------------------------------------------------------------------------
# Parametrar
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
RAMP_SPEED_MAX = 350       # samma skalning som TARGET_INPUT
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
# Status och skydd
# ---------------------------------------------------------------------------

STATUS_FILTER = 408
STATUS = 409
STATUS_LATCHED = 410
MASK_QUICKSTOP = 412
MASK_SHUTDOWN = 413
ERROR = 414

# ---------------------------------------------------------------------------
# Recorder (huvuden -- själva dataarrayerna 1000-4499 hanteras inte av
# kärn-API:t, det är en fråga för tuning-verktyget)
# ---------------------------------------------------------------------------

REC_STATE = 899
REC_TRIGGER = 900
REC_PERIOD = 901
REC_PRECEDING = 902
REC_OFFSET = 903
REC_REGISTER = 904  # 4 register, REC_REGISTER..REC_REGISTER+3

# ---------------------------------------------------------------------------
# 32-bitars registerpar som kräver MSB/LSB-hantering (adresser enligt manualen,
# se docstring i toppen -- listan används av transport-lagret för att veta
# vilka fält som är dubbelregister).
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
    """Värden för MODE-registret (399 / manual 400)."""

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
    """Avkodad vy över ett Status/StatusLatched-registervärde."""

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
# Skalningar
# ---------------------------------------------------------------------------

# rpm = MotorSpeed-raw * SPEED_SCALE  (samma faktor gäller RampSpeed)
# raw  = rpm / SPEED_SCALE            (samma faktor gäller TargetInput/RampSpeedMax)
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
    """Slå ihop två 16-bitars ord (MSB på jämn adress) till ett signat 32-bitarsvärde."""
    raw = ((msb & 0xFFFF) << 16) | (lsb & 0xFFFF)
    return raw - 0x100000000 if raw & 0x80000000 else raw


def split_32(value: int) -> tuple[int, int]:
    """Motsatsen till :func:`combine_32`. Returnerar (msb, lsb) som osignerade 16-bitarsord."""
    raw = value & 0xFFFFFFFF
    return (raw >> 16) & 0xFFFF, raw & 0xFFFF
