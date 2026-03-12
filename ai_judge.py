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

# ==========================================
# 1. FUNZIONE AI (Ritorna il numero puro)
# ==========================================
def analizza_singola_foto(percorso_foto):
    print(f"🟢 [DEBUG] Analizzo la foto: {percorso_foto}")
    if not os.path.exists(percorso_foto):
        print(f"🔴 [ERRORE] La foto {percorso_foto} non esiste!")
        return 0

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
            conteggio = int(match.group(1))
            print(f"🤖 [AI] Gemini ha contato: {conteggio}")
            return conteggio
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
            conteggio = int(match.group(1))
            print(f"🤖 [AI] Groq ha contato: {conteggio}")
            return conteggio
        else:
            print("🔴 [ERRORE] Groq ha risposto, ma non ha usato la parola chiave!")
            return 0

    except Exception as e_groq:
        print(f"🔴 [FATAL] Anche Groq ha fallito: {e_groq}")
        return 0

# ==========================================
# 2. IL NOTAIO INTELLIGENTE (Intenzione Utente)
# ==========================================
def analizza_intenzione_utente(testo_utente, conteggio_ai, totale_attuale):
    testo = str(testo_utente).lower()
    
    # Trova TUTTI i numeri nel messaggio (es: "19487, 88" -> ['19487', '88'])
    numeri_trovati = re.findall(r'\d+', testo)
    numeri_validi = []
    
    for num_str in numeri_trovati:
        num = int(num_str)
        
        # CASO A: Il numero è scritto per intero (es. 19487)
        if totale_attuale < num <= totale_attuale + 15:
            numeri_validi.append(num)
            
        # CASO B: Il numero è abbreviato (es. scrive "88" per intendere 19488)
        elif 0 < num < 100:
            base_centinaia = (totale_attuale // 100) * 100
            num_ricostruito = base_centinaia + num
            
            # Caso limite: passaggio di centinaia (es. da 19499 a 19501 scrivendo "01")
            if num_ricostruito <= totale_attuale:
                num_ricostruito += 100
                
            if totale_attuale < num_ricostruito <= totale_attuale + 15:
                numeri_validi.append(num_ricostruito)

    # CALCOLO DELL'INTENZIONE
    if numeri_validi:
        massimo_dichiarato = max(numeri_validi)
        salto_umano = massimo_dichiarato - totale_attuale
        
        # Se l'AI vede almeno 1 birra, vince la matematica umana
        if conteggio_ai >= 1:
            print(f"⚖️ [NOTAIO] Trovato max: {massimo_dichiarato}. Salto: +{salto_umano} (Ignoro i {conteggio_ai} dell'AI)")
            return salto_umano

    # FALLBACK: Se non ci sono numeri o l'AI vede 0
    print(f"⚖️ [NOTAIO] Nessun numero valido nel testo o foto senza birre. Mi fido dell'AI: +{conteggio_ai}")
    return conteggio_ai if conteggio_ai > 0 else 1

# ==========================================
# 3. MOTORE PRINCIPALE (Ingresso dati)
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("🔴 [ERRORE] Non hai passato nessuna foto al comando!")
        print("BEERS_FOUND: 0")
        sys.exit(1)

    percorso_foto = sys.argv[1]
    
    # Se il bot NodeJS passa anche il totale e il testo, li raccogliamo.
    # Altrimenti mettiamo valori di default per far funzionare lo script anche da solo.
    totale_attuale = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    testo_utente = sys.argv[3] if len(sys.argv) > 3 else ""

    # 1. Chiediamo all'AI di guardare la foto
    conteggio_ai = analizza_singola_foto(percorso_foto)

    # 2. Passiamo la palla al Notaio
    if totale_attuale > 0 or testo_utente:
        risultato_finale = analizza_intenzione_utente(testo_utente, conteggio_ai, totale_attuale)
    else:
        print("⚖️ [NOTAIO] Testo o totale mancanti dal comando terminale. Uso solo l'AI.")
        risultato_finale = conteggio_ai if conteggio_ai > 0 else 1

    # 3. L'unica stringa che il bot NodeJS deve leggere per assegnare i punti
    print(f"BEERS_FOUND: {risultato_finale}")