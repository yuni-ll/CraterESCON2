import serial
import struct
import threading
import time
from dataclasses import dataclass
from typing import List, Callable, Optional

_SOF = b'\xAA\x55'
_FRAME_LEN = 20        
_HEADER_LEN = 2 
_CHECKSUM_RANGE = slice(2, 19) 
_ID_OFFSET = 5  
_DLC_OFFSET = 9
_DATA_OFFSET = 10

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
        dlc = len(data)
       
        frame = bytearray(_FRAME_LEN)
        frame[0] = 0xAA
        frame[1] = 0x55
        frame[2] = 0x01   
        frame[3] = 0x01  
        frame[4] = 0x00
        struct.pack_into('<I', frame, 5, msg_id)
        frame[9] = dlc
        frame[10:10 + dlc] = bytes(data)

        frame[18] = 0x00 
        frame[19] = sum(frame[_CHECKSUM_RANGE]) & 0xFF  
 
        self.ser.write(frame)

    def _listen(self) -> None:
        while self._running:
            if self.ser.in_waiting < _FRAME_LEN:
                time.sleep(0.001)
                continue
            
            b = self.ser.read(1)
            if b != b'\xAA': continue
            b = self.ser.read(1)
            if b != b'\x55': continue

            body = self.ser.read(18)
            if len(body) < 18: continue

            full_frame = b'\xAA\x55' + body
        
            msg_id = struct.unpack('<I', full_frame[5:9])[0]
            dlc = full_frame[9]
            data = full_frame[10:10+dlc]
            
            frame = CANFrame(id=msg_id, data=data)

            if self._callback:
                self._callback(frame)

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
