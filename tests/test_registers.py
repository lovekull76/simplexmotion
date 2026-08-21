import pytest

from simplexmotion import registers as regs


REFERENCE_TARGETS = [
    (50, 213),
    (100, 427),
    (200, 853),
    (300, 1280),
    (400, 1707),
    (500, 2133),
]


def test_rpm_to_raw_matches_reference_table():
    for rpm, expected in REFERENCE_TARGETS:
        assert regs.rpm_to_raw(rpm) == expected


def test_raw_to_rpm_round_trip():
    for rpm, raw in REFERENCE_TARGETS:
        assert regs.raw_to_rpm(raw) == pytest.approx(rpm, abs=0.6)


def test_combine_and_split_32_round_trip():
    for value in (0, 1, -1, 213, -213, 2147483647, -2147483647):
        msb, lsb = regs.split_32(value)
        assert regs.combine_32(msb, lsb) == value


def test_signed16_round_trip():
    for value in (0, 1, -1, 32767, -32768, 11, -3):
        assert regs.to_signed16(regs.to_unsigned16(value)) == value


def test_status_bit_decoding():
    status = regs.Status(256)  # bit 8 = Moving
    assert status.moving is True
    assert status.fail is False
    assert status.locked_shaft is False

    status = regs.Status(770)  # 512 + 256 + 2 -> bits 1, 8, 9
    assert status.communication is True
    assert status.moving is True
    assert status.reverse is True
    assert status.fail is False
