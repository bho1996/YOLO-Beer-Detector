#!/usr/bin/env python3
import sys
import os
from ultralytics import YOLO
import logging
logging.getLogger("ultralytics").setLevel(logging.WARNING)

def analizza_singola_foto(percorso_foto):
    if not os.path.exists(percorso_foto):
        print("BEERS_FOUND: 0")
        return

    try:
        # Carica il modello YOLOv8n (viene scaricato automaticamente la prima volta)
        model = YOLO('yolov8n.pt')
        
        # Inferenza con parametri ottimizzati per Raspberry Pi
        results = model.predict(
            percorso_foto,
            imgsz=320,           # risoluzione ridotta per velocità
            conf=0.15,           # soglia di confidenza (regola se necessario)
            iou=0.5,
            verbose=False
        )
        
        # Classi COCO di interesse: 39=bottle, 40=wine glass, 41=cup
        beer_classes = [39, 40, 41]
        beers_found = 0
        
        # Conta gli oggetti rilevati
        for box in results[0].boxes:
            cls = int(box.cls[0])
            if cls in beer_classes:
                beers_found += 1
        
        print(f"BEERS_FOUND: {beers_found}")
        
        # Debug opzionale (commenta in produzione)
        # print(f"DEBUG: {len(results[0].boxes)} boxes trovate", file=sys.stderr)

    except Exception as e:
        print(f"DEBUG: Errore in AI: {e}", file=sys.stderr)
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
    else:
        print("BEERS_FOUND: 0")