const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { exec } = require('child_process');

// --- CONFIGURAZIONI ---
const NOME_GRUPPO_BERSAGLIO = "1 million beers 🍻"; // <-- Il nome esatto del gruppo
const CHAT_PERSONALE = "+39 339 529 2936"; // <-- Il nome esatto della tua chat per la God Mode
const CARTELLA_MEDIA = "./photo_folder"; 

if (!fs.existsSync(CARTELLA_MEDIA)){
    fs.mkdirSync(CARTELLA_MEDIA);
}

const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g; 

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
    setInterval(() => {
    console.log("⏱️ Bot ancora attivo, in attesa di messaggi...");
}, 30000);
setInterval(async () => {
    try {
        const state = await client.getState();
        console.log(`📡 Stato connessione: ${state}`);
    } catch (e) {
        console.log(`📡 Errore nel recuperare stato: ${e.message}`);
    }
}, 60000);
});

client.on('disconnected', (reason) => {
    console.log('🔴 ATTENZIONE! Bot disconnesso da WhatsApp! Motivo:', reason);
    console.log('🔄 Riavvio forzato in corso...');
    process.exit(1); // Questo uccide il bot, utilissimo se in futuro useremo un gestore che lo riaccende in automatico
});

let isSyncing = false; 

client.on('message_create', async msg => {
    console.log(`🔥 EVENTO SCATTATO - Da: ${msg.from} - Corpo: ${msg.body.substring(0, 30)}`);
    
    try { 
        if (!msg || !msg.from) return;

        const chat = await msg.getChat();
        
        // 🛑 IL BUTTAFUORI
        if (chat.name !== NOME_GRUPPO_BERSAGLIO && chat.name !== CHAT_PERSONALE) {
            return; 
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

        // Apriamo il DB
        const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });

        // 👑 TRUCCO ADMIN (RECUPERO E GOD MODE)
        if (testo.startsWith("!recupera ")) {
            autore = testo.replace("!recupera ", "").trim();
            console.log(`🛠️ [ADMIN] Modalità recupero attivata! AI al lavoro per: ${autore}`);
            
        } else if (testo.startsWith("!forza ")) {
            let parti = testo.split(" ");
            let punti_forzati = parseInt(parti.pop()); 
            let stringa_bersaglio = parti.slice(1).join(" "); 
            
            let soloNumeri = stringa_bersaglio.replace(/\D/g, ''); 
            if (soloNumeri.length >= 10) { 
                let prefisso = "+" + soloNumeri.substring(0, 2); 
                let ultime4 = soloNumeri.slice(-4); 
                autore = `${prefisso} *** ${ultime4}`; 
            } else {
                autore = stringa_bersaglio.trim(); 
            }

            console.log(`⚡ [GOD MODE] Forzati ${punti_forzati} punti a ${autore}! Salvo e invio a Streamlit...`);
            
            let nome_file_finto = `GodMode_${msg.timestamp}.jpg`;
            await inserisciNelDB(db, data_ora, autore, nome_file_finto, punti_forzati, "foto");
            return; 
        }
        
        // 📸 GESTIONE MEDIA E AI
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

        // 🧮 LA FUNZIONE DB (Contabile Universale)
        async function inserisciNelDB(dbConnection, d_ora, utente, file, punti, tipo) {
            try {
                await dbConnection.run(
                    `INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
                    [d_ora, utente, file, punti, tipo]
                );
                
                await dbConnection.run(
                    `UPDATE config SET valore = valore + ? WHERE chiave = 'OFFICIAL_TOTAL'`,
                    [punti]
                );

                console.log(`🏅 ASSEGNATI: ${punti} punti a ${utente}! Il Totale Globale è salito!`);
                
                if (!isSyncing) {
                    isSyncing = true;
                    console.log("☁️ Sincronizzazione in corso...");
                    exec('git add 1m_beers.db && git commit -m "🤖 Auto-update: Punti e Totale aggiornati" && git pull origin main --rebase && git push', (error, stdout, stderr) => {
                        isSyncing = false; 
                        if (error) {
                            console.log("⚠️ Errore Git:", error.message);
                            return;
                        }
                        console.log("🚀 Classifica e Totale aggiornati su Cloud!");
                    });
                } else {
                     console.log("⏳ Sincronizzazione già in coda...");
                }
            } catch (err) {
                console.log("⚠️ Errore DB intercettato:", err.message);
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