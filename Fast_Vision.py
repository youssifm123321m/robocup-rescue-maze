# from ultralytics import YOLO
# import cv2

# # Global variables to hold the model and cameras in the background
# model = None
# cap_left = None
# cap_right = None
# threshold = 0.70

# def init_vision(model_path, left_cam_index=1, right_cam_index=2, conf_threshold=0.70):
#     """Loads the model and opens the cameras ONCE at the start."""
#     global model, cap_left, cap_right, threshold
    
#     threshold = conf_threshold
    
#     print("Loading AI Model...")
#     model = YOLO(model_path, task='classify')
    
#     print("Opening Left Camera...")
#     cap_left = cv2.VideoCapture(left_cam_index)
    
#     print("Opening Right Camera...")
#     cap_right = cv2.VideoCapture(right_cam_index)

# def process_results(results):
#     """
#     Helper function to evaluate confidence scores and apply the custom override.
#     """
#     names = results.names
#     # Extract raw probabilities for all classes
#     probs = results.probs.data.cpu().tolist()
    
#     # Find the dictionary keys (indices) for 'red' and 'yellow' dynamically
#     red_idx = next((k for k, v in names.items() if v.lower() == 'red'), None)
#     yellow_idx = next((k for k, v in names.items() if v.lower() == 'yellow'), None)
    
#     # Apply the custom override logic
#     if red_idx is not None and yellow_idx is not None:
#         conf_red = probs[red_idx]
#         conf_yellow = probs[yellow_idx]
        
#         # If Yellow is 55%-65% AND Red is 20%-30%
#         if 0.55 <= conf_yellow <= 0.65 and 0.20 <= conf_red <= 0.30:
#             # Override and return 'red' with 100% confidence so it passes the threshold
#             return names[red_idx], 1.0 
            
#     # If the custom condition is not met, return the standard top prediction
#     top1_conf = results.probs.top1conf.item()
#     top1_name = names[results.probs.top1]
    
#     return top1_name, top1_conf

# def get_vision_data(return_frames=False):
#     """
#     Reads both cameras, runs the AI, and returns the highest confidence result.
#     If return_frames=True, it also returns the raw image frames for display.
#     """
#     global model, cap_left, cap_right, threshold

#     if model is None or cap_left is None or cap_right is None:
#         print("Error: Vision not initialized! Call init_vision() first.")
#         if return_frames:
#             return "None", "None", None, None
#         return "None", "None"

#     # Grab frames from both cameras instantly
#     success_l, frame_l = cap_left.read()
#     success_r, frame_r = cap_right.read()

#     best_target = "None"
#     best_side = "None"
#     highest_conf = 0.0

#     # Check Left Camera
#     if success_l:
#         results_l = model(frame_l, verbose=False)[0]
#         target_l, conf_l = process_results(results_l)
        
#         if conf_l >= threshold:
#             highest_conf = conf_l
#             best_target = target_l
#             best_side = "L"

#     # Check Right Camera
#     if success_r:
#         results_r = model(frame_r, verbose=False)[0]
#         target_r, conf_r = process_results(results_r)
        
#         if conf_r > highest_conf and conf_r >= threshold:
#             best_target = target_r
#             best_side = "R"

#     if return_frames:
#         return best_target, best_side, frame_l, frame_r
        
#     return best_target, best_side

# def close_vision():
#     """Safely turns off the cameras."""
#     global cap_left, cap_right
#     if cap_left: cap_left.release()
#     if cap_right: cap_right.release()
from ultralytics import YOLO
import cv2

# Global variables to hold the model and cameras in the background
model = None
cap_left = None
cap_right = None
threshold = 0.70

def init_vision(model_path, left_cam_index=1, right_cam_index=2, conf_threshold=0.70):
    """Loads the model and opens the cameras ONCE at the start."""
    global model, cap_left, cap_right, threshold
    
    threshold = conf_threshold
    
    print("Loading AI Model...")
    model = YOLO(model_path, task='classify')
    
    print("Opening Left Camera...")
    cap_left = cv2.VideoCapture(left_cam_index)
    
    print("Opening Right Camera...")
    cap_right = cv2.VideoCapture(right_cam_index)

def process_results(results):
    """
    Helper function to evaluate confidence scores and apply custom overrides.
    """
    names = results.names
    # Extract raw probabilities for all classes
    probs = results.probs.data.cpu().tolist()
    
    # Find the dictionary keys (indices) for 'red' and 'yellow' dynamically
    red_idx = next((k for k, v in names.items() if v.lower() == 'red'), None)
    yellow_idx = next((k for k, v in names.items() if v.lower() == 'yellow'), None)
    
    if red_idx is not None:
        conf_red = probs[red_idx]
        
        # --- OVERRIDE RULE 1: Red False Positives ---
        # If the model is more than 75% confident it's red, it's actually blank
        if conf_red > 0.75:
            # We return "blank" and force confidence to 1.0 so it passes the main threshold
            return "blank", 1.0
            
        # --- OVERRIDE RULE 2: Yellow/Red Confusion ---
        if yellow_idx is not None:
            conf_yellow = probs[yellow_idx]
            # If Yellow is 55%-65% AND Red is 20%-30%
            if 0.55 <= conf_yellow <= 0.65 and 0.20 <= conf_red <= 0.30:
                # It is actually Red
                return names[red_idx], 1.0 
            
    # If no custom conditions are met, return the standard top prediction
    top1_conf = results.probs.top1conf.item()
    top1_name = names[results.probs.top1]
    
    return top1_name, top1_conf

def get_vision_data(return_frames=False):
    """
    Reads both cameras, runs the AI, and returns the highest confidence result.
    If return_frames=True, it also returns the raw image frames for display.
    """
    global model, cap_left, cap_right, threshold

    if model is None or cap_left is None or cap_right is None:
        print("Error: Vision not initialized! Call init_vision() first.")
        if return_frames:
            return "None", "None", None, None
        return "None", "None"

    # Grab frames from both cameras instantly
    success_l, frame_l = cap_left.read()
    success_r, frame_r = cap_right.read()

    best_target = "None"
    best_side = "None"
    highest_conf = 0.0

    # Check Left Camera
    if success_l:
        results_l = model(frame_l, verbose=False)[0]
        target_l, conf_l = process_results(results_l)
        
        if conf_l >= threshold:
            highest_conf = conf_l
            best_target = target_l
            best_side = "L"

    # Check Right Camera
    if success_r:
        results_r = model(frame_r, verbose=False)[0]
        target_r, conf_r = process_results(results_r)
        
        if conf_r > highest_conf and conf_r >= threshold:
            best_target = target_r
            best_side = "R"

    if return_frames:
        return best_target, best_side, frame_l, frame_r
        
    return best_target, best_side

def close_vision():
    """Safely turns off the cameras."""
    global cap_left, cap_right
    if cap_left: cap_left.release()
    if cap_right: cap_right.release()