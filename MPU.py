import smbus
import time
import threading

# ============================================================
# MPU6050 CONFIGURATION (Z-AXIS ONLY)
# ============================================================
bus = smbus.SMBus(1)
MPU_ADDRESS = 0x68

# Global state
current_z_angle = 0.0
gyro_running    = False

# FIX #11: A lock to make reading and writing the angle thread-safe.
# Without this, the main thread could read a half-updated value while
# the background thread is in the middle of writing it.
_angle_lock = threading.Lock()

# ============================================================
# INTERNAL MATH FUNCTIONS
# ============================================================

def _read_raw_gyro_data(addr):
    """Reads 16-bit raw data from the I2C bus."""
    high  = bus.read_byte_data(MPU_ADDRESS, addr)
    low   = bus.read_byte_data(MPU_ADDRESS, addr + 1)
    value = ((high << 8) | low)
    if value > 32768:
        value = value - 65536
    return value

def _gyro_integration_loop():
    """Runs continuously in the background to track the Z-axis angle."""
    global current_z_angle, gyro_running
    last_time = time.time()
    
    while gyro_running:
        current_time = time.time()
        dt           = current_time - last_time
        last_time    = current_time
        
        try:
            raw_z        = _read_raw_gyro_data(0x47)
            z_deg_per_sec = raw_z / 131.0
            
            if abs(z_deg_per_sec) > 1.5:
                with _angle_lock:
                    current_z_angle = (current_z_angle + z_deg_per_sec * dt) % 360.0
                
        except Exception:
            pass
            
        time.sleep(0.01)

# ============================================================
# PUBLIC FUNCTIONS
# ============================================================

def init_mpu():
    """Wakes up the MPU6050 and starts tracking the Z-axis."""
    global gyro_running
    try:
        bus.write_byte_data(MPU_ADDRESS, 0x6B, 0x00)
        bus.write_byte_data(MPU_ADDRESS, 0x1B, 0x00)
        
        gyro_running  = True
        gyro_thread   = threading.Thread(target=_gyro_integration_loop, daemon=True)
        gyro_thread.start()
        print("MPU Sensor initialized: Z-Axis tracking started.")
    except Exception as e:
        print(f"Warning: MPU6050 not detected. Error: {e}")

def get_heading():
    """Returns the current calculated Z-axis angle (0-360)."""
    with _angle_lock:
        return current_z_angle

def force_heading(angle):
    """
    FIX #11: Forcefully sets the internal angle to a known correct value.
    
    Called by Mobility.rotate_to_heading() after every rotation completes.
    Because the robot physically stopped at 'angle' degrees, we can snap
    the software value to exactly that number. This prevents small rounding
    errors from the gyro integration from building up over many turns.
    
    Example: robot rotates to 90°. Gyro says 89.7°. We snap it to 90.0°.
    Next rotation starts from a clean 90.0° instead of a drifted 89.7°.
    """
    global current_z_angle
    with _angle_lock:
        current_z_angle = float(angle) % 360.0

def stop_mpu():
    """Stops the background thread safely."""
    global gyro_running
    gyro_running = False
