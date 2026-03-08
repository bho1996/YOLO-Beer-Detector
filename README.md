# 🍺 Custom YOLO Beer Detector

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Ultralytics](https://img.shields.io/badge/Ultralytics-YOLOv8-orange.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-lightgrey.svg)

A custom-trained AI Python script that uses **YOLOv8** to scan a folder of photos and count exactly how many beers are present. 

Initially built using zero-shot detection, this project has been upgraded to a **custom-trained model** (`best.pt`) for maximum accuracy (99.5% mAP50). It flawlessly detects classic glass pints, plastic cups, and dark stouts in custom opaque cups, while naturally ignoring false positives like water bottles and ketchup.

## 🌟 Key Features

* **Custom Trained AI:** Powered by a locally trained YOLOv8-Nano model, perfectly fine-tuned to recognize specific beer cups and glasses.
* **Plug & Play:** Includes the pre-trained `best.pt` weights. No need to download massive models or train from scratch.
* **High Precision:** Achieves near-perfect recall and precision, eliminating the need for complex "distractor" prompt engineering.
* **Visual Debugging:** Automatically generates a `debug_folder` where you can see exactly where the AI drew its bounding boxes.

## 📂 Project Structure

* `find_beers.py` - Main execution script (Inference)
* `train_yolo.py` - Script used for local training (MPS Apple Silicon optimized)
* `best.pt` - The custom-trained AI brain (Weights)
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
```

2. Install Dependencies

```bash
pip install ultralytics opencv-python
```


3. Prepare your Photos
Create a folder named photo_folder in the same directory as the script and put your images inside.

4. Run the Script
 ```bash
python find_beers.py
```

The script will load the custom best.pt model and process your images instantly. Check the terminal for the final count and the debug_folder for visual results!

## 🧠 How it works under the hood
Instead of relying on generic Zero-Shot text prompts (which often confuse beer with similarly shaped transparent water bottles), this model was built via Supervised Fine-Tuning.

Using a proprietary dataset annotated via MakeSense.ai, a YOLOv8-Nano base model was trained over 50 epochs utilizing Apple's Metal Performance Shaders (MPS) hardware acceleration. The resulting best.pt file understands the exact visual features of the target beverages, completely ignoring background noise and party items.

Powered by Ultralytics
