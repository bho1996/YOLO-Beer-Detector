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
        # UPGRADE: Passiamo dal modello "nano" al modello "small" (s)
        # È molto più preciso con le foto compresse da WhatsApp!
        model = YOLO('yolov8s.pt') 
        
        # Inferenza con "Raggi X" attivati
        results = model.predict(
            percorso_foto,
            imgsz=640,           
            conf=0.15,           # Soglia di confidenza bassa per catturare più oggetti
            iou=0.4,             # Evita di contare due volte la stessa birra se i quadrati si sovrappongono
            verbose=False,
            save=True,           # <-- MAGIA! Salva l'immagine analizzata
            project="debug_ai",  # Crea una cartella chiamata "debug_ai"
            name="viste",        # Dentro ci saranno le foto con i riquadri
            exist_ok=True
        )
        
        # Classi COCO: 39=bottiglia, 40=bicchiere di vino (spesso confuso con pinta), 41=tazza/boccale
        beer_classes = [39, 40, 41]
        beers_found = 0
        
        # Conta gli oggetti rilevati
        for box in results[0].boxes:
            cls = int(box.cls[0])
            if cls in beer_classes:
                beers_found += 1
        
        print(f"BEERS_FOUND: {beers_found}")

    except Exception as e:
        print(f"DEBUG: Errore in AI: {e}", file=sys.stderr)
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
    else:
        print("BEERS_FOUND: 0")