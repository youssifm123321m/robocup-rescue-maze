import time
import RPi.GPIO as GPIO
import MPU
import Mobility
import Map
import Color
import Fast_Vision
import logic

# ============================================================
# 1. HARDWARE CONFIGURATION & BUTTON LOGIC
# ============================================================
PLAY_PIN  = 9   
RESET_PIN = 10  

is_playing      = False
reset_triggered = False

def play_callback(channel):
    global is_playing
    is_playing = not is_playing
    if is_playing:
        print("\n▶️ PLAY BUTTON PRESSED: Robot is now RUNNING!")
    else:
        print("\n⏸️ PLAY BUTTON PRESSED: Robot is now PAUSED!")

def reset_callback(channel):
    global reset_triggered
    reset_triggered = True
    print("\n🔄 RESET BUTTON PRESSED: Memory will reset on the next move!")

def init_buttons():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PLAY_PIN,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(RESET_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(PLAY_PIN,  GPIO.FALLING, callback=play_callback,  bouncetime=500)
    GPIO.add_event_detect(RESET_PIN, GPIO.FALLING, callback=reset_callback, bouncetime=500)

# ============================================================
# 2. BOOT UP & INITIALIZATION
# ============================================================
print("--- Starting RoboCup Rescue Robot ---")

print("Waking up Buttons...")
init_buttons()

# FIX #12: MPU is initialized FIRST and ONLY ONCE here.
# Mobility.init_hardware() no longer calls MPU.init_mpu() internally,
# so there is now exactly one background gyro thread — no double counting.
print("Waking up MPU...")
MPU.init_mpu()

print("Waking up Mobility...")
Mobility.init_hardware()

print("Waking up Ultrasonics...")
Map.init_ultrasonics()

print("Waking up Color Sensor...")
Color.init_color_sensor(s2_pin=13, s3_pin=19, out_pin=26)

print("Loading AI Vision Model...")
Fast_Vision.init_vision(model_path='best.pt', left_cam_index=0, right_cam_index=1, conf_threshold=0.70)

# ============================================================+
# 3. CALIBRATE TRUE NORTH
# ============================================================
print("Calibrating True North... Please keep the robot still.")
time.sleep(2) 

shared_true_north = MPU.get_heading()

Mobility.calibrate_north(shared_true_north)
Map.calibrate_map_north(shared_true_north)

print(f"--- ROBOT READY! True North locked at: {shared_true_north:.2f} degrees ---")
print("Robot is paused. Press the PLAY button to begin!")
time.sleep(1)

# ============================================================
# 4. STATE VARIABLES
# ============================================================
last_move_executed = True
hit_black_hole     = False

# ============================================================
# 5. THE MAIN MAZE LOOP
# ============================================================
try:
    while True:
        if not is_playing:
            time.sleep(0.5)
            continue

        print("\n--- NEW CELL ---")
        
        current_reset_signal = reset_triggered
        reset_triggered      = False 

        # STEP 1: Look at the walls & floor
        available_paths      = Map.get_surroundings()
        is_blue, is_silver   = Color.check_floor_color()

        # STEP 2: Look for Victims
        target, side = Fast_Vision.get_vision_data(return_frames=False)
        actual_victim = None if target == "None" else target
        
        if actual_victim:
            print(f"Vision Alert: I see a {actual_victim} on the {side} side!")

        # FIX #4 + FIX #11: Read the current compass heading right now
        # and pass it into decide(). This is the heading at the exact moment
        # the victim is seen, so kit dropping will face the correct direction.
        current_compass = MPU.get_heading()

        # STEP 3: Ask the Brain what to do.
        # NOTE: logic.decide() now returns 5 values instead of 3:
        #   direction, handle_blue, num_kits, kit_heading, kit_side
        direction, handle_blue, num_kits, kit_heading, kit_side = logic.decide(
            walls                = available_paths,
            executed             = last_move_executed,
            victim               = actual_victim,
            victim_side          = side,           # FIX #4
            current_heading      = current_compass, # FIX #4 + #11
            black_hole           = hit_black_hole,
            blue_floor           = is_blue,
            silver_floor         = is_silver,
            reset_to_checkpoint  = current_reset_signal, 
            play_signal          = True
        )
        
        print(f"Brain says: Move {direction}. Kits to drop: {num_kits}")

        # STEP 4: Check if the maze is done
        if direction == 'DONE':
            print("Maze Complete! Returning to start.")
            break 
        elif direction == 'STOP':
            continue

        # STEP 5: Tell Mobility to physically drive.
        # FIX #4: Pass kit_heading and kit_side instead of just side.
        last_move_executed, hit_black_hole = Mobility.execute_move(
            direction   = direction, 
            blue_flag   = handle_blue, 
            kit_heading = kit_heading,   # FIX #4
            kit_side    = kit_side,      # FIX #4
            num_kits    = num_kits  
        )

except KeyboardInterrupt:
    # ============================================================
    # 6. CLEAN SHUTDOWN
    # ============================================================
    print("\nShutting down Robot gracefully...")
    MPU.stop_mpu()
    Mobility.cleanup_hardware()
    GPIO.cleanup() 
    print("Done. Goodbye!")
