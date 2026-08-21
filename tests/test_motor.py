import csv
import statistics
from pathlib import Path

import pytest

from simplexmotion import Mode, Motor
from simplexmotion.transport import FakeTransport

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def motor():
    transport = FakeTransport.from_config_csv(DATA_DIR / "config.csv")
    return Motor(transport, address=1)


def test_identity(motor):
    assert motor.model_name == "SimplexMotionSE010A"
    assert motor.serial_number == "SE010A-2211005047"
    assert motor.ver_firmware == 312


def test_mode_round_trip(motor):
    assert motor.mode == Mode.SPEED_RAMP  # seeded value from config.csv is 33
    motor.mode = Mode.OFF
    assert motor.mode == Mode.OFF


def test_speed_rpm_round_trip(motor):
    motor.speed_rpm = 200
    assert motor.speed_rpm == pytest.approx(200, abs=0.2)


def test_pid_round_trip(motor):
    assert motor.pid.kp == 500
    motor.pid.kp = 750
    assert motor.pid.kp == 750


def test_measurements_from_seeded_config(motor):
    assert motor.supply_voltage == pytest.approx(11.83, abs=0.01)
    assert motor.motor_torque == 11
    assert motor.reg_error == -3


def test_status_decoding(motor):
    status = motor.status  # seeded as 256 -> Moving
    assert status.moving is True
    assert status.fail is False


def test_store_and_reload_write_mode_register(motor):
    motor.store()
    assert motor.mode == Mode.STORE
    motor.reload()
    assert motor.mode == Mode.RELOAD


def test_scaling_matches_recorded_100rpm_reference_data():
    """Reads one of the recorder's test files and compares it against known reference
    values. Only validates that the data format and scaling (the same factor
    Motor.motor_speed_rpm uses) produce sane values -- no recorder register logic
    involved."""
    from simplexmotion.registers import raw_to_rpm

    path = DATA_DIR / "100rpm.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)  # header
        speeds = [int(row[1].strip()) for row in reader]

    rpms = [raw_to_rpm(raw) for raw in speeds]
    assert statistics.mean(rpms) == pytest.approx(100.9, abs=1.0)
    assert statistics.stdev(rpms) == pytest.approx(9.85, abs=1.0)
