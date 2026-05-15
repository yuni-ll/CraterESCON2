import time
import threading
import struct
from typing import Optional
from .adapter import USB2CANAdapter, CANFrame
from .constants import ObjectIndex, OpMode, ControlCommand

_SDO_TIMEOUT = 0.100  # 100ms
_SDO_DOWNLOAD_ACK = 0x60
_SDO_ABORT = 0x80
_ABORT_CODES = {0x05040001: "Client/server command specifier not valid or unknown"}

class ESCON2:
    def __init__(self, bus: USB2CANAdapter, node_id: int) -> None:
        self.bus: USB2CANAdapter = bus
        self.node_id: int = node_id
        # cob ids
        self.tx_sdo_id: int = 0x580 + node_id
        self.rx_sdo_id: int = 0x600 + node_id
        self.rx_pdo_id: int = 0x200 + node_id 
        self.tx_pdo_id: int = 0x180 + node_id

        self._sdo_event = threading.Event()
        self._sdo_response: Optional[CANFrame] = None

        self.current_mode: Optional[OpMode] = None
        self.statusword: int = 0x0000
      
        self.actual_velocity: int = 0

    def _on_message(self, frame: CANFrame) -> None:
        if frame.id == self.tx_sdo_id:
            command_byte = frame.data[0]
            if command_byte in [0x4F, 0x4B, 0x43]:
                index = struct.unpack('<H', frame.data[1:3])[0]
                if index == ObjectIndex.STATUSWORD:
                    self.statusword = struct.unpack('<H', frame.data[4:6])[0]
                elif index == ObjectIndex.VELOCITY_ACTUAL:
                    self.actual_velocity = struct.unpack('<i', frame.data[4:8])[0]
        elif frame.id == self.tx_pdo_id:
            self.statusword = struct.unpack('<H', frame.data[0:2])[0]
            self.actual_velocity = struct.unpack('<i', frame.data[2:6])[0]

    def write_sdo(self, index: ObjectIndex, subindex: int, data: bytes) -> None:
        size = len(data)
        command_byte = 0x23 | ((4 - size) << 2)
        
        payload = bytearray([command_byte])
        payload += struct.pack('<H', index.value)
        payload.append(subindex)

        payload += data.ljust(4, b'\x00') 
        
    def nmt_start(self) -> None:
        # pre-op to op mode
        print(f"[node {self.node_id}] starting nmt command")
        self.bus.send(0x000, [0x01, self.node_id])

    def reset_fault(self) -> None:
        print(f"[NODE {self.node_id}] resetting faults...")
        self.write_sdo(ObjectIndex.CONTROLWORD, 0x00, int(0x0000).to_bytes(2, 'little'))
        time.sleep(0.05)
        self.write_sdo(ObjectIndex.CONTROLWORD, 0x00, ControlCommand.FAULT_RESET.value.to_bytes(2, 'little'))
        time.sleep(0.1)

    def set_mode(self, mode: OpMode) -> None:
        print(f"[NODE {self.node_id}] setting mode to {mode.name}")
        self.write_sdo(ObjectIndex.MODE_OF_OPERATION, 0x00, bytes([mode.value]))
        self.current_mode = mode

    def configure_profile_ramps(self, accel_rpm_s: int, decel_rpm_s: int) -> None:
        print(f"[NODE {self.node_id}] configuring ramps: accel={accel_rpm_s}, decel={decel_rpm_s}") # or is that done in escon studio already
        self.write_sdo(ObjectIndex.PROFILE_ACCELERATION, 0x00, accel_rpm_s.to_bytes(4, 'little', signed=False))
        time.sleep(0.02)
        self.write_sdo(ObjectIndex.PROFILE_DECELERATION, 0x00, decel_rpm_s.to_bytes(4, 'little', signed=False))
    
    def enable(self) -> None:
        print(f"[NODE {self.node_id}] enabling drive motor...")
        for cmd in [ControlCommand.SHUTDOWN, ControlCommand.SWITCH_ON, ControlCommand.ENABLE_OPERATION]:
            self.write_sdo(ObjectIndex.CONTROLWORD, 0x00, cmd.value.to_bytes(2, 'little'))
            time.sleep(0.05)

    def disable(self) -> None:
        print(f"[NODE {self.node_id}] disabling drive motor...")
        self.write_sdo(ObjectIndex.CONTROLWORD, 0x00, ControlCommand.DISABLE_VOLTAGE.value.to_bytes(2, 'little'))

    def set_velocity(self, rpm: int) -> None:
        if self.current_mode == OpMode.PROFILE_VELOCITY:
            data = rpm.to_bytes(4, byteorder='little', signed=True)
            self.write_sdo(ObjectIndex.TARGET_VELOCITY, 0x00, data)
            
        elif self.current_mode == OpMode.CYCLIC_SYNC_VELOCITY:
            payload = list(struct.pack('<i', int(rpm)))
            self.bus.send(self.rx_pdo_id, payload)
            
        else:
            raise RuntimeError(f"cannot set velocity while in mode: {self.current_mode}")
