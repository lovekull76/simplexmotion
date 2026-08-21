"""Live read-only measurements: a plain snapshot endpoint plus a ~10Hz
WebSocket stream for the realtime plot (RS485 at 57600 baud caps the
achievable rate, per the handover doc)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from simplexmotion import registers as regs

from ..state import state

router = APIRouter(tags=["live"])

LIVE_POLL_INTERVAL_S = 0.1

# Tracked so app shutdown can close them explicitly -- an open WebSocket
# (e.g. a browser tab left on the live chart) otherwise keeps uvicorn's
# graceful shutdown waiting forever for a connection that never closes itself.
_active_websockets: set[WebSocket] = set()


async def close_all_websockets() -> None:
    for ws in list(_active_websockets):
        try:
            await ws.close()
        except Exception:
            pass


def _snapshot() -> dict:
    motor = state.require_motor()
    status = motor.status
    return {
        "supply_voltage": motor.supply_voltage,
        "temp_electronics": motor.temp_electronics,
        "temp_motor": motor.temp_motor,
        "motor_speed_rpm": motor.motor_speed_rpm,
        "motor_torque": motor.motor_torque,
        "reg_error": motor.reg_error,
        "reg_output": motor.reg_output,
        "ramp_speed_rpm": motor.ramp_speed_rpm,
        "status": {bit: getattr(status, bit) for bit in regs.STATUS_BIT_NAMES},
    }


@router.get("/api/live")
def get_live():
    return _snapshot()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    _active_websockets.add(websocket)
    try:
        while True:
            if state.connected:
                try:
                    await websocket.send_json(_snapshot())
                except Exception:
                    pass
            await asyncio.sleep(LIVE_POLL_INTERVAL_S)
    except WebSocketDisconnect:
        pass
    finally:
        _active_websockets.discard(websocket)
