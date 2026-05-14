import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from escon2_can import USB2CANAdapter, CANFrame

def print_incoming_frame(frame: CANFrame) -> None:
    print(f"intercepted frame | id: {hex(frame.id).upper().ljust(6)} | payload data: {frame.data.hex(' ')}")

# check device manager
PORT = 'COMx' 

def main():
    print(f"initializing usb-to-can sniffer on port: {PORT}...")
    bus = USB2CANAdapter(port=PORT)
    bus.listen(print_incoming_frame)
    print("listening... press ctrl+c to terminate.")

    try:
        while True:
            bus.send(0x123, [0x11, 0x22, 0x33])
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n interrupted by user")
        bus.stop()

if __name__ == "__main__":
    main()
