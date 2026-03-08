from ultralytics import YOLOWorld
import os
import shutil

print("Caricamento del modello...")
model = YOLOWorld('yolov8s-world.pt')

cartella_foto = "./foto_gruppo" 
cartella_debug = "./foto_debug" 

# Ricreiamo la cartella di debug pulita
if os.path.exists(cartella_debug):
    shutil.rmtree(cartella_debug)
os.makedirs(cartella_debug)

# 1. VOCABOLARIO BILANCIATO
# Torniamo alle basi. Invece di descrivere colore e forma, diamo i concetti chiave.
model.set_classes(["beer", "glass of beer", "plastic cup of beer", "pint of beer"])

contatore_totale_birre = 0

print("Inizio la scansione e il salvataggio delle foto di debug...")

for nome_file in os.listdir(cartella_foto):
    if nome_file.lower().endswith(('.png', '.jpg', '.jpeg')):
        percorso_completo = os.path.join(cartella_foto, nome_file)
        
        # 2. PARAMETRI OTTIMIZZATI:
        # conf=0.18: Una soglia medio-bassa. Lo incoraggia a trovare anche le birre scure nelle "Stack Cup".
        # iou=0.30: Molto aggressivo sui doppioni! Se due riquadri si sovrappongono solo per il 30%, 
        #           ne terrà UNO SOLO.
        # agnostic_nms=True: Unisce i doppioni anche se scambia una bottiglia per un bicchiere.
        risultati = model.predict(
            percorso_completo, 
            conf=0.18,        
            iou=0.30,         
            agnostic_nms=True, 
            verbose=False
        )
        
        birre_in_questa_foto = 0
        
        for risultato in risultati:
            # HO RIMESSO IL SALVATAGGIO! Ora la cartella foto_debug si riempirà di nuovo.
            percorso_salvataggio = os.path.join(cartella_debug, f"debug_{nome_file}")
            risultato.save(filename=percorso_salvataggio)
            
            birre_in_questa_foto += len(risultato.boxes)
            
        print(f"🍺 {birre_in_questa_foto} birre in: {nome_file}")
        contatore_totale_birre += birre_in_questa_foto

print("-" * 30)
print(f"Risultato finale: {contatore_totale_birre} birre totali.")
print("👉 VAI NELLA CARTELLA 'foto_debug' PER VEDERE I NUOVI RIQUADRI!")