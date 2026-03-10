#!/usr/bin/env python3
import sys
import os
import re
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# Carica la chiave segreta dal file .env
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

def analizza_singola_foto(percorso_foto):
    if not os.path.exists(percorso_foto):
        print("BEERS_FOUND: 0")
        return

    try:
        client = genai.Client(api_key=API_KEY)
        img = Image.open(percorso_foto).convert("RGB")
        
        # PROMPT DA INVESTIGATORE
        prompt = (
            "Sei un esperto sommelier e giudice di gara. Guarda attentamente questa immagine. "
            "Fai una breve indagine visiva: descrivi cosa vedi. Cerca tavoli, mani, e soprattutto contenitori "
            "(bicchieri, boccali, pinte, bottiglie anche chiuse, lattine di birra). "
            "Cerca dettagli come liquido ambrato o dorato, schiuma, loghi di birra o boccali da pub. "
            "Dopo aver descritto la scena, conta le birre valide. "
            "Infine, nell'ultimissima riga della tua risposta, devi scrivere ESATTAMENTE e SOLO: "
            "'RISULTATO_FINALE: X' (dove X è il numero totale intero di birre trovate, oppure 0)."
        )
        
        configurazione = types.GenerateContentConfig(
            temperature=0.2, 
            safety_settings=[
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
            ]
        )

        # 🚀 ATTIVAZIONE DEL MODELLO
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[img, prompt],
            config=configurazione
        )
        
        testo = response.text.strip()
        
        # Estraiamo il risultato finale
        match = re.search(r'RISULTATO_FINALE:\s*(\d+)', testo)
        if match:
            print(f"BEERS_FOUND: {match.group(1)}")
        else:
            print("BEERS_FOUND: 0")

    except Exception as e:
        # Se c'è un errore (es. rete), restituisce 0 per non far crashare Node.js
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
    else:
        print("BEERS_FOUND: 0")