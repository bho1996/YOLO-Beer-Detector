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

let isSyncing = false; // Il semaforo per Git

client.on('message_create', async msg => {
    try { // <-- IL CUSCINO GLOBALE INIZIA QUI
        
        // Filtro di sicurezza immediato: se è roba strana, ignorala
        if (!msg || !msg.from) return;

        const chat = await msg.getChat();
        
        // Ascolta solo il gruppo bersaglio
        if (chat.name !== NOME_GRUPPO_BERSAGLIO && chat.name !== "Tu") {
            return; 
        }

        // Cuscino interno per il contatto
        let contact;
        try {
            contact = await msg.getContact();
        } catch (err) {
            console.log("👻 Messaggio di sistema o reazione ignorata (nessun mittente valido).");
            return; 
        }

        // Maschera del numero
        let numeroGrezzo = contact.number; 
        let autore = contact.pushname || "Sconosciuto";

        if (numeroGrezzo) {
            let prefisso = "+" + numeroGrezzo.substring(0, 2); 
            let ultime4 = numeroGrezzo.slice(-4); 
            autore = `${prefisso} *** ${ultime4}`;
        }

        let testo = msg.body || "";
        let data_ora = new Date(msg.timestamp * 1000).toLocaleString('it-IT', { 
            day: '2-digit', month: '2-digit', year: '2-digit', 
            hour: '2-digit', minute:'2-digit' 
        });

        // Apriamo il DB
        const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });

        // 1. AGGIORNA IL TOTALE UFFICIALE
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

        // 2. DOWNLOAD MEDIA E AI
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
                    
                    fs.writeFileSync(percorso_file, media.data, 'base64');
                    console.log(`📎 File salvato in ${CARTELLA_MEDIA}: ${nome_file}`);

                    if (tipo_file === "video" && testo.match(regex_numeri_birra)) {
                        await inserisciNelDB(db, data_ora, autore, nome_file, 5, "video");
                    } else if (tipo_file === "foto") {
                        console.log(`🤖 Invio la foto all'Intelligenza Artificiale (YOLO) per l'analisi...`);
                        
                        exec(`python ai_judge.py "${percorso_file}"`, async (error, stdout, stderr) => {
                            let birre_trovate = 0;
                            const ai_risposta = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                            if (ai_risposta) {
                                birre_trovate = parseInt(ai_risposta[1]);
                            }

                            if (birre_trovate > 0) {
                                console.log(`✅ L'AI ha sentenziato: CI SONO ${birre_trovate} BIRRE! 🍺`);
                                await inserisciNelDB(db, data_ora, autore, nome_file, birre_trovate, "foto");
                            } else {
                                console.log(`❌ L'AI ha parlato: FALSO ALLARME (Nessuna birra trovata). Foto ignorata.`);
                            }
                        });
                    }
                }
            }
        } else {
            await db.close(); // Se non c'è media, chiudi subito il DB
        }

        // 3. FUNZIONE DI INSERIMENTO E PUSH AUTOMATICO (CON SEMAFORO)
        async function inserisciNelDB(db, d_ora, utente, file, punti, tipo) {
            try {
                await db.run(
                    `INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
                    [d_ora, utente, file, punti, tipo]
                );
                console.log(`🏅 PUNTI ASSEGNATI: ${utente} ha guadagnato ${punti} punti!`);
                

                if (!isSyncing) {
                    isSyncing = true;
                    console.log("☁️ Sincronizzazione con Streamlit Cloud in corso...");
                    
                    // Ordine corretto: Add -> Commit -> Pull -> Push
                    exec('git add 1m_beers.db && git commit -m "🤖 Auto-update: Nuove birre!" && git pull origin main --rebase && git push', (error, stdout, stderr) => {
                        isSyncing = false; // Ridiventa verde!
                        if (error) {
                            console.log("⚠️ Errore Git intercettato:", error.message);
                            return;
                        }
                        console.log("🚀 BOOM! Classifica online aggiornata con successo!");
                    });
                } else {
                     console.log("⏳ Sincronizzazione già in corso, la classifica verrà aggiornata tra poco!");
                }

            } catch (err) {
                console.log("⚠️ Errore DB o file già presente.");
            } finally {
                await db.close();
            }
        }

    } catch (erroreImprevisto) { // <-- IL CUSCINO GLOBALE SI CHIUDE QUI
        console.log("🛡️ Ops, errore imprevisto intercettato (il bot rimane acceso):", erroreImprevisto.message);
    }
});

client.initialize();