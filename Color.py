import RPi.GPIO as GPIO
import time

# ============================================================
# GLOBAL PIN VARIABLES
# ============================================================
_S2  = None
_S3  = None
_OUT = None

# ============================================================
# THRESHOLDS (CALIBRATED FOR ALUMINUM FOIL)
# ============================================================
SILVER_THRESHOLD = 0.0003  
BLUE_THRESHOLD   = 0.0015 

# ============================================================
# INITIALIZATION
# ============================================================

def init_color_sensor(s2_pin, s3_pin, out_pin):
    """Sets up the TCS3200 pins. Call this ONCE from main.py."""
    global _S2, _S3, _OUT
    _S2  = s2_pin
    _S3  = s3_pin
    _OUT = out_pin

    GPIO.setup([_S2, _S3], GPIO.OUT)
    GPIO.setup(_OUT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Default to CLEAR filter (S2=HIGH, S3=LOW)
    GPIO.output(_S2, GPIO.HIGH)
    GPIO.output(_S3, GPIO.LOW)
    
    print("Color Sensor Library Initialized.")

# ============================================================
# SENSOR READING LOGIC
# ============================================================

def _read_channel(s2_value, s3_value):
    GPIO.output(_S2, s2_value)
    GPIO.output(_S3, s3_value)
    time.sleep(0.01) 

    try:
        GPIO.wait_for_edge(_OUT, GPIO.RISING, timeout=50)
        start_time = time.time()
        GPIO.wait_for_edge(_OUT, GPIO.RISING, timeout=50)
        end_time   = time.time()
        return end_time - start_time
    
    except RuntimeError:
        return 999.0 

def read_rgb():
    red_time   = _read_channel(GPIO.LOW,  GPIO.LOW)
    green_time = _read_channel(GPIO.HIGH, GPIO.HIGH)
    blue_time  = _read_channel(GPIO.LOW,  GPIO.HIGH)
    
    # Reset to CLEAR filter after reading
    GPIO.output(_S2, GPIO.HIGH)
    GPIO.output(_S3, GPIO.LOW)
    
    return red_time, green_time, blue_time

# ============================================================
# MAIN EXECUTION FUNCTIONS
# ============================================================

def check_floor_color():
    """
    Evaluates the floor color.
    Returns: (is_blue_flag, is_silver_flag)
    """
    red, green, blue = read_rgb()
    
    is_blue   = False
    is_silver = False

    if red < SILVER_THRESHOLD and green < SILVER_THRESHOLD and blue < SILVER_THRESHOLD:
        is_silver = True
        return is_blue, is_silver 

    if blue < BLUE_THRESHOLD and blue < (red * 0.7) and blue < (green * 0.7):
        is_blue = True

    return is_blue, is_silver

def check_black_hole():
    """
    Fast check for black holes. Called by Mobility.py while driving.

    FIX #10: Before reading, we ALWAYS reset the filter to CLEAR
    (S2=HIGH, S3=LOW). This is critical because check_black_hole()
    is called mid-drive, completely independently of read_rgb().
    If read_rgb() was interrupted or the filter was left in RED or
    BLUE mode, the black hole reading would be wrong — causing either
    a false alarm or a missed black hole.
    """
    # FIX #10: Reset to CLEAR filter before reading.
    GPIO.output(_S2, GPIO.HIGH)
    GPIO.output(_S3, GPIO.LOW)

    # Wait for the pulse to go high. Timeout after 20ms.
    # A black hole absorbs all light → the sensor output stays LOW → timeout!
    edge = GPIO.wait_for_edge(_OUT, GPIO.RISING, timeout=20)
    if edge is None:
        return True   # Timeout = incredibly long pulse = Black Hole!
    return False
