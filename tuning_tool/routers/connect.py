from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from simplexmotion import PymodbusTransport, scan_bus

from ..state import state

router = APIRouter(prefix="/api", tags=["connect"])


class ScanRequest(BaseModel):
    port: str = "/dev/serial0"
    baudrate: int = 57600
    parity: str = "E"
    address_from: int = 1
    address_to: int = 31


class ConnectRequest(BaseModel):
    port: str = "/dev/serial0"
    baudrate: int = 57600
    parity: str = "E"
    address: int = 1


@router.post("/scan")
def scan(request: ScanRequest):
    try:
        transport = PymodbusTransport(
            port=request.port,
            baudrate=request.baudrate,
            parity=request.parity,
            timeout=0.2,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        found = scan_bus(transport, addresses=range(request.address_from, request.address_to + 1))
    finally:
        transport.close()
    return [{"address": m.address, "model_name": m.model_name, "serial_number": m.serial_number} for m in found]


@router.post("/connect")
def connect(request: ConnectRequest):
    try:
        state.connect(port=request.port, address=request.address, baudrate=request.baudrate, parity=request.parity)
    except ConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    motor = state.require_motor()
    try:
        return {
            "connected": True,
            "address": motor.address,
            "model_name": motor.model_name,
            "serial_number": motor.serial_number,
        }
    except Exception as e:
        state.disconnect()
        raise HTTPException(status_code=400, detail=f"Connected but could not read identity: {e}") from e


@router.post("/disconnect")
def disconnect():
    state.disconnect()
    return {"connected": False}


@router.get("/connect")
def connection_status():
    if not state.connected:
        return {"connected": False}
    motor = state.require_motor()
    return {
        "connected": True,
        "address": motor.address,
        "model_name": motor.model_name,
        "serial_number": motor.serial_number,
    }
