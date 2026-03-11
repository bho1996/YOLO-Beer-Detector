#!/usr/bin/env python3
import sys
import os
import re
import base64
from PIL import Image
from dotenv import load_dotenv

print("🟢 [DEBUG] Lo script è partito correttamente!")

try:
    from google import genai
    from google.genai import types
    from openai import OpenAI
    print("🟢 [DEBUG] Tutte le librerie sono installate!")
except Exception as e:
    print(f"🔴 [FATAL] Manca una libreria: {e}")
    sys.exit(1)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("🔴 [FATAL] La chiave GROQ_API_KEY non è stata trovata nel file .env!")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analizza_singola_foto(percorso_foto):
    print(f"🟢 [DEBUG] Analizzo la foto: {percorso_foto}")
    if not os.path.exists(percorso_foto):
        print(f"🔴 [ERRORE] La foto {percorso_foto} non esiste!")
        print("BEERS_FOUND: 0")
        return

    prompt = "Quante birre (bicchieri, bottiglie, pinte o lattine) vedi? Sii permissivo. Rispondi SOLO con la dicitura esatta: BEERS_FOUND: X"

    print("🟡 [DEBUG] Provo a contattare Google Gemini...")
    try:
        client_gemini = genai.Client(api_key=GEMINI_API_KEY)
        img = Image.open(percorso_foto).convert("RGB")
        response = client_gemini.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[img, prompt]
        )
        testo = response.text.strip()
        print(f"🟡 [DEBUG] Risposta grezza di Google: {testo}")
        match = re.search(r'(?:BEERS_FOUND|RISULTATO_FINALE)[*:\s]*(\d+)', testo, re.IGNORECASE)
        if match:
            print(f"[GEMINI] BEERS_FOUND: {match.group(1)}")
            return
    except Exception as e_gemini:
        print(f"🟡 [DEBUG] Google ha fallito o ti ha bloccato: {e_gemini}")

    print("🔵 [DEBUG] Passo al Piano B: Contatto Groq (Llama 4 Scout)...")
    try:
        client_groq = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        base64_image = encode_image(percorso_foto)
        response = client_groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            temperature=0.2
        )
        testo = response.choices[0].message.content.strip()
        print(f"🔵 [DEBUG] Risposta grezza di Groq: {testo}")
        match = re.search(r'(?:BEERS_FOUND|RISULTATO_FINALE)[*:\s]*(\d+)', testo, re.IGNORECASE)
        
        if match:
            print(f"[GROQ] BEERS_FOUND: {match.group(1)}")
        else:
            print("🔴 [ERRORE] Groq ha risposto, ma non ha usato la parola chiave!")
            print("BEERS_FOUND: 0")

    except Exception as e_groq:
        print(f"🔴 [FATAL] Anche Groq ha fallito: {e_groq}")
        print("BEERS_FOUND: 0")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
    else:
        print("🔴 [ERRORE] Non hai passato nessuna foto al comando!")
        print("BEERS_FOUND: 0")
