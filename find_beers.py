from ultralytics import YOLO
import os
import shutil

print("Caricamento del modello personalizzato YOLO-Birra...")
# Carichiamo il TUO modello, non più quello generico!
model = YOLO('best.pt')

photo_folder = "./photo_folder" 
debug_folder = "./debug_folder" 

if os.path.exists(debug_folder):
    shutil.rmtree(debug_folder)
os.makedirs(debug_folder)

total_beer_count = 0

print("Inizio la scansione infallibile...")

for filename in os.listdir(photo_folder):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        full_path = os.path.join(photo_folder, filename)
        
        # Facciamo l'analisi. 
        # conf=0.50: Ora che è super preciso, esigiamo una sicurezza del 50%!
        results = model.predict(
            full_path, 
            conf=0.50,        
            verbose=False
        )
        
        # Salva la foto per vedere i risultati
        save_path = os.path.join(debug_folder, f"debug_{filename}")
        results[0].save(filename=save_path)
        
        # Conta gli oggetti trovati (sono per forza birre, l'AI conosce solo quelle!)
        beers_in_this_photo = len(results[0].boxes)
                
        print(f"🍺 {beers_in_this_photo} birre trovate in: {filename}")
        total_beer_count += beers_in_this_photo

print("-" * 30)
print(f"Risultato finale: {total_beer_count} birre totali.")