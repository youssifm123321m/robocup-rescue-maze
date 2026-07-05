import RPi.GPIO as GPIO
import time
import MPU

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================
# Since the cell is 30x30 cm, if the robot is in the middle, 
# a wall is ~15 cm away. An open path to the next cell is > 30 cm.
WALL_THRESHOLD_CM = 20.0  

# Pin Definitions (Replace these with your actual GPIO pins)
TRIG_F, ECHO_F = 24, 25  # Front Sensor
TRIG_B, ECHO_B = 8, 7    # Back Sensor
TRIG_R, ECHO_R = 1, 12   # Right Sensor
TRIG_L, ECHO_L = 14, 15  # Left Sensor

north_calibration_angle = 0.0  # Stores what angle "North" is

# ============================================================
# INITIALIZATION
# ============================================================

def init_ultrasonics():
    """Sets up the GPIO pins for all 4 ultrasonic sensors."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup Triggers as Outputs
    GPIO.setup([TRIG_F, TRIG_B, TRIG_R, TRIG_L], GPIO.OUT)
    # Setup Echoes as Inputs
    GPIO.setup([ECHO_F, ECHO_B, ECHO_R, ECHO_L], GPIO.IN)

    # Ensure triggers are calm
    GPIO.output([TRIG_F, TRIG_B, TRIG_R, TRIG_L], GPIO.LOW)
    time.sleep(0.5)
    print("Ultrasonic Map Library Initialized.")

def calibrate_map_north(angle):
    """Tells the library what MPU angle represents true 'North'."""
    global north_calibration_angle
    north_calibration_angle = angle

# ============================================================
# INTERNAL SENSOR READING
# ============================================================

def _get_distance(trig_pin, echo_pin):
    """Fires a single sensor safely with a timeout to prevent freezing."""
    # 1. Send a 10-microsecond pulse
    GPIO.output(trig_pin, True)
    time.sleep(0.00001)
    GPIO.output(trig_pin, False)

    start_time = time.time()
    stop_time = time.time()
    
    # 40 millisecond timeout (prevents code from getting stuck forever)
    timeout = time.time() + 0.04 

    # 2. Wait for the echo to go HIGH
    while GPIO.input(echo_pin) == 0:
        start_time = time.time()
        if start_time > timeout:
            return 999.0 # Timeout (pretend path is wide open)

    # 3. Wait for the echo to go LOW
    while GPIO.input(echo_pin) == 1:
        stop_time = time.time()
        if stop_time > timeout:
            return 999.0 # Timeout

    # 4. Calculate Distance
    time_elapsed = stop_time - start_time
    distance = (time_elapsed * 34300) / 2
    return distance

# ============================================================
# MAIN EXECUTION FUNCTION (MAP GENERATION)
# ============================================================

def get_surroundings():
    """
    Fires all sensors, checks for walls, reads the MPU, 
    and returns an absolute [North, South, East, West] list.
    1 = Open Path, 0 = Wall
    """
    # 1. Read raw distances from all 4 sensors
    dist_F = _get_distance(TRIG_F, ECHO_F)
    dist_B = _get_distance(TRIG_B, ECHO_B)
    dist_R = _get_distance(TRIG_R, ECHO_R)
    dist_L = _get_distance(TRIG_L, ECHO_L)

    # 2. Convert distances to binary (1 = Open, 0 = Wall)
    open_F = 1 if dist_F > WALL_THRESHOLD_CM else 0
    open_B = 1 if dist_B > WALL_THRESHOLD_CM else 0
    open_R = 1 if dist_R > WALL_THRESHOLD_CM else 0
    open_L = 1 if dist_L > WALL_THRESHOLD_CM else 0

    # 3. Get the robot's current heading from the MPU file
    raw_heading = MPU.get_heading()
    
    # Normalize the heading so 0 is ALWAYS our calibrated North
    relative_heading = (raw_heading - north_calibration_angle) % 360

    # 4. Determine which way the robot is currently facing
    # We divide by 90 and round to find the nearest cardinal direction
    # 0 = North, 1 = East, 2 = South, 3 = West
    facing = round(relative_heading / 90.0) % 4

    # 5. Map the relative sensors to absolute directions [N, S, E, W]
    if facing == 0:
        # Facing North (0 degrees)
        N = open_F
        S = open_B
        E = open_R
        W = open_L
    
    elif facing == 1:
        # Facing East (90 degrees) -> Front is East, Back is West, Left is North
        N = open_L
        S = open_R
        E = open_F
        W = open_B

    elif facing == 2:
        # Facing South (180 degrees) -> Front is South, Back is North
        N = open_B
        S = open_F
        E = open_L
        W = open_R

    elif facing == 3:
        # Facing West (270 degrees) -> Front is West, Right is North
        N = open_R
        S = open_L
        E = open_B
        W = open_F

    return [N, S, E, W]