import sqlite3
import re
import os

# --- CONFIGURAZIONI ---
FILE_CHAT = "_chat.txt"
NOME_DB = "1m_beers.db"

# --- REGEX (Le regole del cercatore) ---
regex_inizio_msg = re.compile(r"^(\d{2}/\d{2}/\d{2}, \d{2}:\d{2}) - (.*?): (.*)")
regex_messaggio_sistema = re.compile(r"^(\d{2}/\d{2}/\d{2}, \d{2}:\d{2}) - (.*)")

# Nuova regola universale per i numeri di birra (cerca numeri da 10.000 a 999.999)
regex_numeri_birra = re.compile(r"\b[1-9]\d{4,5}\b")

# Il filtro anti-scherzo per il Totale Ufficiale
regex_totale_globale = re.compile(r"\b\d{5,6}\b")

def maschera_utente(nome_grezzo):
    nome_grezzo = nome_grezzo.strip()
    if nome_grezzo.startswith('+'):
        prefisso = nome_grezzo.split()[0]
        solo_numeri = "".join([c for c in nome_grezzo if c.isdigit()])
        ultime_4 = solo_numeri[-4:] if len(solo_numeri) >= 4 else "XXXX"
        return f"{prefisso} *** {ultime_4}"
    return nome_grezzo

def inizializza_db():
    conn = sqlite3.connect(NOME_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS log_birre (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_ora TEXT,
            utente TEXT,
            nome_file TEXT UNIQUE, 
            punti INTEGER,
            tipo_file TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            chiave TEXT PRIMARY KEY,
            valore INTEGER
        )
    ''')
    conn.commit()
    return conn

def analizza_chat():
    conn = inizializza_db()
    c = conn.cursor()
    
    if not os.path.exists(FILE_CHAT):
        print(f"❌ File {FILE_CHAT} non trovato!")
        return

    print("📖 Inizio lettura della chat e ricerca dei Video Epici...")
    
    messaggio_corrente = ""
    autore_corrente = ""
    data_corrente = ""
    file_allegato = ""
    
    totale_foto_aggiunte = 0
    totale_video_aggiunti = 0
    ultimo_totale_valido = 17500 
    
    # La memoria per ricollegare i video ai messaggi precedenti
    storico_messaggi = []
    
    with open(FILE_CHAT, 'r', encoding='utf-8') as file:
        righe = file.readlines()
        
    righe.append("01/01/99, 00:00 - Finto: Fine")

    for riga in righe:
        match = regex_inizio_msg.match(riga)
        if match:
            if autore_corrente:
                # --- RICERCA DEL TOTALE UFFICIALE ---
                possibili_totali = regex_totale_globale.findall(messaggio_corrente)
                for p in possibili_totali:
                    valore = int(p)
                    if 17500 <= valore <= 30000:
                        ultimo_totale_valido = valore
                
                # Salvataggio in memoria per il contesto dei video
                storico_messaggi.append({'utente': autore_corrente, 'testo': messaggio_corrente})
                if len(storico_messaggi) > 15:
                    storico_messaggi.pop(0)

            if file_allegato:
                punti = 0
                tipo = ""
                
                if file_allegato.endswith(('.jpg', '.jpeg', '.png')):
                    tipo = "foto"
                    numeri_trovati = regex_numeri_birra.findall(messaggio_corrente)
                    punti = len(numeri_trovati) 
                    
                elif file_allegato.endswith('.mp4'):
                    tipo = "video"
                    
                    # Cerca QUALSIASI numero progressivo di birra, non solo quelli con 000
                    ha_fatto_sgolata = regex_numeri_birra.search(messaggio_corrente)
                    
                    if not ha_fatto_sgolata:
                        for msg in storico_messaggi:
                            # Controlla se l'autore ha scritto il numero nel messaggio subito prima
                            if msg['utente'] == autore_corrente and regex_numeri_birra.search(msg['testo']):
                                ha_fatto_sgolata = True
                                msg['testo'] = "" # Cancella la memoria per non dare doppi punti
                                break
                                
                    if ha_fatto_sgolata:
                        punti = 5 
                
                if punti > 0:
                    try:
                        c.execute('''
                            INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (data_corrente, autore_corrente, file_allegato, punti, tipo))
                        
                        if tipo == "foto":
                            totale_foto_aggiunte += 1
                        else:
                            totale_video_aggiunti += 1
                            
                    except sqlite3.IntegrityError:
                        pass
            
            data_corrente = match.group(1)
            autore_corrente = maschera_utente(match.group(2).strip())
            testo_iniziale = match.group(3)
            
            file_allegato = ""
            if "(file allegato)" in testo_iniziale:
                parti = testo_iniziale.split(" (file allegato)")
                file_allegato = parti[0].replace("\u200e", "").strip() 
                messaggio_corrente = parti[1] if len(parti) > 1 else ""
            else:
                messaggio_corrente = testo_iniziale
                
        elif regex_messaggio_sistema.match(riga):
            continue 
            
        else:
            messaggio_corrente += " " + riga.strip()
            
    c.execute("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", (ultimo_totale_valido,))
    conn.commit()
    conn.close()
    
    print("-" * 30)
    print("✅ Aggiornamento Database Completato!")
    print(f"🍺 Foto conteggiate: {totale_foto_aggiunte}")
    print(f"🎬 Video validati (5pt): {totale_video_aggiunti}")
    print(f"🏆 Totale Ufficiale Estratto: {ultimo_totale_valido}")

if __name__ == "__main__":
    analizza_chat()