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

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        executablePath: '/usr/bin/chromium',
        timeout: 60000,
        protocolTimeout: 60000,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-gpu'
        ]
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));

client.on('ready', () => {
    console.log('✅ Bot connesso e AI caricata! In attesa di birre...');
    setInterval(() => console.log("⏱️ Bot ancora attivo, in attesa di messaggi..."), 30000);
    setInterval(async () => {
        try {
            const state = await client.getState();
            console.log(`📡 Stato connessione: ${state}`);
        } catch (e) {
            console.log(`📡 Errore nel recuperare stato: ${e.message}`);
        }
    }, 60000);
});

client.on('disconnected', reason => {
    console.log('🔴 ATTENZIONE! Bot disconnesso! Motivo:', reason);
    process.exit(1);
});

let isSyncing = false;

client.on('message_create', async msg => {
    console.log(`🔥 EVENTO SCATTATO - Da: ${msg.from} - Corpo: ${msg.body.substring(0, 30)}`);

    try {
        if (!msg || !msg.from) return;

        const chat = await msg.getChat();
        if (chat.name !== NOME_GRUPPO_BERSAGLIO && chat.name !== CHAT_PERSONALE) return;

        console.log(`\n📬 [EVENTO] Messaggio AUTORIZZATO da: ${msg.from} | Chat: "${chat.name}" | Tipo: ${msg.type}`);

        let contact;
        try {
            contact = await msg.getContact();
        } catch {
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
            hour: '2-digit', minute: '2-digit'
        });

        // Apriamo il DB
        const db = await open({ filename: './1m_beers.db', driver: sqlite3.Database });

        // 🧮 FUNZIONE DB (definita subito per essere usata dopo)
        async function inserisciNelDB(dbConnection, d_ora, utente, file, punti, tipo, shouldClose = true) {
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

                console.log(`🏅 ASSEGNATI: ${punti} punti a ${utente}! Il Totale Globale è salito!`);

                if (!isSyncing) {
                    isSyncing = true;
                    console.log("☁️ Sincronizzazione in corso...");
                    exec('git add 1m_beers.db && git commit -m "🤖 Auto-update" && git pull origin main --rebase && git push', (error) => {
                        isSyncing = false;
                        if (error) console.log("⚠️ Errore Git:", error.message);
                        else console.log("🚀 Aggiornato su Cloud!");
                    });
                } else {
                    console.log("⏳ Sincronizzazione già in coda...");
                }
            } catch (err) {
                console.log("⚠️ Errore DB:", err.message);
            } finally {
                if (shouldClose) await dbConnection.close();
            }
        }

        // 👑 GESTIONE COMANDI ADMIN
        if (testo.startsWith("!recupera_storico ")) {
            let limite = parseInt(testo.replace("!recupera_storico ", "").trim()) || 50;
            console.log(`\n⏳ [RECUPERO STORICO] Scansione ultimi ${limite} messaggi...`);

            const messaggi = await chat.fetchMessages({ limit: limite });
            let recuperati = 0;

            for (let m of messaggi) {
                if (!m.hasMedia || (m.type !== "image" && m.type !== "video")) continue;

                let estensione = m.type === "image" ? "jpg" : "mp4";
                let tipo_file = m.type === "image" ? "foto" : "video";
                let nome_file = `WA_${m.timestamp}.${estensione}`;

                const esiste = await db.get('SELECT 1 FROM log_birre WHERE nome_file = ?', [nome_file]);
                if (esiste) {
                    console.log(`⏭️ Salto: ${nome_file} già presente.`);
                    continue;
                }

                console.log(`📥 Download: ${nome_file}...`);
                const media = await m.downloadMedia();
                if (!media) continue;

                let percorso_file = `${CARTELLA_MEDIA}/${nome_file}`;
                fs.writeFileSync(percorso_file, media.data, 'base64');

                let mContact = await m.getContact();
                let numGrezzo = mContact.number;
                let mAutore = mContact.pushname || "Sconosciuto";
                if (numGrezzo) {
                    let prefisso = "+" + numGrezzo.substring(0, 2);
                    let ultime4 = numGrezzo.slice(-4);
                    mAutore = `${prefisso} *** ${ultime4}`;
                }
                let mDataOra = new Date(m.timestamp * 1000).toLocaleString('it-IT', {
                    day: '2-digit', month: '2-digit', year: '2-digit',
                    hour: '2-digit', minute: '2-digit'
                });

                let testoMsg = m.body || "";

                if (tipo_file === "foto") {
                    await new Promise(resolve => {
                        exec(`./env_birre/bin/python ai_judge.py "${percorso_file}"`, async (error, stdout) => {
                            let birre = 0;
                            const match = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                            if (match) birre = parseInt(match[1]);

                            if (birre > 0) {
                                console.log(`✅ [RECUPERO] Trovate ${birre} birre!`);
                                await inserisciNelDB(db, mDataOra, mAutore, nome_file, birre, "foto", false);
                                recuperati++;
                            } else {
                                console.log(`❌ [RECUPERO] Nessuna birra.`);
                            }
                            fs.unlinkSync(percorso_file);
                            resolve();
                        });
                    });
                } else if (tipo_file === "video" && testoMsg.match(regex_numeri_birra)) {
                    await inserisciNelDB(db, mDataOra, mAutore, nome_file, 5, "video", false);
                    fs.unlinkSync(percorso_file);
                    recuperati++;
                } else {
                    fs.unlinkSync(percorso_file);
                }
            }
            console.log(`🎉 Recuperati ${recuperati} nuovi file.`);
            await db.close();
            return;
        }
        else if (testo.startsWith("!recupera ")) {
            let target = testo.replace("!recupera ", "").trim();
            console.log(`🛠️ [ADMIN] Recupero per: ${target}`);
            await db.close();
            return;
        }
        else if (testo.startsWith("!forza ")) {
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
            return;
        }

        // 📸 GESTIONE MEDIA IN DIRETTA
        if (msg.hasMedia) {
            console.log("⏳ Download media in corso...");
            const media = await msg.downloadMedia();
            if (!media) return;

            let tipo_file = media.mimetype.includes("image") ? "foto" : media.mimetype.includes("video") ? "video" : "";
            let estensione = tipo_file === "foto" ? "jpg" : tipo_file === "video" ? "mp4" : "";
            if (!tipo_file) return;

            let nome_file = `WA_${msg.timestamp}.${estensione}`;
            let percorso_file = `${CARTELLA_MEDIA}/${nome_file}`;
            fs.writeFileSync(percorso_file, media.data, 'base64');
            console.log(`📎 File salvato: ${nome_file}`);

            if (tipo_file === "video" && testo.match(regex_numeri_birra)) {
                await inserisciNelDB(db, data_ora, autore, nome_file, 5, "video");
                fs.unlinkSync(percorso_file);
                console.log(`🗑️ Video eliminato.`);
                return;
            }
            else if (tipo_file === "foto") {
                console.log(`🤖 Invio foto all'AI...`);
                exec(`./env_birre/bin/python ai_judge.py "${percorso_file}"`, async (error, stdout) => {
                    let birre = 0;
                    const match = stdout.match(/BEERS_FOUND:\s*(\d+)/);
                    if (match) birre = parseInt(match[1]);

                    if (birre > 0) {
                        console.log(`✅ AI: ${birre} birre! 🍺`);
                        await inserisciNelDB(db, data_ora, autore, nome_file, birre, "foto");
                    } else {
                        console.log(`❌ AI: zero birre.`);
                        fs.unlinkSync(percorso_file);
                        await db.close(); // chiudi qui perché non c'è stato inserimento
                    }
                });
            }
        } else {
            await db.close(); // messaggi di testo
        }

    } catch (erroreImprevisto) {
        console.log("🛡️ Errore imprevisto:", erroreImprevisto.message);
    }
});

client.initialize();