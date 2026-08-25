from ultralytics import YOLOWorld
import os
import shutil

print("Loading the model...")
model = YOLOWorld('yolov8s-world.pt')

# Folder setup
photo_folder = "./photo_folder" 
debug_folder = "./debug_folder" 

# Clean and recreate the debug folder
if os.path.exists(debug_folder):
    shutil.rmtree(debug_folder)
os.makedirs(debug_folder)

# 1. DISTRACTOR TRICK
# We look for beers, but we also look for objects that confuse the model!
classes_to_search = [
   "yellow beer in a cup",   # Index 0 (Focalizzato sul liquido giallo e la tazza)
    "dark beer in a cup",     # Index 1 (Focalizzato sul liquido scuro)
    "glass pint of beer",     # Index 2 (Focalizzato sul vetro)
    "water in a clear bottle",# Index 3 (DISTRATTORE - molto specifico sulla bottiglia)
    "red ketchup bottle"      # Index 4 (DISTRATTORE - focalizzato sul rosso)
]
model.set_classes(classes_to_search)

# Define which indices are actual beers (0 to 3)
beer_indices = [0, 1, 2]

total_beer_count = 0

print("Starting the scan...")

for filename in os.listdir(photo_folder):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        full_path = os.path.join(photo_folder, filename)
        
        # 2. OPTIMIZED PARAMETERS:
        # conf=0.25: High enough to cut out useless reflections.
        # iou=0.15: SUPER AGGRESSIVE. Eliminates overlapping double boxes on the same cup.
        results = model.predict(
            full_path, 
            conf=0.25,        
            iou=0.15,         
            agnostic_nms=True, 
            verbose=False
        )
        
        # Save the image with drawn bounding boxes
        save_path = os.path.join(debug_folder, f"debug_{filename}")
        results[0].save(filename=save_path)
        
        # 3. COUNT ONLY BEERS, IGNORE WATER AND KETCHUP
        beers_in_this_photo = 0
        for box in results[0].boxes:
            detected_class = int(box.cls[0]) # Get the index of the found object
            
            if detected_class in beer_indices:
                beers_in_this_photo += 1
                
        print(f"🍺 {beers_in_this_photo} beers found in: {filename}")
        total_beer_count += int(beers_in_this_photo)

print("-" * 30)
print(f"Final result: {total_beer_count} total beers.")
print("👉 Check the 'debug_folder' to see the bounding boxes!")