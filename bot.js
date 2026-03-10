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
const pythonPath = "./env_birre/bin/python";

if (!fs.existsSync(CARTELLA_MEDIA)) fs.mkdirSync(CARTELLA_MEDIA);
const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g;

let isSyncing = false;

// --- FUNZIONE DB CON LOGICA NOTAIO E VIDEO ---
async function inserisciNelDB(dbConnection, d_ora, utente, file, punti, tipo, numeroDichiarato = null) {
    try {
        const row = await dbConnection.get("SELECT valore FROM config WHERE chiave = 'OFFICIAL_TOTAL'");
        const totalePrecedente = parseInt(row.valore || 0);
        
        let incrementoReale = punti;

        // ⚖️ LOGICA NOTAIO: Se l'utente scrive un numero, verifichiamo il salto
        if (numeroDichiarato && tipo === "foto") {
            const saltoRichiesto = numeroDichiarato - totalePrecedente;
            if (saltoRichiesto > 0 && saltoRichiesto <= 10) {
                incrementoReale = saltoRichiesto;
                console.log(`⚖️ Notaio: Accettato salto a ${numeroDichiarato} (AI vedeva ${punti} birre)`);
            }
        }

        const nuovoTotale = totalePrecedente + incrementoReale;

        await dbConnection.run(
            `INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
            [d_ora, utente, file, incrementoReale, tipo]
        );

        await dbConnection.run(`UPDATE config SET valore = ? WHERE chiave = 'OFFICIAL_TOTAL'`, [nuovoTotale]);

        console.log(`🏅 ASSEGNATI: ${incrementoReale} punti a ${utente}! (Nuovo Totale: ${nuovoTotale})`);

        // 🎥 ALLERTA VIDEO OGNI 100
        if (Math.floor(nuovoTotale / 100) > Math.floor(totalePrecedente / 100)) {
            const centinaio = Math.floor(nuovoTotale / 100) * 100;
            console.log(`🚨 TRAGUARDO RAGGIUNTO: ${centinaio}! Mandare messaggio nel gruppo.`);
            // Qui potresti aggiungere: client.sendMessage(chatId, "🚨 VIDEO ALERT: quota " + centinaio);
        }

        if (!isSyncing) {
            isSyncing = true;
            exec('git add 1m_beers.db && git commit -m "🤖 Auto-update" && git pull origin main --rebase && git push', (error) => {
                isSyncing = false;
                if (!error) console.log("🚀 Cloud Sincronizzato!");
            });
        }
    } catch (err) {
        console.log("⚠️ Errore DB:", err.message);
    }
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        executablePath: '/usr/bin/chromium',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));
client.on('ready', () => console.log('✅ Bot Online!'));

const ritardo = ms => new Promise(res => setTimeout(res, ms));

client.on('message_create', async msg => {
    if (!msg || !msg.from) return;

    try {
        const chat = await msg.getChat().catch(() => null);
        if (!chat || (chat.name !== NOME_GRUPPO_BERSAGLIO && chat.name !== CHAT_PERSONALE)) return;

        let testo = msg.body || "";
        const numeriNelTesto = testo.match(/\d{4,6}/g);
        const numeroDichiarato = numeriNelTesto ? parseInt(numeriNelTesto[numeriNelTesto.length - 1]) : null;

        // 🟢 COMANDO RECUPERO STORICO
        if (testo.startsWith("!recupera_storico ")) {
            let limite = parseInt(testo.replace("!recupera_storico ", "").trim()) || 50;
            const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });
            let messaggi = await chat.fetchMessages({ limit: limite });
            messaggi.reverse();

            for (let m of messaggi) {
                if (!m.hasMedia) continue;
                let tipo = m.type === "image" ? "foto" : m.type === "video" ? "video" : null;
                if (!tipo) continue;

                let nome_file = `WA_${m.timestamp}.${tipo === "foto" ? "jpg" : "mp4"}`;
                const esiste = await db.get('SELECT 1 FROM log_birre WHERE nome_file = ?', [nome_file]);
                if (esiste) continue;

                const media = await m.downloadMedia();
                let percorso = `${CARTELLA_MEDIA}/${nome_file}`;
                fs.writeFileSync(percorso, media.data, 'base64');

                // Estrazione numero dal testo del messaggio vecchio
                const mNumeri = (m.body || "").match(/\d{4,6}/g);
                const mNumeroDichiarato = mNumeri ? parseInt(mNumeri[mNumeri.length - 1]) : null;

                if (tipo === "foto") {
                    await ritardo(5000);
                    await new Promise(res => {
                        exec(`${pythonPath} ai_judge.py "${percorso}"`, async (err, stdout) => {
                            const match = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                            let birre = match ? parseInt(match[1]) : 0;
                            if (birre > 0) await inserisciNelDB(db, "Storico", m.from, nome_file, birre, "foto", mNumeroDichiarato);
                            if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                            res();
                        });
                    });
                }
            }
            await db.close();
            return;
        }

        // 🟡 GESTIONE MESSAGGI IN DIRETTA
        if (msg.hasMedia) {
            const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });
            const media = await msg.downloadMedia();
            let tipo = media.mimetype.includes("image") ? "foto" : "video";
            let nome_file = `WA_${msg.timestamp}.${tipo === "foto" ? "jpg" : "mp4"}`;
            let percorso = `${CARTELLA_MEDIA}/${nome_file}`;
            fs.writeFileSync(percorso, media.data, 'base64');

            if (tipo === "foto") {
                exec(`${pythonPath} ai_judge.py "${percorso}"`, async (err, stdout) => {
                    const match = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                    let birre = match ? parseInt(match[1]) : 0;
                    if (birre > 0) await inserisciNelDB(db, "Diretta", msg.from, nome_file, birre, "foto", numeroDichiarato);
                    if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                    await db.close();
                });
            } else {
                if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                await db.close();
            }
        }
    } catch (e) { console.log("🛡️ Errore:", e.message); }
});

client.initialize();