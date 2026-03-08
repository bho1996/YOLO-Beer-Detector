# 🍺 YOLO-World Beer Detector

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Ultralytics](https://img.shields.io/badge/Ultralytics-YOLOv8-orange.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-lightgrey.svg)

An AI-powered Python script that uses the zero-shot capabilities of **YOLO-World** to scan a folder of photos and count exactly how many beers are present. 

Whether it's a classic glass pint, a plastic cup, or a dark stout in a custom opaque cup, this script finds it. It even uses a clever "distractor" logic to stop confusing beers with common party items like ketchup and water bottles!

## 🌟 Key Features

* **Zero-Shot Detection:** Uses the `yolov8s-world.pt` model to detect objects purely by text description. No custom training required.
* **Smart Filtering (Agnostic NMS):** Aggressively removes duplicate bounding boxes on transparent objects (like plastic cups) using an optimized Intersection Over Union (IoU) threshold.
* **Distractor Logic:** Specifically instructed to recognize and *ignore* common false positives (e.g., water bottles, ketchup) to keep the final count accurate.
* **Visual Debugging:** Automatically generates a `debug_folder` where you can see exactly where the AI drew its bounding boxes and what labels it applied.

## 📂 Project Structure

* `find_beers.py` - Main execution script
* `README.md` - Project documentation
* `photo_folder/` - Place your raw images here (JPG/PNG/JPEG)
* `debug_folder/` - Automatically generated outputs with bounding boxes

## 🚀 Quick Start (macOS / Apple Silicon Optimized)

### Prerequisites
Make sure you have Python 3 installed. It is highly recommended to run this project inside a Virtual Environment to avoid system conflicts.

### 1. Setup the Environment
Open your terminal and run:
```bash
python3 -m venv env_beer
source env_beer/bin/activate

2. Install Dependencies

pip install ultralytics opencv-python


3. Prepare your Photos
Create a folder named photo_folder in the same directory as the script and put your images inside.

4. Run the Script
python find_beers.py

The script will automatically download the YOLO-World weights on its first run and process your images. Check the terminal for the final count and the debug_folder for visual results!

🧠 How it works under the hood
YOLO-World is highly sensitive to text prompts. To prevent the AI from hallucinating beers out of similarly shaped objects, the script sets a custom, mixed vocabulary:

["plastic cup of beer", "glass of beer", "pint of beer", "dark beer", "water bottle", "ketchup bottle"]

It allows the model to label water and ketchup (the "distractors"), but the internal Python counting logic completely ignores their indices, ensuring a flawless final count of actual beverages.

Powered by Ultralytics