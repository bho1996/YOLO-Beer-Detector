#!/usr/bin/env python3
import sys
import os
import google.generativeai as genai
from PIL import Image
import re

# 1. INSERISCI QUI LA CHIAVE CHE HAI PRESO SU AI STUDIO
genai.configure(api_key="AIzaSyBkGr--DtYdXO60FJR9JwBwenxY9rvr7RA")

def analizza_singola_foto(percorso_foto):
    if not os.path.exists(percorso_foto):
        print("BEERS_FOUND: 0")
        return

    try:
        # Carichiamo la foto (operazione leggerissima per la RAM)
        img = Image.open(percorso_foto)
        
        # Usiamo il modello Flash (velocissimo)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Il Prompt per il Giudice
        prompt = (
            "Sei un giudice inflessibile in una gara di birre. "
            "Guarda questa foto e dimmi quante birre vedi. "
            "Conta pinte, boccali, bottiglie di birra o bicchieri contenenti palesemente birra. "
            "Rispondi SOLO con un singolo numero intero (es. 0, 1, 2, 3). Non aggiungere testo."
        )
        
        # Chiamata all'API
        response = model.generate_content([prompt, img])
        testo = response.text.strip()
        
        # Estraiamo il numero per sicurezza (se risponde "Vedo 2 birre" prenderà il "2")
        numeri = re.findall(r'\d+', testo)
        if numeri:
            print(f"BEERS_FOUND: {numeri[0]}")
        else:
            print("BEERS_FOUND: 0")

    except Exception as e:
        print(f"DEBUG: Errore in AI: {e}", file=sys.stderr)
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
    else:
        print("BEERS_FOUND: 0")