"""Holds the single shared Motor/Transport/Recorder connection for the whole
app. One motor at a time -- the transport owns the serial port exclusively,
so there's nothing to gain from juggling several connections in this tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException
from simplexmotion import Motor, PymodbusTransport, Recorder, RecorderData


@dataclass
class AppState:
    transport: PymodbusTransport | None = None
    motor: Motor | None = None
    recorder: Recorder | None = None
    last_recording: RecorderData | None = None
    last_recording_channel_names: list[str] = field(default_factory=list)

    @property
    def connected(self) -> bool:
        return self.motor is not None

    def connect(self, port: str, address: int, baudrate: int = 57600, parity: str = "E") -> None:
        if self.transport is not None:
            self.disconnect()
        self.transport = PymodbusTransport(port=port, baudrate=baudrate, parity=parity, timeout=1.0)
        self.motor = Motor(self.transport, address=address)
        self.recorder = Recorder(self.motor)

    def disconnect(self) -> None:
        if self.transport is not None:
            self.transport.close()
        self.transport = None
        self.motor = None
        self.recorder = None
        self.last_recording = None
        self.last_recording_channel_names = []

    def require_motor(self) -> Motor:
        if self.motor is None:
            raise HTTPException(status_code=409, detail="Not connected to a motor")
        return self.motor

    def require_recorder(self) -> Recorder:
        if self.recorder is None:
            raise HTTPException(status_code=409, detail="Not connected to a motor")
        return self.recorder


state = AppState()
