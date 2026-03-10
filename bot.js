const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { exec } = require('child_process');

// --- CONFIGURAZIONI ---
const NOME_GRUPPO_BERSAGLIO = "1 million beers 🍻";
const CHAT_PERSONALE = "+39 339 529 2936";
const CARTELLA_MEDIA = "./photo_folder";

if (!fs.existsSync(CARTELLA_MEDIA)) fs.mkdirSync(CARTELLA_MEDIA);
const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g;

// --- VARIABILI DI STATO ---
let isSyncing = false;

// --- FUNZIONE DB UNIVERSALE (Spostata FUORI per stabilità) ---
async function inserisciNelDB(dbConnection, d_ora, utente, file, punti, tipo) {
    try {
        await dbConnection.run(
            `INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
            [d_ora, utente, file, punti, tipo]
        );

        let incrementoReale = (tipo === "video") ? 1 : punti;
        await dbConnection.run(
            `UPDATE config SET valore = valore + ? WHERE chiave = 'OFFICIAL_TOTAL'`,
            [incrementoReale]
        );

        console.log(`🏅 ASSEGNATI: ${punti} punti a ${utente}!`);

        if (!isSyncing) {
            isSyncing = true;
            console.log("☁️ Sincronizzazione Cloud...");
            exec('git add 1m_beers.db && git commit -m "🤖 Auto-update" && git pull origin main --rebase && git push', (error) => {
                isSyncing = false;
                if (error) console.log("⚠️ Errore Git:", error.message);
                else console.log("🚀 Aggiornato su Cloud!");
            });
        }
    } catch (err) {
        console.log("⚠️ Errore scrittura DB:", err.message);
    }
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        executablePath: '/usr/bin/chromium',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));

client.on('ready', () => console.log('✅ Bot Online!'));

client.on('message_create', async msg => {
    try {
        if (!msg || !msg.from) return;
        const chat = await msg.getChat();
        if (chat.name !== NOME_GRUPPO_BERSAGLIO && chat.name !== CHAT_PERSONALE) return;

        let contact = await msg.getContact();
        let numeroGrezzo = contact.number;
        let autore = contact.pushname || "Sconosciuto";
        if (numeroGrezzo) {
            autore = `+${numeroGrezzo.substring(0, 2)} *** ${numeroGrezzo.slice(-4)}`;
        }

        let testo = msg.body || "";
        let data_ora = new Date(msg.timestamp * 1000).toLocaleString('it-IT');

        // 🟢 COMANDO RECUPERO STORICO
        if (testo.startsWith("!recupera_storico ")) {
            let limite = parseInt(testo.replace("!recupera_storico ", "").trim()) || 50;
            console.log(`⏳ Scansione ultimi ${limite} messaggi...`);
            
            const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });
            const messaggi = await chat.fetchMessages({ limit: limite });
            let recuperati = 0;

            for (let m of messaggi) {
                if (!m.hasMedia) continue;
                let tipo_file = m.type === "image" ? "foto" : m.type === "video" ? "video" : null;
                if (!tipo_file) continue;

                let nome_file = `WA_${m.timestamp}.${tipo_file === "foto" ? "jpg" : "mp4"}`;
                
                // Controllo se esiste già
                const esiste = await db.get('SELECT 1 FROM log_birre WHERE nome_file = ?', [nome_file]);
                if (esiste) continue;

                const media = await m.downloadMedia();
                if (!media) continue;

                let percorso = `${CARTELLA_MEDIA}/${nome_file}`;
                fs.writeFileSync(percorso, media.data, 'base64');

                // Dati del vecchio messaggio
                let mContact = await m.getContact();
                let mAutore = `+${mContact.number.substring(0, 2)} *** ${mContact.number.slice(-4)}`;
                let mDataOra = new Date(m.timestamp * 1000).toLocaleString('it-IT');

                if (tipo_file === "foto") {
                    await new Promise(resolve => {
                        exec(`./env_birre/bin/python ai_judge.py "${percorso}"`, async (err, stdout) => {
                            const match = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                            let birre = match ? parseInt(match[1]) : 0;
                            if (birre > 0) {
                                await inserisciNelDB(db, mDataOra, mAutore, nome_file, birre, "foto");
                                recuperati++;
                            }
                            if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                            resolve();
                        });
                    });
                } else if (tipo_file === "video" && m.body.match(regex_numeri_birra)) {
                    await inserisciNelDB(db, mDataOra, mAutore, nome_file, 5, "video");
                    if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                    recuperati++;
                } else {
                    if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                }
            }
            console.log(`🎉 Recupero finito: ${recuperati} birre aggiunte.`);
            await db.close();
            return; // STOP QUI
        }

        // 🟡 GESTIONE MESSAGGI IN DIRETTA
const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });

        if (testo.startsWith("!forza ")) {
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

            console.log(`⚡ [GOD MODE] Forzati ${punti_forzati} punti a ${autore}`);
            let nome_file_finto = `GodMode_${msg.timestamp}.jpg`;
            await inserisciNelDB(db, data_ora, autore, nome_file_finto, punti_forzati, "foto");
            await db.close(); // Fondamentale chiudere qui!
            return;
        }

        if (msg.hasMedia) {
            const media = await msg.downloadMedia();
            let tipo_file = media.mimetype.includes("image") ? "foto" : media.mimetype.includes("video") ? "video" : null;
            if (tipo_file) {
                let nome_file = `WA_${msg.timestamp}.${tipo_file === "foto" ? "jpg" : "mp4"}`;
                let percorso = `${CARTELLA_MEDIA}/${nome_file}`;
                fs.writeFileSync(percorso, media.data, 'base64');

                if (tipo_file === "video" && testo.match(regex_numeri_birra)) {
                    await inserisciNelDB(db, data_ora, autore, nome_file, 5, "video");
                    fs.unlinkSync(percorso);
                } else if (tipo_file === "foto") {
                    exec(`./env_birre/bin/python ai_judge.py "${percorso}"`, async (err, stdout) => {
                        const match = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                        let birre = match ? parseInt(match[1]) : 0;
                        if (birre > 0) {
                            await inserisciNelDB(db, data_ora, autore, nome_file, birre, "foto");
                        }
                        if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                        await db.close();
                    });
                    return; // Usciamo perché la chiusura del DB è asincrona dentro exec
                }
            }
        }
        await db.close();

    } catch (e) {
        console.log("🛡️ Errore:", e.message);
    }
});

client.initialize();