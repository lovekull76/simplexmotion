"""The adjustable-parameter table from the handover doc, backed 1:1 by
Motor properties already in the library. No range enforcement beyond what's
shown to the user -- the manual's stated ranges are display hints only.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from simplexmotion import Mode
from simplexmotion import registers as regs

from ..state import state

router = APIRouter(prefix="/api", tags=["params"])

# name -> (getter, setter, unit, min, max, note)
_SIMPLE_PARAMS = {
    "pid_kp": (lambda m: m.pid.kp, lambda m, v: setattr(m.pid, "kp", v), "", 0, 10000, ""),
    "pid_ki": (lambda m: m.pid.ki, lambda m, v: setattr(m.pid, "ki", v), "", 0, 10000, ""),
    "pid_kd": (lambda m: m.pid.kd, lambda m, v: setattr(m.pid, "kd", v), "", 0, 10000, ""),
    "pid_limit": (lambda m: m.pid.limit, lambda m, v: setattr(m.pid, "limit", v), "", 0, 65535, ""),
    "pid_delay": (
        lambda m: m.pid.delay,
        lambda m, v: setattr(m.pid, "delay", v),
        "",
        0,
        8,
        "Derivative filtering",
    ),
    "pid_friction": (
        lambda m: m.pid.friction,
        lambda m, v: setattr(m.pid, "friction", v),
        "",
        0,
        200,
        "Speed feed-forward",
    ),
    "pid_inertia": (
        lambda m: m.pid.inertia,
        lambda m, v: setattr(m.pid, "inertia", v),
        "",
        0,
        1000,
        "Acceleration feed-forward",
    ),
    "pid_deadband": (
        lambda m: m.pid.deadband,
        lambda m, v: setattr(m.pid, "deadband", v),
        "",
        0,
        100,
        "",
    ),
    "pid_error_max": (
        lambda m: m.pid.error_max,
        lambda m, v: setattr(m.pid, "error_max", v),
        "",
        0,
        65535,
        "Trip level for the Regulator status bit",
    ),
    "speed_filter": (
        lambda m: m.speed_filter,
        lambda m, v: setattr(m, "speed_filter", v),
        "",
        0,
        15,
        "",
    ),
    "torque_max": (
        lambda m: m.torque_max,
        lambda m, v: setattr(m, "torque_max", v),
        "mNm",
        0,
        2000,
        "",
    ),
    "torque_stop": (
        lambda m: m.torque_stop,
        lambda m, v: setattr(m, "torque_stop", v),
        "mNm",
        0,
        2000,
        "",
    ),
    "target_filter": (
        lambda m: m.target_filter,
        lambda m, v: setattr(m, "target_filter", v),
        "",
        0,
        16,
        "",
    ),
}

# name -> (rpm getter, rpm setter, raw-conversion helper)
_SPEED_PARAMS = {
    "speed_rpm": (
        lambda m: m.speed_rpm,
        lambda m, v: setattr(m, "speed_rpm", v),
        regs.rpm_to_raw,
        regs.raw_to_rpm,
    ),
    "ramp_speed_max_rpm": (
        lambda m: m.ramp_speed_max_rpm,
        lambda m, v: setattr(m, "ramp_speed_max_rpm", v),
        regs.rpm_to_raw,
        regs.raw_to_rpm,
    ),
    "ramp_acc_max": (
        lambda m: m.ramp_acc_max,
        lambda m, v: setattr(m, "ramp_acc_max", v),
        regs.rpm_per_s_to_raw,
        regs.raw_to_rpm_per_s,
    ),
    "ramp_dec_max": (
        lambda m: m.ramp_dec_max,
        lambda m, v: setattr(m, "ramp_dec_max", v),
        regs.rpm_per_s_to_raw,
        regs.raw_to_rpm_per_s,
    ),
}

_BITFIELD_PARAMS = {
    "status_filter": lambda m: m.status_filter,
    "mask_quickstop": lambda m: m.mask_quickstop,
    "mask_shutdown": lambda m: m.mask_shutdown,
}

_BITFIELD_SETTERS = {
    "status_filter": lambda m, v: setattr(m, "status_filter", v),
    "mask_quickstop": lambda m, v: setattr(m, "mask_quickstop", v),
    "mask_shutdown": lambda m, v: setattr(m, "mask_shutdown", v),
}


class ParamsUpdate(BaseModel):
    values: dict[str, float | str | int]


@router.get("/params")
def get_params():
    motor = state.require_motor()
    result: dict[str, dict] = {}

    for name, (getter, _setter, unit, lo, hi, note) in _SIMPLE_PARAMS.items():
        result[name] = {"value": getter(motor), "unit": unit, "min": lo, "max": hi, "note": note}

    for name, (getter, _setter, to_raw, _from_raw) in _SPEED_PARAMS.items():
        value = getter(motor)
        result[name] = {"value": value, "raw": to_raw(value), "unit": "rpm" if "acc" not in name and "dec" not in name else "rpm/s"}

    for name, getter in _BITFIELD_PARAMS.items():
        raw = getter(motor)
        status = regs.Status(raw)
        result[name] = {
            "value": raw,
            "bits": {bit: getattr(status, bit) for bit in regs.STATUS_BIT_NAMES},
        }

    mode = motor.mode
    result["mode"] = {"value": mode.name, "options": [m.name for m in Mode]}

    return result


def flat_values(motor) -> dict[str, float | str | int]:
    """All adjustable parameters as plain name -> value, suitable for saving
    as a profile or feeding back into :func:`apply_values`."""
    values: dict[str, float | str | int] = {}
    for name, (getter, _setter, *_rest) in _SIMPLE_PARAMS.items():
        values[name] = getter(motor)
    for name, (getter, _setter, *_rest) in _SPEED_PARAMS.items():
        values[name] = getter(motor)
    for name, getter in _BITFIELD_PARAMS.items():
        values[name] = getter(motor)
    values["mode"] = motor.mode.name
    return values


def apply_values(motor, values: dict) -> dict:
    applied = {}
    for name, value in values.items():
        if name in _SIMPLE_PARAMS:
            _, setter, *_ = _SIMPLE_PARAMS[name]
            setter(motor, int(value))
        elif name in _SPEED_PARAMS:
            _, setter, *_ = _SPEED_PARAMS[name]
            setter(motor, float(value))
        elif name in _BITFIELD_SETTERS:
            _BITFIELD_SETTERS[name](motor, int(value))
        elif name == "mode":
            motor.mode = Mode[str(value)]
        else:
            continue
        applied[name] = value
    return applied


@router.post("/params")
def set_params(update: ParamsUpdate):
    return {"applied": apply_values(state.require_motor(), update.values)}


@router.post("/store")
def store():
    state.require_motor().store()
    return {"ok": True}


@router.post("/reload")
def reload_settings():
    state.require_motor().reload()
    return {"ok": True}
