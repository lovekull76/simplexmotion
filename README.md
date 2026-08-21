# simplexmotion

Python-bibliotek för SimplexMotion SE010A-servomotorer över Modbus RTU (RS485).

Tre lager:

- **Transport** — `Transport`-protokollet, plus `PymodbusTransport` (standard, kräver
  ansluten hårdvara) och `FakeTransport` (spelar upp/håller register i minnet, för
  utveckling och test utan motor).
- **Register** (`simplexmotion.registers`) — adresser, skalningar, Mode/Status.
- **Motor API** — `Motor`, det som faktiskt används.

## Exempel

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

Flera motorer kan dela samma buss — transporten äger porten och serialiserar
åtkomsten, `Motor` äger bara adressen.

## Utveckling utan ansluten motor

```python
from simplexmotion import Motor, FakeTransport

bus = FakeTransport.from_config_csv("tests/data/config.csv")
motor = Motor(bus, address=1)
print(motor.model_name, motor.motor_speed_rpm)
```

## Tester

```
pip install -e ".[dev]"
pytest
```

Alla tester körs offline mot `FakeTransport` och testdata i `tests/data/`
(recorder-CSV:er från Simplex Motion Tool samt en fullständig registerdump).

## Status

Kärnlagren (Transport/Register/Motor API) är på plats. Tuning-verktyget
(FastAPI-backend, FFT-analys, recorder-UI) är inte byggt ännu.
