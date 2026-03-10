import sys
import os
import logging
from ultralytics import YOLOWorld

logging.getLogger("ultralytics").setLevel(logging.WARNING)

def analizza_singola_foto(percorso_foto):
    if not os.path.exists(percorso_foto):
        print("BEERS_FOUND: 0")
        return

    try:
        model = YOLOWorld('yolov8s-world.pt')
        
        # Parole SECCHE. Dato che è un gruppo di birre, 
        # se c'è una bottiglia o un bicchiere, assumiamo sia birra!
        classes_to_search = [
            "beer", 
            "bottle", 
            "glass",
            "pint",
            "can"
        ]
        model.set_classes(classes_to_search)
        
        # Tutte le classi sopra sono valide (indici da 0 a 4)
        beer_indices = [0, 1, 2, 3, 4]

        results = model.predict(
            percorso_foto, 
            conf=0.10,          # Modalità "manica larghissima"
            iou=0.50,           # FONDAMENTALE: permette birre vicine e sovrapposte
            agnostic_nms=False, # Disattivato per non far scontrare classi diverse
            verbose=False
        )
        
        beers_found = 0
        for box in results[0].boxes:
            detected_class = int(box.cls[0]) 
            if detected_class in beer_indices:
                beers_found += 1
                
        print(f"BEERS_FOUND: {beers_found}")

    except Exception as e:
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        percorso = sys.argv[1]
        analizza_singola_foto(percorso)
    else:
        print("BEERS_FOUND: 0")