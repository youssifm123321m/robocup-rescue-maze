import RPi.GPIO as GPIO
import time

# Use the pins from your project
S2, S3, OUT = 13, 19, 26 

GPIO.setmode(GPIO.BCM)
GPIO.setup([S2, S3], GPIO.OUT)
GPIO.setup(OUT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def read_raw():
    # Helper to read Red, Green, and Blue raw pulse times
    channels = {'RED': (GPIO.LOW, GPIO.LOW), 'GREEN': (GPIO.HIGH, GPIO.HIGH), 'BLUE': (GPIO.LOW, GPIO.HIGH)}
    results = {}
    
    for name, (s2_val, s3_val) in channels.items():
        GPIO.output(S2, s2_val)
        GPIO.output(S3, s3_val)
        time.sleep(0.1) # Stability wait
        
        start = time.time()
        # Wait for a pulse (timeout after 0.1s)
        edge = GPIO.wait_for_edge(OUT, GPIO.FALLING, timeout=100)
        if edge is None:
            results[name] = 0.1 # Max timeout
        else:
            results[name] = time.time() - start
            
    return results

try:
    print("--- TCS3200 Color Calibration Mode ---")
    print("Place sensor over the surface and wait...")
    while True:
        data = read_raw()
        print(f"R: {data['RED']:.5f} | G: {data['GREEN']:.5f} | B: {data['BLUE']:.5f}")
        time.sleep(0.5)
except KeyboardInterrupt:
    GPIO.cleanup()