#!/usr/bin/env python3
import sys
import os
from google import genai
from google.genai import types
from PIL import Image
import re

# 1. INSERISCI QUI LA CHIAVE CHE HAI PRESO SU AI STUDIO
genai.configure(api_key="AIzaSyBkGr--DtYdXO60FJR9JwBwenxY9rvr7RA")

client = genai.Client(api_key=API_KEY)

def analizza_singola_foto(percorso_foto):
    if not os.path.exists(percorso_foto):
        print("BEERS_FOUND: 0")
        return

    try:
        img = Image.open(percorso_foto)
        
        prompt = (
            "Sei un giudice inflessibile in una gara di birre. "
            "Guarda questa foto e dimmi quante birre vedi. "
            "Conta pinte, boccali, bottiglie di birra o bicchieri contenenti palesemente birra. "
            "Rispondi SOLO con un singolo numero intero (es. 0, 1, 2, 3). Non aggiungere testo."
        )
        
        # Chiamata API con il nuovo SDK e i filtri disattivati per le foto nei pub
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, prompt],
            config=types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
                ]
            )
        )
        
        testo = response.text.strip()
        print(f"GEMINI_RAW_RESPONSE: {testo}")
        
        numeri = re.findall(r'\d+', testo)
        if numeri:
            print(f"BEERS_FOUND: {numeri[0]}")
        else:
            print("BEERS_FOUND: 0")

    except Exception as e:
        print(f"GEMINI_ERROR: {e}")
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
    else:
        print("BEERS_FOUND: 0")