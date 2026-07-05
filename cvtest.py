import cv2
from ultralytics import YOLO
import Fast_Vision # Imports the file we just edited!

def test_single_image(model_path, image_path):
    print(f"Loading AI model from: {model_path}...")
    
    # We load the model directly into Fast_Vision's memory 
    # to avoid triggering the camera startup sequence.
    Fast_Vision.model = YOLO(model_path, task='classify')
    
    print(f"Loading test image from: {image_path}...")
    frame = cv2.imread(image_path)
    
    if frame is None:
        print("Error: Could not load the image. Please double-check the image path!")
        return
        
    print("Running AI prediction...")
    # Run the model on the single frame
    results = Fast_Vision.model(frame, verbose=False)[0]
    
    # Print the raw probabilities before the override to see what it's thinking
    print("\n--- RAW AI SCORES ---")
    names = results.names
    probs = results.probs.data.cpu().tolist()
    for i, score in enumerate(probs):
        print(f"{names[i]}: {score * 100:.2f}%")
        
    # Pass the results through our custom override logic
    final_color, final_conf = Fast_Vision.process_results(results)
    
    print("\n--- FINAL DECISION ---")
    print(f"Target Detected : {final_color.upper()}")
    print(f"Confidence      : {final_conf * 100:.2f}%")
    print("----------------------\n")

if __name__ == "__main__":
    # --- SETUP YOUR PATHS HERE ---
    # Replace 'best.pt' with the actual name of your model file
    MY_MODEL_PATH = "best.pt" 
    
    # Replace 'test_pic.jpg' with the actual path to the image you want to test
    MY_IMAGE_PATH = r'C:\Users\ym268\OneDrive - MOE Stem Schools\Desktop\red.jpeg'
    
    test_single_image(MY_MODEL_PATH, MY_IMAGE_PATH)