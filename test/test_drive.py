import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from escon2_can import USB2CANAdapter, ESCON2, OpMode

# check device manager
PORT = 'COMx' 

def main():
    NODE1, NODE2, NODE3, NODE4 = 1, 2, 3, 4
    print(f"initializing bus on port: {PORT}...")
    bus = USB2CANAdapter(port=PORT)
    drive1 = ESCON2(bus=bus, node_id=NODE1)
    drive2 = ESCON2(bus=bus, node_id=NODE2)
    drive3 = ESCON2(bus=bus, node_id=NODE3)
    drive4 = ESCON2(bus=bus, node_id=NODE4)
  
    drives = [drive1, drive2, drive3, drive4]

    def master_bus_callback(frame):
        for drive in drives:
            drive._on_message(frame)
            
    bus.listen(master_bus_callback)

    try:
        print("\n starting nmt...")
        for drive in drives:
            drive.nmt_start()
        time.sleep(0.5)

        print("\n enabling motor chain...")
        for drive in drives:
            drive.reset_fault()
            time.sleep(0.05)
          
            drive.set_mode(OpMode.PROFILE_VELOCITY)
          
            drive.configure_profile_ramps(accel_rpm_s=500, decel_rpm_s=500)

            drive.enable()
        time.sleep(1.0)

        print("\n commanding velocity targets: ")
        drive1.set_velocity(500)
        drive2.set_velocity(500)
        drive3.set_velocity(300)
        drive4.set_velocity(-500) # Opposite direction axis test
        
        # Let it spin for 5 seconds while tracking the statusword via telemetry
        print("\n streaming: ")
        for _ in range(50):
            s1 = hex(drive1.statusword).upper().ljust(6)
            s2 = hex(drive2.statusword).upper().ljust(6)
            s3 = hex(drive3.statusword).upper().ljust(6)
            s4 = hex(drive4.statusword).upper().ljust(6)
            
            v1 = drive1.actual_velocity
            v2 = drive2.actual_velocity
            v3 = drive3.actual_velocity
            v4 = drive4.actual_velocity
            
            print(f"Status | Node1: {s1} (v: {v1}) | Node2: {s2} (v: {v2}) | Node3: {s3} (v: {v3}) | Node4: {s4} (v: {v4})")
            time.sleep(0.1) #
            
        print("\n decelerating... ")
        for drive in drives:
            drive.set_velocity(0)
        time.sleep(1.5) 
    
        print("disabling motor chain...")
        for drive in drives:
            drive.disable()

    except KeyboardInterrupt:
        print("\n[USER] interrupted by user")
        for drive in drives:
            try:
                drive.set_velocity(0)
                drive.disable()
            except Exception:
                pass
            
    finally:
        print("\n shutting down...")
        bus.stop() 
        print("system closed down cleanly.")

if __name__ == "__main__":
    main()
