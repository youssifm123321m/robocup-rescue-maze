import RPi.GPIO as GPIO
import time
import math
import MPU 
import Color

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================

WHEEL_DIAMETER_CM = 3          
TICKS_PER_REVOLUTION = 20         
CELL_DISTANCE_CM = 30.0           

WHEEL_CIRCUMFERENCE = WHEEL_DIAMETER_CM * math.pi
TICKS_PER_CM = TICKS_PER_REVOLUTION / WHEEL_CIRCUMFERENCE
TICKS_PER_CELL = int(CELL_DISTANCE_CM * TICKS_PER_CM)

# Pin Definitions
IN1, IN2 = 27, 17 # Left Motor
IN3, IN4 = 23, 22  # Right Motor

ENC_LEFT_PIN  = 5
ENC_RIGHT_PIN = 6

STEP_PINS = [4, 16, 20, 21] 

LED_PIN = 18

# ============================================================
# GLOBAL VARIABLES
# ============================================================
left_ticks  = 0
right_ticks = 0
initial_north_heading = 0.0  

# ============================================================
# INITIALIZATION
# FIX #12: Removed MPU.init_mpu() from here.
#          main.py already calls it. Calling it twice was
#          spawning two background threads, doubling the
#          gyro integration speed and causing heading errors.
# ============================================================

