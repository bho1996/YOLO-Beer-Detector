#!/usr/bin/env python3
import sys
import os
import re
import base64
from PIL import Image
from dotenv import load_dotenv

# Librerie Google
from google import genai
from google.genai import types

# Libreria Groq (usa lo standard OpenAI)
from openai import OpenAI

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analizza_singola_foto(percorso_foto):
    if not os.path.exists(percorso_foto):
        print(f"ERRORE: La foto {percorso_foto} non esiste!")
        print("BEERS_FOUND: 0")
        return

    prompt = (
        "Sei un esperto sommelier e giudice di gara molto permissivo. Guarda attentamente questa immagine. "
        "Cerca tavoli, mani, e soprattutto contenitori (bicchieri, boccali, pinte, bottiglie, lattine o bicchieri di plastica). "
        "Sii di manica larga: conta come birra valida anche se il bicchiere è mezzo coperto, la foto è sfocata, "
        "o l'inquadratura taglia il boccale. Se c'è un drink, contalo. "
        "Nell'ultimissima riga della tua risposta scrivi ESATTAMENTE e SOLO: "
        "BEERS_FOUND: X (dove X è il numero totale intero di birre trovate, oppure 0)."
    )

    # ==========================================
    # PIANO A: GOOGLE GEMINI
    # ==========================================
    try:
        client_gemini = genai.Client(api_key=GEMINI_API_KEY)
        img = Image.open(percorso_foto).convert("RGB")
        
        configurazione = types.GenerateContentConfig(
            temperature=0.2, 
            safety_settings=[
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
            ]
        )

        # Usiamo il 2.0-flash o 2.5-flash (quello che preferisci)
        response = client_gemini.models.generate_content(
            model='gemini-2.0-flash', 
            contents=[img, prompt],
            config=configurazione
        )
        
        testo = response.text.strip()
        match = re.search(r'(?:BEERS_FOUND|RISULTATO_FINALE)[*:\s]*(\d+)', testo, re.IGNORECASE)
        
        if match:
            # Stampiamo anche [GEMINI] per farti capire chi ha risposto nei log!
            print(f"[GEMINI] BEERS_FOUND: {match.group(1)}")
            return # Se ha successo, esce dalla funzione e non disturba Groq
        else:
            raise ValueError("Gemini non ha trovato la parola chiave.")

    except Exception as e_gemini:
        # Se siamo qui, Google ci ha dato errore (es. il maledetto 429)
        # Non stampiamo l'errore per non confondere bot.js, ma passiamo al piano B
        pass 


    # ==========================================
    # PIANO B: GROQ (IL SALVAVITA)
    # ==========================================
    try:
        if not GROQ_API_KEY:
            raise ValueError("Chiave Groq non trovata nel file .env")

        client_groq = OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        
        base64_image = encode_image(percorso_foto)
        
        response = client_groq.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            temperature=0.2
        )
        
        testo = response.choices[0].message.content.strip()
        match = re.search(r'(?:BEERS_FOUND|RISULTATO_FINALE)[*:\s]*(\d+)', testo, re.IGNORECASE)
        
        if match:
            print(f"[GROQ] BEERS_FOUND: {match.group(1)}")
        else:
            print(f"DIARIO SEGRETO DI GROQ: {testo}")
            print("BEERS_FOUND: 0")

    except Exception as e_groq:
        # Se falliscono ENTRAMBI (apocalisse zombie), restituisce 0
        print("BEERS_FOUND: 0")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        analizza_singola_foto(sys.argv[1])
    else:
        print("BEERS_FOUND: 0")