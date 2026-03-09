const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { exec } = require('child_process'); // Il modulo per lanciare Python!

// --- CONFIGURAZIONI ---
const NOME_GRUPPO_BERSAGLIO = "1 million beers 🍻"; // <-- METTI IL TUO GRUPPO QUI
const CARTELLA_MEDIA = "./photo_folder"; // Ora salva direttamente qui

// Creiamo la cartella se non c'è
if (!fs.existsSync(CARTELLA_MEDIA)){
    fs.mkdirSync(CARTELLA_MEDIA);
}

const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g; 
const regex_totale_globale = /\b\d{5,6}\b/g;

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true, args: ['--no-sandbox'] }
});

client.on('qr', (qr) => {
    qrcode.generate(qr, {small: true});
});

client.on('ready', () => {
    console.log('✅ Bot connesso e AI caricata! In attesa di birre...');
});

client.on('message_create', async msg => {
    const chat = await msg.getChat();
    
    if (chat.name !== NOME_GRUPPO_BERSAGLIO && chat.name !== "Tu") {
        return; 
    }

const contact = await msg.getContact();
    
    // Usiamo .number che è robusto e non si rompe mai (restituisce es. "393395292936")
    let numeroGrezzo = contact.number; 
    let autore = contact.pushname || "Sconosciuto";

    // Ricreiamo a mano la maschera "+39 *** 2936"
    if (numeroGrezzo) {
        // Prende le prime 2 cifre per il prefisso (es. "39") e aggiunge il "+"
        let prefisso = "+" + numeroGrezzo.substring(0, 2); 
        // Prende le ultime 4 cifre
        let ultime4 = numeroGrezzo.slice(-4); 
        
        autore = `${prefisso} *** ${ultime4}`;
    }

    let testo = msg.body || "";
    
    let data_ora = new Date(msg.timestamp * 1000).toLocaleString('it-IT', { 
        day: '2-digit', month: '2-digit', year: '2-digit', 
        hour: '2-digit', minute:'2-digit' 
    });

    console.log(`\n[${chat.name}] ${autore}: ${testo}`);

    const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });

    // 1. AGGIORNA IL TOTALE UFFICIALE (Se c'è un numero nel testo)
    let matchTotale = testo.match(regex_totale_globale);
    if (matchTotale) {
        for (let numStr of matchTotale) {
            let valore = parseInt(numStr);
            if (valore >= 17500 && valore <= 30000) {
                await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", valore);
                console.log(`🏆 Totale Ufficiale aggiornato a: ${valore}`);
            }
        }
    }

    // 2. DOWNLOAD E GIUDIZIO DELL'AI
    if (msg.hasMedia) {
        console.log("⏳ Download media in corso...");
        const media = await msg.downloadMedia();
        
        if (media) {
            let tipo_file = "";
            let estensione = "";
            
            if (media.mimetype.includes("image")) {
                tipo_file = "foto";
                estensione = "jpg";
            } else if (media.mimetype.includes("video")) {
                tipo_file = "video";
                estensione = "mp4";
            }

            if (tipo_file !== "") {
                let nome_file = `WA_${msg.timestamp}.${estensione}`;
                let percorso_file = `${CARTELLA_MEDIA}/${nome_file}`;
                
                // Salva il file
                fs.writeFileSync(percorso_file, media.data, 'base64');
                console.log(`📎 File salvato in ${CARTELLA_MEDIA}: ${nome_file}`);

                // --- GESTIONE VIDEO (I video valgono 5 punti a prescindere dall'AI se c'è un numero) ---
                if (tipo_file === "video" && testo.match(regex_numeri_birra)) {
                    await inserisciNelDB(db, data_ora, autore, nome_file, 5, "video");
                } 
                
                // --- GESTIONE FOTO (Passa la palla all'AI!) ---
                else if (tipo_file === "foto") {
                    console.log(`🤖 Invio la foto all'Intelligenza Artificiale (YOLO) per l'analisi...`);
                    
                    // Lancia lo script Python!
                    exec(`python ai_judge.py "${percorso_file}"`, async (error, stdout, stderr) => {
                        let birre_trovate = 0;
                        
                        // Cerca la risposta magica "BEERS_FOUND: X"
                        const ai_risposta = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                        if (ai_risposta) {
                            birre_trovate = parseInt(ai_risposta[1]);
                        }

                        if (birre_trovate > 0) {
                            console.log(`✅ L'AI ha sentenziato: CI SONO ${birre_trovate} BIRRE! 🍺`);
                            // Scrive nel database i punti (1 punto per ogni birra trovata dall'AI)
                            await inserisciNelDB(db, data_ora, autore, nome_file, birre_trovate, "foto");
                        } else {
                            console.log(`❌ L'AI ha parlato: FALSO ALLARME (Nessuna birra trovata). Foto ignorata.`);
                        }
                    });
                }
            }
        }
    } else {
        // Chiudiamo il DB se non c'era nessun media
        await db.close();
    }

    // Funzione helper per non ripetere il codice
// Funzione helper per non ripetere il codice e FARE L'AUTOPUSH
    async function inserisciNelDB(db, d_ora, utente, file, punti, tipo) {
        try {
            await db.run(
                `INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
                [d_ora, utente, file, punti, tipo]
            );
            console.log(`🏅 PUNTI ASSEGNATI: ${utente} ha guadagnato ${punti} punti!`);
            
            // --- IL TOCCO MAGICO: AGGIORNA GITHUB IN AUTOMATICO ---
            console.log("☁️ Sincronizzazione con Streamlit Cloud in corso...");
            exec('git add 1m_beers.db && git commit -m "🤖 Auto-update: Nuova birra registrata!" && git push', (error, stdout, stderr) => {
                if (error) {
                    console.log("⚠️ Punti salvati in locale, ma errore nel caricamento su GitHub:", error.message);
                    return;
                }
                console.log("🚀 BOOM! Classifica online aggiornata con successo!");
            });

        } catch (err) {
            console.log("⚠️ Errore DB o file già presente.");
        } finally {
            await db.close();
        }
    }
});

client.initialize();