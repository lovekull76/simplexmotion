import csv
import statistics
from pathlib import Path

import pytest

from simplexmotion import Motor, Recorder, RecorderState
from simplexmotion import registers as regs
from simplexmotion.transport import FakeTransport

DATA_DIR = Path(__file__).parent / "data"


def _load_motor_speed_column(path: Path) -> list[int]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)  # header
        return [int(row[1].strip()) for row in reader]


def _seed_circular_buffer(transport: FakeTransport, bank_base: int, flat: list[int], offset: int, unit: int = 1):
    """Place ``flat`` (in playback order) into a circular buffer starting at
    ``bank_base`` such that reading from ``offset`` and rotating reproduces it."""
    raw_bank = [0] * len(flat)
    for i, value in enumerate(flat):
        raw_bank[(offset + i) % len(flat)] = value
    transport.write_registers(bank_base, raw_bank, unit)


@pytest.fixture
def motor():
    transport = FakeTransport.from_config_csv(DATA_DIR / "config.csv")
    return Motor(transport, address=1)


def test_configure_writes_channels_period_and_preceding(motor):
    recorder = Recorder(motor)
    recorder.configure(channels=[regs.MOTOR_SPEED + 1, 0, 0, 0], period=3, preceding=100)

    written = motor.transport.read_registers(regs.REC_REGISTER, 4, motor.address)
    assert written[0] == regs.MOTOR_SPEED + 1
    assert motor.transport.read_registers(regs.REC_PERIOD, 1, motor.address)[0] == 3
    assert motor.transport.read_registers(regs.REC_PRECEDING, 1, motor.address)[0] == 100


def test_start_writes_trigger_and_state(motor):
    recorder = Recorder(motor)
    recorder.start(mode=RecorderState.SINGLE, trigger_mask=256)

    assert motor.transport.read_registers(regs.REC_TRIGGER, 1, motor.address)[0] == 256
    assert motor.transport.read_registers(regs.REC_STATE, 1, motor.address)[0] == RecorderState.SINGLE


def test_is_idle_reflects_rec_state(motor):
    recorder = Recorder(motor)
    motor.transport.write_register(regs.REC_STATE, RecorderState.SINGLE, motor.address)
    assert recorder.is_idle() is False
    motor.transport.write_register(regs.REC_STATE, RecorderState.IDLE, motor.address)
    assert recorder.is_idle() is True


def test_read_reconstructs_circular_buffer_with_offset(motor):
    flat = _load_motor_speed_column(DATA_DIR / "100rpm.csv")
    assert len(flat) == 500

    offset = 137
    _seed_circular_buffer(motor.transport, regs.REC_DATA1, flat, offset, unit=motor.address)
    motor.transport.write_register(regs.REC_OFFSET, offset, motor.address)

    recorder = Recorder(motor)
    recorder.configure(channels=[regs.MOTOR_SPEED + 1], period=3)
    data = recorder.read()

    assert data.samples[0] == flat
    assert data.sample_interval_s == pytest.approx(0.002)


def test_read_multi_channel_reconstructs_all_banks(motor):
    flat_speed = _load_motor_speed_column(DATA_DIR / "50rpm.csv")
    with open(DATA_DIR / "50rpm.csv", newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)
        flat_torque = [int(row[2].strip()) for row in reader]

    offset = 42
    _seed_circular_buffer(motor.transport, regs.REC_DATA1, flat_speed, offset, unit=motor.address)
    _seed_circular_buffer(motor.transport, regs.REC_DATA2, flat_torque, offset, unit=motor.address)
    motor.transport.write_register(regs.REC_OFFSET, offset, motor.address)

    recorder = Recorder(motor)
    recorder.configure(channels=[regs.MOTOR_SPEED + 1, regs.MOTOR_TORQUE + 1], period=3)
    data = recorder.read()

    assert data.samples[0] == flat_speed
    assert data.samples[1] == flat_torque


def test_time_axis_matches_sample_interval(motor):
    flat = _load_motor_speed_column(DATA_DIR / "100rpm.csv")
    _seed_circular_buffer(motor.transport, regs.REC_DATA1, flat, 0, unit=motor.address)
    motor.transport.write_register(regs.REC_OFFSET, 0, motor.address)

    recorder = Recorder(motor)
    recorder.configure(channels=[regs.MOTOR_SPEED + 1], period=3)
    data = recorder.read()

    axis = data.time_axis()
    assert axis[0] == 0
    assert axis[1] == pytest.approx(0.002)
    assert axis[-1] == pytest.approx(499 * 0.002)


def test_reconstructed_data_matches_known_reference_stats():
    """Cross-check against the same reference values used in test_motor.py's
    scaling test -- confirms the recorder round-trip doesn't corrupt values."""
    transport = FakeTransport.from_config_csv(DATA_DIR / "config.csv")
    motor = Motor(transport, address=1)
    flat = _load_motor_speed_column(DATA_DIR / "100rpm.csv")

    _seed_circular_buffer(transport, regs.REC_DATA1, flat, 250, unit=1)
    transport.write_register(regs.REC_OFFSET, 250, 1)

    recorder = Recorder(motor)
    recorder.configure(channels=[regs.MOTOR_SPEED + 1], period=3)
    data = recorder.read()

    rpms = [regs.raw_to_rpm(raw) for raw in data.samples[0]]
    assert statistics.mean(rpms) == pytest.approx(100.9, abs=1.0)
    assert statistics.stdev(rpms) == pytest.approx(9.85, abs=1.0)
