const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { exec } = require('child_process');

// --- CONFIGURAZIONI ---
const NOME_GRUPPO_BERSAGLIO = "I kenioti 🫥"; // <-- Il nome esatto del gruppo
const CHAT_PERSONALE = "+39 339 529 2936"; // <-- Il nome esatto della tua chat per la God Mode
const CARTELLA_MEDIA = "./photo_folder"; 

if (!fs.existsSync(CARTELLA_MEDIA)){
    fs.mkdirSync(CARTELLA_MEDIA);
}

const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g; 
const regex_totale_globale = /\b\d{5,6}\b/g;

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        headless: true, 
        executablePath: '/usr/bin/chromium',
        args: [
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage', 
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process'
        ] 
    }
});

client.on('qr', (qr) => {
    qrcode.generate(qr, {small: true});
});

client.on('ready', () => {
    console.log('✅ Bot connesso e AI caricata! In attesa di birre...');
});

let isSyncing = false; 

client.on('message_create', async msg => {
    
    try { 
        if (!msg || !msg.from) return;

        const chat = await msg.getChat();
        
        // 🛑 IL BUTTAFUORI: Accetta solo il gruppo o te stesso
        if (chat.name !== NOME_GRUPPO_BERSAGLIO && chat.name !== CHAT_PERSONALE) {
            return; // Messaggi di altri ignorati in silenzio
        }

        console.log(`\n📬 [EVENTO] Messaggio AUTORIZZATO da: ${msg.from} | Chat: "${chat.name}" | Tipo: ${msg.type}`);

        let contact;
        try {
            contact = await msg.getContact();
        } catch (err) {
            return; 
        }

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

        // Apriamo il DB SUBITO
        const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });

        // 👑 TRUCCO ADMIN (RECUPERO E GOD MODE)
        if (testo.startsWith("!recupera ")) {
            autore = testo.replace("!recupera ", "").trim();
            console.log(`🛠️ [ADMIN] Modalità recupero attivata! AI al lavoro per: ${autore}`);
            
        } else if (testo.startsWith("!forza ")) {
            let parti = testo.split(" ");
            let punti_forzati = parseInt(parti.pop()); // Prende i punti alla fine
            let stringa_bersaglio = parti.slice(1).join(" "); // Prende quello che sta in mezzo
            
            // 🛡️ Maschera automatica del numero Admin
            let soloNumeri = stringa_bersaglio.replace(/\D/g, ''); // Togli spazi e +
            if (soloNumeri.length >= 10) { 
                let prefisso = "+" + soloNumeri.substring(0, 2); 
                let ultime4 = soloNumeri.slice(-4); 
                autore = `${prefisso} *** ${ultime4}`; 
            } else {
                autore = stringa_bersaglio.trim(); // Se è un nome testuale, lo lascia così
            }

            console.log(`⚡ [GOD MODE] Forzati ${punti_forzati} punti a ${autore}! Salvo e invio a Streamlit...`);
            
            // Salva ISTANTANEAMENTE senza aver bisogno di foto e chiude il DB
            await inserisciNelDB(db, data_ora, autore, "God_Mode_Manuale", punti_forzati, "foto");
            return; // Fine corsa! Non cerca foto e non fa altro.
        }
        // 👑 FINE TRUCCO ADMIN
        
        // 1. AGGIORNA IL TOTALE
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

        // 2. GESTIONE MEDIA E AI
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
                    console.log(`📎 File salvato: ${nome_file}`);

                    if (tipo_file === "video" && testo.match(regex_numeri_birra)) {
                        await inserisciNelDB(db, data_ora, autore, nome_file, 5, "video");
                        fs.unlinkSync(percorso_file);
                        console.log(`🗑️ Pulizia: Video eliminato.`);
                        
                    } else if (tipo_file === "foto") {
                        // Niente più if(salta_ai), qui ci arriva solo se non hai usato !forza
                        console.log(`🤖 Invio la foto all'AI...`);
                        exec(`python ai_judge.py "${percorso_file}"`, async (error, stdout, stderr) => {
                            let birre_trovate = 0;
                            const ai_risposta = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                            if (ai_risposta) {
                                birre_trovate = parseInt(ai_risposta[1]);
                            }

                            if (birre_trovate > 0) {
                                console.log(`✅ AI: CI SONO ${birre_trovate} BIRRE! 🍺`);
                                await inserisciNelDB(db, data_ora, autore, nome_file, birre_trovate, "foto");
                            } else {
                                console.log(`❌ AI: FALSO ALLARME. Zero birre.`);
                            }
                            
                            fs.unlinkSync(percorso_file);
                            console.log(`🗑️ Pulizia RAM: ok.`);
                        });
                    }
                }
            }
        } else {
            await db.close(); 
        }

        // 3. LA FUNZIONE DB 
        async function inserisciNelDB(dbConnection, d_ora, utente, file, punti, tipo) {
            try {
                await dbConnection.run(
                    `INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
                    [d_ora, utente, file, punti, tipo]
                );
                console.log(`🏅 ASSEGNATI: ${punti} punti a ${utente}!`);
                
                if (!isSyncing) {
                    isSyncing = true;
                    console.log("☁️ Sincronizzazione in corso...");
                    exec('git add 1m_beers.db && git commit -m "🤖 Auto-update" && git pull origin main --rebase && git push', (error, stdout, stderr) => {
                        isSyncing = false; 
                        if (error) {
                            console.log("⚠️ Errore Git:", error.message);
                            return;
                        }
                        console.log("🚀 Classifica aggiornata su Cloud!");
                    });
                } else {
                     console.log("⏳ Sincronizzazione già in coda...");
                }
            } catch (err) {
                console.log("⚠️ Errore salvataggio (forse duplicato?).");
            } finally {
                if (dbConnection) {
                    await dbConnection.close();
                }
            }
        }

    } catch (erroreImprevisto) { 
        console.log("🛡️ Errore imprevisto:", erroreImprevisto.message);
    }
});

client.initialize();