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

## Motor API reference

Everything below is a plain Python property/method on `Motor` — reads issue a
Modbus read, writes issue a Modbus write, nothing is cached.

### Identity (read-only)

| Property | Type | Description |
|---|---|---|
| `model_name` | `str` | e.g. `"SimplexMotionSE010A"` |
| `serial_number` | `str` | e.g. `"SE010A-2211005047"` |
| `ver_firmware` | `int` | Firmware version |
| `ver_hardware` | `int` | Hardware version |

### Control

| Property | Type | Description |
|---|---|---|
| `mode` | `Mode` | `Mode.OFF`, `Mode.SPEED_RAMP`, `Mode.RESET`, `Mode.STORE`, `Mode.RELOAD`, `Mode.FACTORY` |
| `speed_rpm` | `float` | Target speed, rpm (signed — negative reverses direction) |
| `ramp_speed_max_rpm` | `float` | Speed ramp ceiling, rpm |
| `ramp_acc_max` | `float` | Max acceleration, rpm/s |
| `ramp_dec_max` | `float` | Max deceleration, rpm/s |
| `speed_filter` | `int` | Speed measurement filter (0-15) |
| `target_filter` | `int` | Target input filter (0-16) |
| `torque_max` | `int` | Torque limit, mNm |
| `torque_stop` | `int` | Torque trip threshold, mNm |

### PID / control loop (`motor.pid.*`)

| Property | Description |
|---|---|
| `pid.kp` | Proportional gain |
| `pid.ki` | Integral gain |
| `pid.kd` | Derivative gain |
| `pid.limit` | Output limit |
| `pid.delay` | Derivative filtering |
| `pid.friction` | Speed feed-forward |
| `pid.inertia` | Acceleration feed-forward |
| `pid.deadband` | Error deadband |
| `pid.error_max` | Trip level for the Regulator status bit |

### Measurements (read-only)

| Property | Type | Description |
|---|---|---|
| `supply_voltage` | `float` | Volts |
| `temp_electronics` | `float` | Degrees C |
| `temp_motor` | `float` | Degrees C |
| `motor_speed_rpm` | `float` | Actual speed, rpm |
| `motor_torque` | `int` | mNm |
| `reg_error` | `int` | Control loop error, ±8192 |
| `reg_output` | `int` | Control loop output |
| `ramp_speed_rpm` | `float` | Current ramp setpoint, rpm |

### Status (read-only)

`status` and `status_latched` each return a `Status` object with one boolean
per status bit: `fail`, `communication`, `current`, `voltage`, `temperature`,
`torque_limit`, `locked_shaft`, `regulator`, `moving`, `reverse`, `target`,
`input_a`, `input_b`, `user1`, `user2`.

### Non-volatile memory

| Method | Description |
|---|---|
| `store()` | Save current register values to non-volatile memory (Mode = 9) |
| `reload()` | Discard unsaved changes, read back saved values (Mode = 8) |
| `factory_reset()` | Reset everything, including address and comms settings (Mode = 7) |

### Bus scanning

```python
from simplexmotion import scan_bus

for info in scan_bus(bus, addresses=range(1, 32)):
    print(info.address, info.model_name, info.serial_number)
```

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

## Tuning tool

`tuning_tool/` is a FastAPI + vanilla-JS web app for live parameter tuning,
realtime plotting, and recorder/FFT diagnostics. See
[`tuning_tool/README.md`](tuning_tool/README.md) for setup and usage.

## Status

The core layers (Transport/Register/Motor API) and the tuning tool are in
place. Not yet built: a shared-bus daemon so the tuning tool and another
consumer (e.g. a running control process) can use the port at the same
time -- for now, whichever needs the port must have exclusive access.
