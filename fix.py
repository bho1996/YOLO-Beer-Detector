node -e "
const sqlite3 = require('sqlite3').verbose();
const db = new sqlite3.Database('./1m_beers.db');

db.serialize(() => {
  // Flush del WAL per essere certi di leggere dati aggiornati
  db.run('PRAGMA wal_checkpoint(TRUNCATE)', (err) => {
    if(err) console.error('Checkpoint error:', err.message);
    else console.log('✅ Checkpoint completato\n');
  });

  // Legge il valore 'OFFICIAL_TOTAL' dalla tabella config
  db.get(\"SELECT valore FROM config WHERE chiave = 'OFFICIAL_TOTAL'\", (err, row) => {
    if (err) console.error('Errore lettura config:', err.message);
    else if (row) console.log('🏆 Totale Ufficiale nel DB:', row.valore);
    else console.log('❌ Chiave OFFICIAL_TOTAL non trovata!');
  });

  // Somma di tutti i punti nella tabella log_birre
  db.get('SELECT SUM(punti) as totale_punti FROM log_birre', (err, row) => {
    if (err) console.error('Errore somma punti:', err.message);
    else if (row) console.log('🧮 Somma dei punti registrati:', row.totale_punti);
  });

  // Conta il numero di righe
  db.get('SELECT COUNT(*) as conteggio FROM log_birre', (err, row) => {
    if (err) console.error('Errore conteggio:', err.message);
    else if (row) console.log('📊 Numero di rilevazioni (foto/video):', row.conteggio);
  });
});

setTimeout(() => db.close(), 2000);
"
