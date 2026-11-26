#!/usr/bin/env python3
import base64
import io
import json
import os
import re
import sys

from PIL import Image
from dotenv import load_dotenv

print("🟢 [DEBUG] Script avviato!")

try:
    from google import genai
    from openai import OpenAI
    print("🟢 [DEBUG] Librerie OK!")
except Exception as e:
    print(f"🔴 [FATAL] Manca una libreria: {e}")
    print("BEERS_FOUND: -1")
    sys.exit(1)

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

IMAGE_MAX_SIDE = 448
IMAGE_JPEG_QUALITY = 80

GROQ_MODEL = "qwen/qwen3.8-27b"  # modello vision attuale di Groq

# Google AI Studio: modelli multimodali gratuiti con bucket di quota indipendenti.
GEMINI_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
)
GEMINI_MODEL = GEMINI_MODELS[0]

# OpenRouter: solo modelli vision gratuiti (:free), mai router casuali o modelli a pagamento.
OPENROUTER_MODELS = (
    "nvidia/nemotron-3.5-super-vl:free",
    "inclusionai/ling-3.2-flash:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
)
OPENROUTER_MODEL = OPENROUTER_MODELS[0]


def load_resized_image(image_path, max_side=IMAGE_MAX_SIDE):
    img = Image.open(image_path).convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def encode_image(image_path, max_side=IMAGE_MAX_SIDE, quality=IMAGE_JPEG_QUALITY):
    """Ridimensiona la foto a max_side px lato lungo per ridurre i token vision di ~3-4x."""
    try:
        img = load_resized_image(image_path, max_side=max_side)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")


def estrai_verdetto_binario(testo):
    if not testo:
        return None
    matches = re.findall(r"BEERS_FOUND[*:\s]*([01])\b", testo, re.IGNORECASE)
    if matches:
        return int(matches[-1])
    return None


def analizza_google_ai(percorso_foto, prompt):
    if not GEMINI_API_KEY:
        print("🔵 [DEBUG] Google AI Studio non configurato: manca GEMINI_API_KEY.")
        return -1
    clean_prompt = prompt.replace("/no_think", "").strip()
    try:
        img = load_resized_image(percorso_foto)
        client_gemini = genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 15000})
    except Exception as error:
        print(f"🔴 [DEBUG] Inizializzazione Google AI fallita: {error}")
        return -1

    for model_name in GEMINI_MODELS:
        print(f"🔵 [DEBUG] Provo Google AI ({model_name})...")
        try:
            response = client_gemini.models.generate_content(
                model=model_name,
                contents=[img, clean_prompt],
            )
            testo = (getattr(response, "text", None) or "").strip()
            print(f"🔵 [DEBUG] Risposta {model_name}: {testo[:200]}")
            valore = estrai_verdetto_binario(testo)
            if valore is not None:
                print(f"🤖 [AI] Google AI ({model_name}) ha contato: {valore}")
                return valore
            print(f"🔵 [DEBUG] {model_name} senza verdetto binario valido.")
        except Exception as error:
            msg = str(error)
            if GEMINI_API_KEY:
                msg = msg.replace(GEMINI_API_KEY, "[CHIAVE OSCURATA]")
            print(f"🔵 [DEBUG] {model_name} ha fallito: {msg[:300]}")
    return -1


