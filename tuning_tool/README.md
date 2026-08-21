# SimplexMotion tuning tool

A small FastAPI + vanilla-JS web app for live parameter tuning, realtime
plotting, and recorder/FFT diagnostics against a connected SE010A. Built on
top of the `simplexmotion` library in this repo.

## Requirements

- Exclusive access to the motor's serial port. If something else (e.g. the
  `fermenter` systemd service on the Raspberry Pi) already owns it, stop
  that first:
  ```
  sudo systemctl stop fermenter
  ```
  There's no shared-bus daemon yet -- see the main README's Status section.
- Run it where the serial port actually is (typically the Pi itself).

## Setup

```
git clone https://github.com/lovekull76/simplexmotion.git
cd simplexmotion
pip install -e ".[tuning]"
```

## Run

Run from the repo root (the directory containing `tuning_tool/`) -- `uvicorn`
resolves `tuning_tool.app:app` as a Python module import, so it fails if you're
anywhere else:

```
cd simplexmotion   # or wherever you cloned it, e.g. /home/pi/simplexmotion-repo
uvicorn tuning_tool.app:app --host 0.0.0.0 --port 8000
```

Open `http://<host>:8000/` from a browser anywhere on the LAN.

## Notes

- Parameter profiles are saved as JSON under `tuning_tool/profiles/` (gitignored).
- The recorder can only capture 16-bit registers -- see `RECORDABLE_CHANNELS`
  in `tuning_tool/routers/recorder.py` for the list.
- When done, stop the tool and restart whatever service normally owns the
  port (e.g. `sudo systemctl start fermenter`).
