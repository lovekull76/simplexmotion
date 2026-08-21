"""Recorder capture, FFT analysis, statistics, and CSV export.

FFT peak-finding and the 6x-rotation-frequency marker are the core
diagnostic this tool exists for: rotation-locked disturbances scale with
rpm, mechanical resonances don't (see the handover doc's background
section on the agitator troubleshooting that motivated this feature).
"""

from __future__ import annotations

import cmath
import csv
import io
import statistics

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from simplexmotion import RecorderState
from simplexmotion import registers as regs

from ..state import state

router = APIRouter(prefix="/api/recorder", tags=["recorder"])

# Manual register numbers of the channels worth recording -- the recorder
# can only capture 16-bit registers (see manual section 4.8).
RECORDABLE_CHANNELS = {
    100: "Supply",
    101: "TempElectronics",
    102: "TempMotor",
    202: "MotorSpeed",
    203: "MotorTorque",
    308: "RegError",
    310: "RegOutput",
    350: "RampSpeed",
    410: "Status",
}

_MOTOR_SPEED_CHANNEL = 202


class StartRequest(BaseModel):
    channels: list[int]
    period: int = 3
    preceding: int = 0
    mode: str = "SINGLE"
    trigger_mask: int = 0


@router.get("/channels")
def list_channels():
    return [{"register": reg, "name": name} for reg, name in RECORDABLE_CHANNELS.items()]


@router.post("/start")
def start(request: StartRequest):
    recorder = state.require_recorder()
    if not 1 <= len(request.channels) <= 4:
        raise HTTPException(status_code=400, detail="channels must contain 1 to 4 register numbers")
    recorder.configure(channels=request.channels, period=request.period, preceding=request.preceding)
    recorder.start(mode=RecorderState[request.mode], trigger_mask=request.trigger_mask)
    state.last_recording = None
    state.last_recording_channel_names = [
        RECORDABLE_CHANNELS.get(ch, f"reg{ch}") for ch in request.channels
    ]
    return {"started": True}


@router.get("/status")
def status():
    return {"idle": state.require_recorder().is_idle()}


def _ensure_read() -> None:
    recorder = state.require_recorder()
    if not recorder.is_idle():
        raise HTTPException(status_code=409, detail="Recording still in progress")
    if state.last_recording is None:
        state.last_recording = recorder.read()


@router.get("/data")
def data():
    _ensure_read()
    rec = state.last_recording
    return {
        "channels": rec.channels,
        "channel_names": state.last_recording_channel_names,
        "sample_interval_s": rec.sample_interval_s,
        "time": rec.time_axis(),
        "samples": rec.samples,
    }


@router.get("/stats")
def stats():
    _ensure_read()
    rec = state.last_recording
    result = []
    for name, samples in zip(state.last_recording_channel_names, rec.samples):
        mean = statistics.mean(samples)
        lo, hi = min(samples), max(samples)
        result.append(
            {
                "channel": name,
                "mean": mean,
                "min": lo,
                "max": hi,
                "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
                "ripple_percent": ((hi - lo) / (2 * mean) * 100) if mean else 0.0,
            }
        )
    return result


def _fft(x: list[complex]) -> list[complex]:
    """Radix-2 Cooley-Tukey. ``x`` must have a power-of-two length."""
    n = len(x)
    if n <= 1:
        return x
    even = _fft(x[0::2])
    odd = _fft(x[1::2])
    twiddled = [cmath.exp(-2j * cmath.pi * k / n) * odd[k] for k in range(n // 2)]
    return [even[k] + twiddled[k] for k in range(n // 2)] + [even[k] - twiddled[k] for k in range(n // 2)]


def _real_fft(samples: list[int], sample_interval_s: float) -> tuple[list[float], list[float]]:
    """FFT of a real-valued signal, zero-padded to the next power of two (no
    numpy on this deployment target -- 500-ish samples is trivial for a pure
    Python radix-2 FFT). Returns (frequencies_hz, magnitudes), DC through Nyquist.
    """
    n = len(samples)
    n_padded = 1
    while n_padded < n:
        n_padded *= 2

    mean = sum(samples) / n
    padded = [complex(v - mean, 0.0) for v in samples] + [0j] * (n_padded - n)
    spectrum = _fft(padded)

    half = n_padded // 2 + 1
    freqs = [k / (n_padded * sample_interval_s) for k in range(half)]
    magnitudes = [abs(spectrum[k]) * 2.0 / n for k in range(half)]
    magnitudes[0] = abs(spectrum[0]) / n  # DC bin isn't doubled
    return freqs, magnitudes


def _rotation_frequency_hz() -> float:
    rec = state.last_recording
    if rec is not None and _MOTOR_SPEED_CHANNEL in rec.channels:
        idx = rec.channels.index(_MOTOR_SPEED_CHANNEL)
        mean_raw = statistics.mean(rec.samples[idx])
        rpm = regs.raw_to_rpm(mean_raw)
    else:
        rpm = state.require_motor().motor_speed_rpm
    return abs(rpm) / 60.0


@router.get("/fft")
def fft(channel: int = 0, top_n: int = 3):
    _ensure_read()
    rec = state.last_recording
    if not 0 <= channel < len(rec.samples):
        raise HTTPException(status_code=400, detail="channel index out of range")

    freqs, magnitude = _real_fft(rec.samples[channel], rec.sample_interval_s)

    # skip DC (index 0) when ranking peaks
    ranked = sorted(range(1, len(magnitude)), key=lambda i: magnitude[i], reverse=True)
    top_peaks = [{"frequency_hz": freqs[i], "magnitude": magnitude[i]} for i in ranked[:top_n]]

    rotation_hz = _rotation_frequency_hz()

    return {
        "channel": state.last_recording_channel_names[channel],
        "frequencies_hz": freqs,
        "magnitudes": magnitude,
        "rotation_frequency_hz": rotation_hz,
        "six_x_frequency_hz": rotation_hz * 6,
        "top_peaks": top_peaks,
    }


@router.get("/csv")
def csv_export():
    _ensure_read()
    rec = state.last_recording
    names = state.last_recording_channel_names

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Time (s)"] + names)

    def fmt(value: float) -> str:
        return f"{value:g}".replace(".", ",")

    for i, t in enumerate(rec.time_axis()):
        row = [fmt(t)] + [fmt(rec.samples[ch][i]) for ch in range(len(names))]
        writer.writerow(row)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=recording.csv"},
    )