def analizza_openrouter(percorso_foto, prompt):
    if not OPENROUTER_API_KEY:
        print("🟣 [DEBUG] OpenRouter non configurato: manca OPENROUTER_API_KEY.")
        return -1

    clean_prompt = prompt.replace("/no_think", "").strip()
    b64 = encode_image(percorso_foto)

    for model_name in OPENROUTER_MODELS:
        if not model_name.endswith(":free"):
            continue
        print(f"🟣 [DEBUG] Provo OpenRouter ({model_name}, gratuito)...")
        try:
            with OpenAI(
                api_key=OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                timeout=20.0,
                max_retries=0,
            ) as client:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": clean_prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}"
                        }},
                    ]}],
                    temperature=0.2,
                    max_tokens=1536,
                )
            choices = getattr(response, "choices", None)
            first = choices[0] if choices else None
            message = getattr(first, "message", None)
            api_error = getattr(response, "error", None)
            details = {
                "model": getattr(response, "model", None),
                "error": api_error,
                "choices_count": len(choices) if choices is not None else None,
                "finish_reason": getattr(first, "finish_reason", None),
                "usage": getattr(response, "usage", None),
            }
            if api_error or not choices or message is None:
                diagnostic = json.dumps(details, ensure_ascii=False, default=str)
                diagnostic = diagnostic.replace(OPENROUTER_API_KEY, "[CHIAVE OSCURATA]")
                print(f"🟣 [DEBUG] Dettagli errore OpenRouter ({model_name}): {diagnostic[:1200]}")
                continue
            testo = getattr(message, "content", None) or ""
            print(f"🟣 [DEBUG] Modello OpenRouter: {getattr(response, 'model', model_name)}")
            print(f"🟣 [DEBUG] Risposta OpenRouter: {testo[:200]}")
            valore = estrai_verdetto_binario(testo)
            if valore is not None:
                print(f"🤖 [AI] OpenRouter ({model_name}) ha contato: {valore}")
                return valore
            diagnostic = json.dumps(details, ensure_ascii=False, default=str)
            diagnostic = diagnostic.replace(OPENROUTER_API_KEY, "[CHIAVE OSCURATA]")
            print(f"🟣 [DEBUG] Risposta senza verdetto binario ({model_name}): {diagnostic[:1200]}")
        except Exception as error:
            msg = str(error).replace(OPENROUTER_API_KEY, "[CHIAVE OSCURATA]")
            print(f"🟣 [DEBUG] OpenRouter ({model_name}) ha fallito: {msg[:300]}")
    return -1


# ==========================================
# 1. CONTEGGIO AI (Groq -> Google AI -> OpenRouter free)
# ==========================================
def analizza_singola_foto(percorso_foto):
    print(f"🟢 [DEBUG] Analizzo la foto: {percorso_foto}")
    if not os.path.exists(percorso_foto):
        print(f"🔴 [ERRORE] La foto {percorso_foto} non esiste!")
        return -1

    prompt = ("In questa foto c'è almeno un oggetto che è o potrebbe aver contenuto una birra "
              "(bicchiere, bottiglia, pinta, lattina, boccale)? "
              "Anche vuoto o mezzo pieno conta. Non contare riflessi o oggetti ambigui. "
              "Rispondi SOLO con la dicitura esatta: BEERS_FOUND: 1  (se sì)  oppure  BEERS_FOUND: 0  (se no) "
              "/no_think")

    if "--openrouter-only" in sys.argv:
        return analizza_openrouter(percorso_foto, prompt)
    if "--gemini-only" in sys.argv:
        return analizza_google_ai(percorso_foto, prompt)

    # --- PIANO A: GROQ (immagine 512px, modalità no-thinking) ---
    if GROQ_API_KEY:
        print("🟡 [DEBUG] Provo Groq (Qwen 3.8 27B, 512px, no-think)...")
        try:
            client_groq = OpenAI(
                api_key=GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                timeout=25.0,
                max_retries=0,
            )
            base64_image = encode_image(percorso_foto)
            messaggi = [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
            ]}]

            try:
                response = client_groq.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messaggi,
                    temperature=0.2,
                    max_tokens=60,
                    extra_body={"reasoning_effort": "none"},
                )
            except Exception as error:
                if getattr(error, "status_code", None) != 400:
                    raise
                response = client_groq.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messaggi,
                    temperature=0.2,
                    max_tokens=1024,
                )

            testo = (response.choices[0].message.content or "").strip()
            print(f"🟡 [DEBUG] Risposta Groq: {testo[:200]}")
            valore = estrai_verdetto_binario(testo)
            if valore is not None:
                print(f"🤖 [AI] Groq ha contato: {valore}")
                return valore
            print("🔴 [ERRORE] Groq ha risposto senza parola chiave!")
        except Exception as e_groq:
            msg = str(e_groq).replace(GROQ_API_KEY, "[CHIAVE OSCURATA]")
            print(f"🟡 [DEBUG] Groq ha fallito: {msg[:300]}")

    # --- PIANO B: GOOGLE AI STUDIO (Gemma 4 + Gemini Flash Lite + Gemini Flash) ---
    valore = analizza_google_ai(percorso_foto, prompt)
    if valore >= 0:
        return valore

    # --- PIANO C: OPENROUTER (solo modelli vision :free) ---
    valore = analizza_openrouter(percorso_foto, prompt)
    if valore >= 0:
        return valore

    print("🔴 [FATAL] Nessuna AI disponibile.")
    return -1


