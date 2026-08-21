# simplexmotion

Python library for SimplexMotion SE010A servo motors over Modbus RTU (RS485).

Three layers:

- **Transport** — the `Transport` protocol, plus `PymodbusTransport` (default, requires
  connected hardware) and `FakeTransport` (plays back/holds registers in memory, for
  development and testing without a motor).
- **Registers** (`simplexmotion.registers`) — addresses, scalings, Mode/Status.
- **Motor API** — `Motor`, the thing you actually use.

## Example

```python
from simplexmotion import Motor, PymodbusTransport, Mode

bus = PymodbusTransport(port="/dev/ttyUSB0", baudrate=57600, parity="E")

agitator = Motor(bus, address=1)
pump = Motor(bus, address=2)

agitator.mode = Mode.SPEED_RAMP
agitator.speed_rpm = 200
agitator.pid.kp = 500
print(agitator.status.locked_shaft)
```

Several motors can share the same bus — the transport owns the port and
serializes access, `Motor` only owns the address.

## Development without a connected motor

```python
from simplexmotion import Motor, FakeTransport

bus = FakeTransport.from_config_csv("tests/data/config.csv")
motor = Motor(bus, address=1)
print(motor.model_name, motor.motor_speed_rpm)
```

## Tests

```
pip install -e ".[dev]"
pytest
```

All tests run offline against `FakeTransport` and the test data in
`tests/data/` (recorder CSVs from Simplex Motion Tool plus a full register
dump).

## Documentation

The manufacturer's SE010A manual (publicly distributed by SimplexMotion) is
included in `docs/`.

## Status

The core layers (Transport/Register/Motor API) are in place. The tuning tool
(FastAPI backend, FFT analysis, recorder UI) hasn't been built yet.
