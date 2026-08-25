#!/usr/bin/env python3
import sys
import os
import re
import base64
from PIL import Image
from dotenv import load_dotenv

print("🟢 [DEBUG] Script avviato!")

try:
    from google import genai
    from openai import OpenAI
    print("🟢 [DEBUG] Librerie OK!")
except Exception as e:
    print(f"🔴 [FATAL] Manca una libreria: {e}")
    print("BEERS_FOUND: 1")
    sys.exit(1)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "qwen/qwen3.6-27b"      # modello vision attuale di Groq
GEMINI_MODEL = "gemini-2.5-flash"    # solo ripiego: 20 richieste/giorno free


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


# ==========================================
# 1. CONTEGGIO AI (Groq prima, Gemini ripiego)
# ==========================================
def analizza_singola_foto(percorso_foto):
    print(f"🟢 [DEBUG] Analizzo la foto: {percorso_foto}")
    if not os.path.exists(percorso_foto):
        print(f"🔴 [ERRORE] La foto {percorso_foto} non esiste!")
        return 0

    prompt = ("Quante birre (bicchieri, bottiglie, pinte o lattine) vedi in primo piano "
              "o chiaramente intese nella foto? Sii permissivo ma non contare riflessi o oggetti ambigui. "
              "Rispondi SOLO con la dicitura esatta: BEERS_FOUND: X  /no_think")

    # --- PIANO A: GROQ (quota generosa, modalità no-thinking) ---
    print("🟡 [DEBUG] Provo Groq (Qwen 3.6 27B, no-think)...")
    try:
        client_groq = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1", timeout=60.0)
        base64_image = encode_image(percorso_foto)
        messaggi = [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]}]

        try:
            response = client_groq.chat.completions.create(
                model=GROQ_MODEL, messages=messaggi, temperature=0.2,
                max_tokens=60, extra_body={"reasoning_effort": "none"}
            )
        except Exception:
            response = client_groq.chat.completions.create(
                model=GROQ_MODEL, messages=messaggi, temperature=0.2, max_tokens=1024
            )

        testo = response.choices[0].message.content.strip()
        print(f"🟡 [DEBUG] Risposta Groq: {testo[:200]}")
        match = re.search(r'BEERS_FOUND[*:\s]*(\d+)', testo, re.IGNORECASE)
        if match:
            conteggio = int(match.group(1))
            print(f"🤖 [AI] Groq ha contato: {conteggio}")
            return conteggio
        print("🔴 [ERRORE] Groq ha risposto senza parola chiave!")
    except Exception as e_groq:
        print(f"🟡 [DEBUG] Groq ha fallito: {e_groq}")

    # --- PIANO B: GEMINI (ripiego, quota 20/giorno) ---
    print("🔵 [DEBUG] Passo a Gemini...")
    try:
        client_gemini = genai.Client(api_key=GEMINI_API_KEY)
        img = Image.open(percorso_foto).convert("RGB")
        response = client_gemini.models.generate_content(model=GEMINI_MODEL, contents=[img, prompt])
        testo = response.text.strip()
        print(f"🔵 [DEBUG] Risposta Gemini: {testo[:200]}")
        match = re.search(r'BEERS_FOUND[*:\s]*(\d+)', testo, re.IGNORECASE)
        if match:
            conteggio = int(match.group(1))
            print(f"🤖 [AI] Gemini ha contato: {conteggio}")
            return conteggio
    except Exception as e_gemini:
        print(f"🔴 [DEBUG] Anche Gemini ha fallito: {e_gemini}")

    print("🔴 [FATAL] Nessuna AI disponibile.")
    return 0


# ==========================================
# 2. IL NOTAIO (decisione finale sul delta)
# ==========================================
def analizza_intenzione_utente(testo_utente, conteggio_ai, totale_attuale):
    """
    Principio: ogni birra fisica va SEMPRE contata, il totale avanza sempre.
    - Counter dell'utente coerente → fidati dell'utente
    - Counter incoerente (typo) → correggi con le birre fisiche
    - Counter indietro → ignora il numero, aggiungi le birre fisiche
    - Nessun counter → usa l'AI (cappata)
    """
    testo = str(testo_utente)
    numeri = [int(n) for n in re.findall(r'\d+', testo)]

    # Sanità sull'AI: una singola foto non ha realisticamente più di 8 birre
    if conteggio_ai > 8:
        print(f"⚖️ [NOTAIO] AI vede {conteggio_ai} birre (irrealistico). Riduco a 1.")
        conteggio_ai = 1

    birre_fisiche = conteggio_ai if conteggio_ai >= 1 else 1

    if totale_attuale <= 0:
        print(f"⚖️ [NOTAIO] Nessun totale di riferimento. Aggiungo {birre_fisiche}.")
        return birre_fisiche

    # Cerca il totale globale dichiarato dall'utente
    totale_dichiarato = None
    for num in numeri:
        salto = num - totale_attuale
        if -10 <= salto <= 2000:
            if totale_dichiarato is None or num > totale_dichiarato:
                totale_dichiarato = num

    if totale_dichiarato is None:
        print(f"⚖️ [NOTAIO] Nessun totale nel testo. Aggiungo {birre_fisiche} birre fisiche.")
        return birre_fisiche

    salto = totale_dichiarato - totale_attuale

    # CASO 1: counter indietro o uguale → NON scartare, aggiungi le birre fisiche
    if salto <= 0:
        print(f"⚖️ [NOTAIO] Utente scrive {totale_dichiarato} (≤ DB {totale_attuale}). Aggiungo {birre_fisiche} fisiche.")
        return birre_fisiche

    # CASO 2: salto piccolo → fidati dell'utente (anche se l'AI vede di più)
    if salto <= 15:
        print(f"⚖️ [NOTAIO] Salto +{salto} dichiarato dall'utente. Accettato (AI vedeva {conteggio_ai}).")
        return salto

    # CASO 3: salto grande → proporzionale alle birre fisiche, altrimenti è typo
    soglia_typo = (birre_fisiche * 3) + 5
    if salto > soglia_typo:
        print(f"⚖️ [NOTAIO] Salto +{salto} ma AI vede {birre_fisiche} birre (soglia {soglia_typo}). TYPO → aggiungo {birre_fisiche}.")
        return birre_fisiche

    print(f"⚖️ [NOTAIO] Salto +{salto} coerente con {birre_fisiche} birre. Accetto.")
    return salto


# ==========================================
# 3. MOTORE PRINCIPALE
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("BEERS_FOUND: 1")
        sys.exit(1)

    percorso_foto = sys.argv[1]
    totale_attuale = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    testo_utente = sys.argv[3] if len(sys.argv) > 3 else ""

    conteggio_ai = analizza_singola_foto(percorso_foto)
    risultato_finale = analizza_intenzione_utente(testo_utente, conteggio_ai, totale_attuale)

    # Una foto nel gruppo conta sempre almeno 1
    if risultato_finale < 1:
        risultato_finale = 1

    print(f"BEERS_FOUND: {risultato_finale}")