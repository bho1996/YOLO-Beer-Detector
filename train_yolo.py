from ultralytics import YOLO

print("Inizio la creazione di YOLO-Birra...")

# 1. Carichiamo un modello YOLO "vuoto" e velocissimo (Nano)
model = YOLO('yolov8n.pt') 

# 2. Addestriamo il modello usando i tuoi dati!
# epochs=50: Leggerà i tuoi appunti 50 volte per imparare bene.
# device='mps': Accende l'accelerazione hardware del tuo chip Apple Silicon M3!
risultati = model.train(
    data='./dataset/dataset.yaml', 
    epochs=50, 
    imgsz=640, 
    device='mps'
)

print("Addestramento completato! Il tuo modello è pronto.")