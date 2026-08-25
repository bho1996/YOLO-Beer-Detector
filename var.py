import sqlite3
import datetime

# Ci colleghiamo al database
conn = sqlite3.connect('1m_beers.db')
c = conn.cursor()

# Creiamo la data di oggi formattata giusta
oggi = datetime.datetime.now().strftime('%d/%m/%Y, %H:%M:%S')

# Lanciamo la penalità a Frank
c.execute("INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, '+39 *** 2936', 'VAR_PENALTY_MANUAL', -37, 'foto')", (oggi,))

# Aggiorniamo il totale globale
c.execute("UPDATE config SET valore = 23821 WHERE chiave = 'OFFICIAL_TOTAL'")

# Salviamo e chiudiamo
conn.commit()
conn.close()

print("✅ VAR ESEGUITA CON SUCCESSO! Punti tolti e Totale aggiornato a 23821.")