# ==========================================
# 2. IL NOTAIO (decisione finale sul delta)
# ==========================================
def analizza_intenzione_utente(testo_utente, conteggio_ai, totale_attuale):
    """
    Logica semplificata per il sistema "a gettoni":
    - L'utente dichiara un totale globale nel testo -> il delta è il salto (se ragionevole)
    - L'utente NON dichiara nulla -> 1 punto se l'AI ha visto una birra, 0 altrimenti
    """
    testo = str(testo_utente)
    numeri = [int(n) for n in re.findall(r"\d+", testo)]

    birre_fisiche = 1 if conteggio_ai >= 1 else 0

    if totale_attuale <= 0:
        print(f"⚖️ [NOTAIO] Nessun totale di riferimento. Aggiungo {birre_fisiche}.")
        return birre_fisiche

    totale_dichiarato = None
    for num in numeri:
        salto = num - totale_attuale
        if -10 <= salto <= 2000:
            if totale_dichiarato is None or num > totale_dichiarato:
                totale_dichiarato = num

    if totale_dichiarato is None:
        print(f"⚖️ [NOTAIO] Nessun totale nel testo. AI ha visto birra? {'Sì' if birre_fisiche else 'No'} → {birre_fisiche} punto/i.")
        return birre_fisiche

    salto = totale_dichiarato - totale_attuale

    if salto <= 0:
        print(f"⚖️ [NOTAIO] Utente scrive {totale_dichiarato} (≤ DB {totale_attuale}). Ignoro, uso gettone AI: {birre_fisiche}.")
        return birre_fisiche

    if salto <= 2000:
        print(f"⚖️ [NOTAIO] Salto +{salto} dichiarato dall'utente. Accettato.")
        return salto

    print(f"⚖️ [NOTAIO] Salto +{salto} irrealistico (probabile typo). Uso gettone AI: {birre_fisiche}.")
    return birre_fisiche


# ==========================================
# 3. MOTORE PRINCIPALE
# ==========================================
if __name__ == "__main__":
    flags = {"--openrouter-only", "--gemini-only"}
    args = [arg for arg in sys.argv[1:] if arg not in flags]
    if not args:
        print("🔴 [FATAL] Uso: ai_judge.py FOTO [TOTALE] [TESTO] [--openrouter-only|--gemini-only]")
        print("BEERS_FOUND: -1")
        sys.exit(1)

    percorso_foto = args[0]
    totale_attuale = int(args[1]) if len(args) > 1 else 0
    testo_utente = args[2] if len(args) > 2 else ""

    conteggio_ai = analizza_singola_foto(percorso_foto)
    if conteggio_ai < 0:
        print("🔴 [FATAL] Analisi non completata: foto da riprovare.")
        print("BEERS_FOUND: -1")
        sys.exit(1)
    risultato_finale = analizza_intenzione_utente(testo_utente, conteggio_ai, totale_attuale)
    print(f"BEERS_FOUND: {risultato_finale}")
