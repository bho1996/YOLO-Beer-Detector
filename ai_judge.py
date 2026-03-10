import sys
import os
from google import genai
from PIL import Image
from dotenv import load_dotenv

print("[DEBUG] 1. Script avviato!")

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
print(f"[DEBUG] 2. API Key trovata? {'SI' if API_KEY else 'NO'}")

percorso_foto = sys.argv[1]
print(f"[DEBUG] 3. Cerco il file: {percorso_foto}")
print(f"[DEBUG] 4. Il file ESISTE DAVVERO? {os.path.exists(percorso_foto)}")

client = genai.Client(api_key=API_KEY)
img = Image.open(percorso_foto).convert("RGB")

print("[DEBUG] 5. Foto aperta. Contatto Gemini...")

prompt = "Guarda questa immagine e conta le birre. Alla fine scrivi ESATTAMENTE 'RISULTATO_FINALE: X'."

response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=[img, prompt]
)

print("[DEBUG] 6. GEMINI HA RISPOSTO!")
print("--- TESTO AI ---")
print(response.text)
print("----------------")