def init_hardware():
    """Sets up all GPIO pins. Does NOT touch the MPU — main.py handles that."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup([IN1, IN2, IN3, IN4], GPIO.OUT)
    stop_motors()

    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)

    GPIO.setup(STEP_PINS, GPIO.OUT)

    GPIO.setup(ENC_LEFT_PIN,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(ENC_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(ENC_LEFT_PIN,  GPIO.RISING, callback=count_left_tick)
    GPIO.add_event_detect(ENC_RIGHT_PIN, GPIO.RISING, callback=count_right_tick)

    # FIX #12: MPU.init_mpu() intentionally removed from here.
    # main.py calls it once before calling init_hardware().

def calibrate_north(manual_angle=None):
    global initial_north_heading
    if manual_angle is not None:
        initial_north_heading = manual_angle
    else:
        initial_north_heading = MPU.get_heading()
    print(f"Calibrated: North is now {initial_north_heading} degrees.")

# ============================================================
# INTERRUPTS & SENSOR READING
# ============================================================

def count_left_tick(channel):
    global left_ticks
    left_ticks += 1

def count_right_tick(channel):
    global right_ticks
    right_ticks += 1

def is_black_hole():
    return Color.check_black_hole()

# ============================================================
# MOTOR CONTROLS
# ============================================================

def stop_motors():
    GPIO.output([IN1, IN2, IN3, IN4], GPIO.LOW)

def move_forward():
    GPIO.output(IN1, GPIO.HIGH); GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH); GPIO.output(IN4, GPIO.LOW)

def move_backward():
    GPIO.output(IN1, GPIO.LOW);  GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW);  GPIO.output(IN4, GPIO.HIGH)

def turn_right_inplace():
    GPIO.output(IN1, GPIO.HIGH); GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW);  GPIO.output(IN4, GPIO.HIGH)

def turn_left_inplace():
    GPIO.output(IN1, GPIO.LOW);  GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH); GPIO.output(IN4, GPIO.LOW)

def rotate_to_heading(target_angle):
    """Turns the robot until the MPU reading matches the target angle."""
    current = MPU.get_heading()
    diff = (target_angle - current) % 360
    
    if diff == 0:
        return
    elif diff < 180:
        turn_right_inplace()
    else:
        turn_left_inplace()

    while True:
        curr = MPU.get_heading()
        if abs(curr - target_angle) <= 15 or abs(curr - target_angle) >= 350:
            break
        time.sleep(0.01)
    
    stop_motors()

    # FIX #11: After every rotation, snap the MPU's internal angle to exactly
    # the target. This prevents small rounding errors from accumulating across
    # many turns during a long maze run (gyro drift correction).
    MPU.force_heading(target_angle)

# ============================================================
# KIT DROPPING
# FIX #4: drop_kits now receives the ABSOLUTE compass heading
#         (kit_heading) that was recorded the moment the victim
#         was spotted, instead of rotating relative to whatever
#         direction the robot happens to face right now.
#         This guarantees the robot always faces the correct
#         real-world direction when dropping kits.
# ============================================================

def drop_kits(num_kits, kit_heading, kit_side):
    """
    Rotates to the exact compass direction the victim was spotted from,
    blinks the LED, drops kits with the stepper, then rotates back.

    Parameters:
        num_kits   – how many kits to release (0 = just blink, no stepper)
        kit_heading – the MPU compass angle when the victim was first seen
        kit_side   – 'L' or 'R', which side of the robot the victim was on
    """
    if num_kits <= 0 or kit_heading is None:
        return

    # Save where we are pointing right now so we can come back to it.
    heading_before_drop = MPU.get_heading()

    # FIX #4: Calculate the absolute angle to face the victim.
    # If the victim was on the RIGHT when heading was kit_heading,
    # we need to face kit_heading + 90 degrees (absolute).
    # If on the LEFT, we face kit_heading - 90 degrees.
    if kit_side == 'R':
        drop_heading = (kit_heading + 90) % 360
    elif kit_side == 'L':
        drop_heading = (kit_heading - 90) % 360
    else:
        return  # Unknown side, do nothing safely.

    # Rotate to face the victim direction.
    rotate_to_heading(drop_heading)

    # Blink the LED 5 times.
    for _ in range(5):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(0.5)

    # Run the stepper motor to dispense kits.
    steps_needed  = int(318 * num_kits)
    step_sequence = [[1,0,0,1], [1,1,0,0], [0,1,1,0], [0,0,1,1]]
    
    for i in range(steps_needed):
        for pin, state in zip(STEP_PINS, step_sequence[i % 4]):
            GPIO.output(pin, state)
        time.sleep(0.002) 
    
    GPIO.output(STEP_PINS, GPIO.LOW)

    # Rotate back to the heading we were at before dropping.
    rotate_to_heading(heading_before_drop)

# ============================================================
# MAIN EXECUTION FUNCTION
# FIX #3: After reversing from a black hole, the robot now
#         calls rotate_to_heading() to correct any drift
#         that happened during the backward movement.
# FIX #4: execute_move now accepts kit_heading and kit_side
#         and passes them directly to drop_kits.
# ============================================================

def execute_move(direction, blue_flag, kit_heading, kit_side, num_kits):
    """
    Executes one cell movement. Returns (executed, black_hole_detected).

    Parameters:
        direction  – 'N', 'S', 'E', or 'W'
        blue_flag  – True if we should wait 5 seconds first
        kit_heading – absolute compass heading saved when victim was spotted
        kit_side   – 'L' or 'R' side from the camera
        num_kits   – how many kits to drop (0 = none)
    """
    global left_ticks, right_ticks, initial_north_heading

    if blue_flag:
        print("Blue floor detected. Waiting 5 seconds...")
        time.sleep(5)

    # FIX #4: Pass kit_heading and kit_side to drop_kits.
    if num_kits > 0:
        drop_kits(num_kits, kit_heading, kit_side)

    if direction not in ['N', 'S', 'E', 'W']:
        return False, False

    offsets = {'N': 0, 'E': 90, 'S': 180, 'W': 270}
    target_heading = (initial_north_heading + offsets[direction]) % 360

    rotate_to_heading(target_heading)

    left_ticks  = 0
    right_ticks = 0
    move_forward()

    while (left_ticks + right_ticks) / 2 < TICKS_PER_CELL:
        if is_black_hole():
            stop_motors()
            print("BLACK HOLE DETECTED! Reversing...")
            
            # Save how far we traveled before the black hole.
            ticks_traveled = (left_ticks + right_ticks) / 2
            
            # Reset and reverse the same distance.
            left_ticks  = 0
            right_ticks = 0
            move_backward()
            
            while (left_ticks + right_ticks) / 2 < ticks_traveled:
                time.sleep(0.01) 
            
            stop_motors()

            # FIX #3: After reversing, the robot may have drifted slightly.
            # Snap back to the exact heading we were facing before we moved.
            # This puts the robot back in the correct orientation in the cell.
            rotate_to_heading(target_heading)

            return False, True 

        time.sleep(0.01)

    stop_motors()
    return True, False

def cleanup_hardware():
    MPU.stop_mpu()
    GPIO.cleanup()
