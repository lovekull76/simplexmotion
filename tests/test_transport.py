from pathlib import Path

from simplexmotion import registers as regs
from simplexmotion.transport import FakeTransport, decode_string

DATA_DIR = Path(__file__).parent / "data"


def test_fake_transport_read_write_round_trip():
    transport = FakeTransport()
    transport.write_register(10, 1234, unit=1)
    assert transport.read_registers(10, 1, unit=1) == [1234]


def test_fake_transport_write_registers_and_read_range():
    transport = FakeTransport()
    transport.write_registers(0, [1, 2, 3], unit=1)
    assert transport.read_registers(0, 3, unit=1) == [1, 2, 3]


def test_fake_transport_unread_registers_default_to_zero():
    transport = FakeTransport()
    assert transport.read_registers(0, 4, unit=1) == [0, 0, 0, 0]


def test_fake_transport_separates_units():
    transport = FakeTransport()
    transport.write_register(0, 111, unit=1)
    transport.write_register(0, 222, unit=2)
    assert transport.read_registers(0, 1, unit=1) == [111]
    assert transport.read_registers(0, 1, unit=2) == [222]


def test_32bit_split_combine_via_fake_transport():
    transport = FakeTransport()
    value = -12345
    msb, lsb = regs.split_32(value)
    transport.write_registers(regs.TARGET_INPUT_MSB, [msb, lsb], unit=1)
    words = transport.read_registers(regs.TARGET_INPUT_MSB, 2, unit=1)
    assert regs.combine_32(words[0], words[1]) == value


def test_from_config_csv_seeds_identity_and_measurements():
    transport = FakeTransport.from_config_csv(DATA_DIR / "config.csv")

    model_words = transport.read_registers(regs.MODEL_NAME, regs.MODEL_NAME_LENGTH, unit=1)
    assert decode_string(model_words) == "SimplexMotionSE010A"

    serial_words = transport.read_registers(regs.SERIAL_NUMBER, regs.SERIAL_NUMBER_LENGTH, unit=1)
    assert decode_string(serial_words) == "SE010A-2211005047"

    (supply,) = transport.read_registers(regs.SUPPLY, 1, unit=1)
    assert supply == 1183

    words = transport.read_registers(regs.TARGET_INPUT_MSB, 2, unit=1)
    assert regs.combine_32(words[0], words[1]) == 213
