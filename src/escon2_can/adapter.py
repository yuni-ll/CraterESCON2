import serial
import struct
import threading
import time
from dataclasses import dataclass
from typing import List, Callable, Optional

@dataclass(frozen=True)
class CANFrame:
    id: int
    data: bytes
    def __repr__(self) -> str:
        return f"CANFrame(id={hex(self.id)}, data={self.data.hex(' ')})"

class USB2CANAdapter:
    def __init__(self, port: str, baud: int = 2000000) -> None:
        self.ser: serial.Serial = serial.Serial(port, baud, timeout=0.01)
        self._callback: Optional[Callable[[CANFrame], None]] = None
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

    def send(self, msg_id: int, data: List[int]) -> None:
        frame = bytearray([0xAA, 0x55, 0x01, 0x01, 0x00])
        frame += struct.pack('<I', msg_id)
        frame.append(len(data))
        frame += bytes(data).ljust(8, b'\x00')
        frame.append(0x00)
        frame.append(sum(frame[2:]) & 0xFF) 
        self.ser.write(frame)

    def _listen(self) -> None:
        while self._running:
            if self.ser.in_waiting >= 20:
                if self.ser.read(1) == b'\xAA' and self.ser.read(1) == b'\x55':
                    body: bytes = self.ser.read(18)
                    if len(body) == 18 and self._callback:
                        msg_id: int = struct.unpack('<I', body[3:7])[0]
                        dlc: int = body[7]
                        frame = CANFrame(id=msg_id, data=body[8:8+dlc])
                        self._callback(frame)
            time.sleep(0.001)

    def listen(self, callback_func: Callable[[CANFrame], None]) -> None:
        if self._running:
            return
        self._callback = callback_func
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self.ser.close()
