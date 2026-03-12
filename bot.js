const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { exec } = require('child_process');

// --- CONFIGURAZIONI ---
const ID_GRUPPO = "120363420647117056@g.us";
const ID_PERSONALE = "393395292936@c.us"; 
const CARTELLA_MEDIA = "./photo_folder";
const pythonPath = "./env_birre/bin/python";

if (!fs.existsSync(CARTELLA_MEDIA)) fs.mkdirSync(CARTELLA_MEDIA);
const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g;

let isSyncing = false;
const ritardo = ms => new Promise(res => setTimeout(res, ms));

// --- FUNZIONE DB (Pulita, senza il vecchio Notaio) ---
async function inserisciNelDB(dbConnection, d_ora, utente, file, punti, tipo) {
    try {
        const row = await dbConnection.get("SELECT valore FROM config WHERE chiave = 'OFFICIAL_TOTAL'");
        const totalePrecedente = parseInt(row.valore || 0);
        
        // I punti che arrivano qui sono già quelli definitivi decisi dal Python!
        let incrementoReale = (tipo === "video") ? 1 : punti;
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
            console.log(`🚨 TRAGUARDO 100 RAGGIUNTO: ${centinaio}!`);
        }

        if (!isSyncing) {
            isSyncing = true;
            console.log("☁️ Sincronizzazione Cloud...");
            exec('git add 1m_beers.db && git commit -m "🤖 Auto-update DB" && git pull origin main --rebase && git push', (error) => {
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
client.on('ready', () => console.log('✅ Bot Online e in Ascolto!'));

client.on('message_create', async msg => {
    try {
        if (!msg || !msg.from) return;
        const chat = await msg.getChat().catch(() => null);
        
        if (chat) {
            console.log(`[DEBUG] Messaggio in arrivo da chat: '${chat.name}' (ID: ${msg.from})`);
        }

        // FILTRO DI INGRESSO
        if (!chat || (msg.from !== ID_GRUPPO && msg.from !== ID_PERSONALE)) return;

        let contact = await msg.getContact().catch(() => null);
        let autore = "Sconosciuto";
        if (contact && contact.number) {
            autore = `+${contact.number.substring(0, 2)} *** ${contact.number.slice(-4)}`;
        }

        let testo = msg.body || "";
        let data_ora = new Date(msg.timestamp * 1000).toLocaleString('it-IT');

        // 🟢 COMANDO RECUPERO STORICO
        if (testo.startsWith("!recupera_storico ")) {
            let limite = parseInt(testo.replace("!recupera_storico ", "").trim()) || 50;
            console.log(`\n⏳ [RECUPERO] Scansione ultimi ${limite} messaggi DEL GRUPPO...`);
            
            const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });
            const chatGruppo = await client.getChatById(ID_GRUPPO).catch(() => null);
            if (!chatGruppo) {
                console.log("❌ Errore: non riesco a trovare il gruppo in memoria!");
                await db.close();
                return;
            }

            let messaggi = await chatGruppo.fetchMessages({ limit: limite }).catch(() => []);
            messaggi.reverse();
            let recuperati = 0;

            for (let m of messaggi) {
                if (!m || !m.hasMedia) continue;
                
                let tipo_file = m.type === "image" ? "foto" : m.type === "video" ? "video" : null;
                if (!tipo_file) continue;

                let nome_file = `WA_${m.timestamp}.${tipo_file === "foto" ? "jpg" : "mp4"}`;
                const esiste = await db.get('SELECT 1 FROM log_birre WHERE nome_file = ?', [nome_file]);
                if (esiste) continue;

                const media = await m.downloadMedia().catch(() => null);
                if (!media || !media.data) continue;

                let percorso = `${CARTELLA_MEDIA}/${nome_file}`;
                fs.writeFileSync(percorso, media.data, 'base64');

                let mDataOra = new Date(m.timestamp * 1000).toLocaleString('it-IT');
                let mContact = await m.getContact().catch(() => null);
                let mAutore = "Storico";
                if (mContact && mContact.number) {
                    mAutore = `+${mContact.number.substring(0, 2)} *** ${mContact.number.slice(-4)}`;
                } else if (m.author) {
                    let rawNum = m.author.replace('@c.us', '');
                    if (rawNum.length > 6) mAutore = `+${rawNum.substring(0, 2)} *** ${rawNum.slice(-4)}`;
                }

                if (tipo_file === "foto") {
                    console.log(`🤖 Invio ${nome_file} all'AI... (Pausa 10s per evitare blocchi)`);
                    await ritardo(10000);
                    
                    // PREPARAZIONE DATI PER PYTHON (Storico)
                    const row = await db.get("SELECT valore FROM config WHERE chiave = 'OFFICIAL_TOTAL'");
                    const totaleAttuale = parseInt(row.valore || 0);
                    const mTestoPulito = (m.body || "").replace(/"/g, '\\"').replace(/\n/g, ' ');

                    await new Promise(resolve => {
                        // CHIAMATA A PYTHON CON I NUOVI ARGOMENTI
                        exec(`${pythonPath} ai_judge.py "${percorso}" ${totaleAttuale} "${mTestoPulito}"`, async (err, stdout) => {
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
                } else if (tipo_file === "video" && (m.body || "").match(regex_numeri_birra)) {
                    await inserisciNelDB(db, mDataOra, mAutore, nome_file, 1, "video");
                    if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                    recuperati++;
                } else {
                    if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                }
            }
            console.log(`🎉 Recupero finito: ${recuperati} birre aggiunte.`);
            await db.close();
            return;
        }

        // 🟡 GESTIONE MESSAGGI IN DIRETTA
        if (msg.hasMedia) {
            const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });
            const media = await msg.downloadMedia().catch(() => null);
            if (!media) { await db.close(); return; }

            let tipo_file = media.mimetype.includes("image") ? "foto" : media.mimetype.includes("video") ? "video" : null;
            if (tipo_file) {
                let nome_file = `WA_${msg.timestamp}.${tipo_file === "foto" ? "jpg" : "mp4"}`;
                let percorso = `${CARTELLA_MEDIA}/${nome_file}`;
                fs.writeFileSync(percorso, media.data, 'base64');

                if (tipo_file === "foto") {
                    
                    // PREPARAZIONE DATI PER PYTHON (Diretta)
                    const row = await db.get("SELECT valore FROM config WHERE chiave = 'OFFICIAL_TOTAL'");
                    const totaleAttuale = parseInt(row.valore || 0);
                    const testoPulito = testo.replace(/"/g, '\\"').replace(/\n/g, ' ');

                    // CHIAMATA A PYTHON CON I NUOVI ARGOMENTI
                    exec(`${pythonPath} ai_judge.py "${percorso}" ${totaleAttuale} "${testoPulito}"`, async (err, stdout) => {
                        const match = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                        let birre = match ? parseInt(match[1]) : 0;
                        if (birre > 0) {
                            await inserisciNelDB(db, data_ora, autore, nome_file, birre, "foto");
                        }
                        if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                        await db.close();
                    });
                    return; 
                } else if (tipo_file === "video" && testo.match(regex_numeri_birra)) {
                    await inserisciNelDB(db, data_ora, autore, nome_file, 1, "video");
                    if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                } else {
                    if (fs.existsSync(percorso)) fs.unlinkSync(percorso);
                }
            }
            await db.close();
        }

    } catch (e) {
        console.log("🛡️ Errore generale:", e.message);
    }
});

client.initialize();