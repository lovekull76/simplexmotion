"""The recorder subsystem: a 4-channel, 500-sample-per-channel circular
buffer built into the SE010A, used to capture fast time-series data for
diagnostics (see manual section 4.8).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import IntEnum

from . import registers as regs
from .motor import Motor

_DATA_BANKS = (regs.REC_DATA1, regs.REC_DATA2, regs.REC_DATA3, regs.REC_DATA4)
_MAX_REGISTERS_PER_READ = 125  # FC03 cap


class RecorderState(IntEnum):
    IDLE = 0
    CONTINUOUS = 1
    SINGLE = 2
    TRIGGER = 3


@dataclass
class RecorderData:
    """One completed recording, already de-circularized (index 0 is the
    oldest/first sample)."""

    channels: list[int]  # manual register numbers recorded on each of the 4 banks
    sample_interval_s: float
    samples: list[list[int]]  # samples[channel_index][sample_index], signed 16-bit

    def time_axis(self) -> list[float]:
        return [i * self.sample_interval_s for i in range(len(self.samples[0]))]


class Recorder:
    """Drives the recorder registers on a single :class:`~simplexmotion.motor.Motor`."""

    def __init__(self, motor: Motor) -> None:
        self.motor = motor
        self._channels: list[int] = []
        self._sample_interval_s: float = regs.rec_period_to_interval_s(0)

    def configure(self, channels: list[int], period: int = 0, preceding: int = 0) -> None:
        """Select up to 4 source registers (manual numbers) to record, the sample
        period (see :func:`~simplexmotion.registers.rec_period_to_interval_s`), and
        how many samples of a triggered recording should precede the trigger."""
        if not 1 <= len(channels) <= 4:
            raise ValueError("channels must contain 1 to 4 register numbers")
        padded = list(channels) + [0] * (4 - len(channels))
        self.motor.transport.write_registers(regs.REC_REGISTER, padded, self.motor.address)
        self.motor.transport.write_register(regs.REC_PERIOD, period, self.motor.address)
        self.motor.transport.write_register(regs.REC_PRECEDING, preceding, self.motor.address)
        self._channels = list(channels)
        self._sample_interval_s = regs.rec_period_to_interval_s(period)

    def start(self, mode: RecorderState = RecorderState.SINGLE, trigger_mask: int = 0) -> None:
        """Arm/start a recording. ``trigger_mask`` is only used for
        :attr:`RecorderState.TRIGGER` -- a status-bit mask (see
        :class:`~simplexmotion.registers.Status`)."""
        self.motor.transport.write_register(regs.REC_TRIGGER, trigger_mask, self.motor.address)
        self.motor.transport.write_register(regs.REC_STATE, int(mode), self.motor.address)

    def is_idle(self) -> bool:
        raw = self.motor.transport.read_registers(regs.REC_STATE, 1, self.motor.address)[0]
        return RecorderState(raw) == RecorderState.IDLE

    def wait_until_idle(self, timeout: float = 10.0, poll_interval: float = 0.1) -> None:
        deadline = time.monotonic() + timeout
        while not self.is_idle():
            if time.monotonic() > deadline:
                raise TimeoutError("Recorder did not finish within the timeout")
            time.sleep(poll_interval)

    def read(self) -> RecorderData:
        """Read back a completed recording, de-circularizing each channel so
        that index 0 is the oldest sample (see the manual's ``RecOffset`` note
        and the "recorder circularity" pitfall in the handover doc)."""
        offset = self.motor.transport.read_registers(regs.REC_OFFSET, 1, self.motor.address)[0]

        samples: list[list[int]] = []
        for bank_base in _DATA_BANKS[: len(self._channels)]:
            words: list[int] = []
            remaining = regs.REC_DATA_LENGTH
            address = bank_base
            while remaining > 0:
                chunk = min(remaining, _MAX_REGISTERS_PER_READ)
                words.extend(
                    self.motor.transport.read_registers(address, chunk, self.motor.address)
                )
                address += chunk
                remaining -= chunk
            rotated = words[offset:] + words[:offset]
            samples.append([regs.to_signed16(w) for w in rotated])

        return RecorderData(
            channels=list(self._channels),
            sample_interval_s=self._sample_interval_s,
            samples=samples,
        )
