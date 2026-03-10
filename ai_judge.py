#!/usr/bin/env python3
import sys
import os
from google import genai
from google.genai import types
from PIL import Image
import re
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") 
client = genai.Client(api_key=API_KEY)

def analizza_singola_foto(percorso_foto):
    if not os.path.exists(percorso_foto):
        print("BEERS_FOUND: 0")
        return

    try:
        img = Image.open(percorso_foto).convert("RGB")
        
        # PROMPT DA INVESTIGATORE (Sfruttiamo l'intelligenza del PRO)
        prompt = (
            "Sei un esperto sommelier e giudice di gara. Guarda attentamente questa immagine. "
            "Fai una breve indagine visiva: descrivi cosa vedi. Cerca tavoli, mani, e soprattutto contenitori "
            "(bicchieri, boccali, pinte, bottiglie anche chiuse, lattine di birra). "
            "Cerca dettagli come liquido ambrato o dorato, schiuma, loghi di birra o boccali da pub. "
            "Dopo aver descritto la scena, conta le birre. "
            "Infine, nell'ultimissima riga della tua risposta, devi scrivere ESATTAMENTE e SOLO: "
            "'RISULTATO_FINALE: X' (dove X è il numero totale intero di birre trovate, oppure 0)."
        )
        
        configurazione = types.GenerateContentConfig(
            temperature=0.2, # Molto analitico e poco fantasioso
            safety_settings=[
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
            ]
        )

        # 🚀 ATTIVAZIONE DEL MODELLO PRO

        response = client.models.generate_content(
            model='gemini-2.5-flash',
response = client.models.generate_content(
            model='gemini-2.5-pro', # <-- Usa 2.5-pro o 2.5-flash

            contents=[img, prompt],
            config=configurazione
        )
        
        testo = response.text.strip()
        
        # Stampiamo il ragionamento dell'AI, utile se vogliamo fare debug dal terminale
        print(f"DEBUG_PENSIERO_AI:\n{testo}")
        
        # Estraiamo il risultato finale in modo chirurgico
        match = re.search(r'RISULTATO_FINALE:\s*(\d+)', testo)
        if match:
            print(f"BEERS_FOUND: {match.group(1)}")
        else:
            print("BEERS_FOUND: 0")

    except Exception as e:
        print(f"GEMINI_ERROR: {e}")
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
