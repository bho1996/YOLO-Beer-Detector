const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { execFile, exec } = require('child_process');

// --- CONFIGURAZIONI ---
const NOME_GRUPPO_BERSAGLIO = "1 million beers 🍻";
const CARTELLA_MEDIA = "./photo_folder";
const PYTHON_PATH = "/srv/mergerfs/PoolArchivio/YOLO-Beer-Detector/venv/bin/python";
const SCRIPT_PATH = "/srv/mergerfs/PoolArchivio/YOLO-Beer-Detector/ai_judge.py";
const DB_PATH = "/srv/mergerfs/PoolArchivio/YOLO-Beer-Detector/1m_beers.db";
const AI_TIMEOUT_MS = 120000;
const SALTO_MAX_SICUREZZA = 5000;   // anti-typo catastrofico (uno zero in più)
const SYNC_INTERVALLO_MS = 15 * 60 * 1000;  // sync periodico ogni 15 min

if (!fs.existsSync(CARTELLA_MEDIA)) {
    fs.mkdirSync(CARTELLA_MEDIA);
}

const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g;
const regex_totale_globale = /\b\d{5,6}\b/g;

// ==========================================
// PREFISSI INTERNAZIONALI (longest-first)
// ==========================================
const PREFISSI_INT = [
    '+1242','+1246','+1264','+1268','+1284','+1340','+1345','+1441','+1473',
    '+1649','+1664','+1670','+1671','+1684','+1758','+1767','+1784','+1809',
    '+1829','+1849','+1868','+1869','+1876',
    '+212','+213','+216','+218','+220','+221','+222','+223','+224','+225',
    '+226','+227','+228','+229','+230','+231','+232','+233','+234','+235',
    '+236','+237','+238','+239','+240','+241','+242','+243','+244','+245',
    '+246','+247','+248','+249','+250','+251','+252','+253','+254','+255',
    '+256','+257','+258','+260','+261','+262','+263','+264','+265','+266',
    '+267','+268','+269','+290','+291','+297','+298','+299',
    '+350','+351','+352','+353','+354','+355','+356','+357','+358','+359',
    '+370','+371','+372','+373','+374','+375','+376','+377','+378','+379',
    '+380','+381','+382','+383','+385','+386','+387','+388','+389',
    '+420','+421','+423',
    '+500','+501','+502','+503','+504','+505','+506','+507','+508','+509',
    '+590','+591','+592','+593','+594','+595','+596','+597','+598','+599',
    '+670','+672','+673','+674','+675','+676','+677','+678','+679','+680',
    '+681','+682','+683','+685','+686','+687','+688','+689','+690','+691','+692',
    '+850','+852','+853','+855','+856','+880','+886',
    '+960','+961','+962','+963','+964','+965','+966','+967','+968','+970',
    '+971','+972','+973','+974','+975','+976','+977','+992','+993','+994',
    '+995','+996','+998',
    '+20','+27','+30','+31','+32','+33','+34','+36','+39','+40','+41','+43',
    '+44','+45','+46','+47','+48','+49','+51','+52','+53','+54','+55','+56',
    '+57','+58','+60','+61','+62','+63','+64','+65','+66','+81','+82','+84',
    '+86','+90','+91','+92','+93','+94','+95','+98',
    '+1','+7'
];

function estraiPrefisso(numeroCompleto) {
    for (const pref of PREFISSI_INT) {
        const prefPulito = pref.replace('+', '');
        if (numeroCompleto.startsWith(prefPulito)) return pref;
    }
    return '+??';
}

// ==========================================
// STATO GLOBALI
// ==========================================
let db;
let isSyncing = false;
const codaAI = [];
let staProcessandoCoda = false;
let tentativiRiconnessione = 0;
let ultimoMessaggioVisto = Date.now();
let erroriSondaConsecutivi = 0;
let ultimoSyncDate = null;   // Tiene traccia del giorno in cui è stato fatto il sync

// ==========================================
// MOTORE DEL TOTALE: avanza sempre, non blocca mai
// ==========================================
async function leggiTotale() {
    const row = await db.get("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'");
    return row ? parseInt(row.valore) : 0;
}

async function avanzaTotale(delta, fonte) {
    if (delta < 1) delta = 1;
    const totaleAttuale = await leggiTotale();
    const nuovoTotale = totaleAttuale + delta;
    await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", nuovoTotale);
    console.log(`🏆 [${fonte}] Totale: ${totaleAttuale} → ${nuovoTotale} (+${delta})`);
    return nuovoTotale;
}

async function allineaTotale(nuovoValore, fonte) {
    const totaleAttuale = await leggiTotale();
    if (nuovoValore <= totaleAttuale) {
        console.log(`ℹ️ [${fonte}] ${nuovoValore} ≤ ${totaleAttuale}. Ignorato (no rollback).`);
        return { aggiornato: false, delta: 0 };
    }
    const salto = nuovoValore - totaleAttuale;
    if (salto > SALTO_MAX_SICUREZZA) {
        console.log(`⚠️ [${fonte}] Salto +${salto} eccessivo (${nuovoValore}). Probabile typo. NON blocco, ignoro.`);
        return { aggiornato: false, delta: 0 };
    }
    await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", nuovoValore);
    console.log(`🏆 [${fonte}] Totale: ${totaleAttuale} → ${nuovoValore} (+${salto})`);
    return { aggiornato: true, delta: salto };
}

// ==========================================
// SYNC GIT CENTRALIZZATA
// ==========================================
async function sincronizzaGit(messaggioCommit = "🤖 Auto-update: nuove birre") {
    if (isSyncing) return;
    isSyncing = true;
    try {
        await db.run('PRAGMA wal_checkpoint(TRUNCATE)');
        exec(`git add 1m_beers.db && if ! git diff --cached --quiet; then git commit -m "${messaggioCommit}"; fi && git push origin main`, (error) => {
            isSyncing = false;
            if (error) console.log("⚠️ Errore Git:", error.message);
            else console.log("🚀 Dashboard aggiornata!");
        });
    } catch (e) {
        isSyncing = false;
    }
}

// ==========================================
// CODA AI CON TIMEOUT
// ==========================================
async function smaltisciCoda() {
    if (staProcessandoCoda || codaAI.length === 0) return;
    staProcessandoCoda = true;
    while (codaAI.length > 0) {
        const task = codaAI.shift();
        try { await task(); } catch (err) { console.log("⚠️ Errore task coda AI:", err.message); }
    }
    staProcessandoCoda = false;
}

function runAiJudge(percorso_file, totaleAttuale, testoUtente) {
    return new Promise((resolve) => {
        let chiuso = false;
        const args = [SCRIPT_PATH, percorso_file, String(totaleAttuale || 0), (testoUtente || "").slice(0, 500)];
        const child = execFile(PYTHON_PATH, args, { maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
            if (chiuso) return;
            chiuso = true;
            clearTimeout(timer);
            if (error) console.log(`⚠️ Errore AI: ${error.message}`);
            // Prendi l'ULTIMA occorrenza: quella finale del Notaio,
            // non quella stampata nei debug delle risposte grezze
            const occorrenze = stdout ? [...stdout.matchAll(/BEERS_FOUND:\s*(\d+)/g)] : [];
            if (occorrenze.length > 0) {
                resolve(parseInt(occorrenze[occorrenze.length - 1][1], 10));
            } else {
                resolve(0); // il chiamante fa il clamp a 1
            }
        });
        const timer = setTimeout(() => {
            if (chiuso) return;
            console.log(`⏱️ Timeout AI (${AI_TIMEOUT_MS / 1000}s). Kill.`);
            try { child.kill("SIGKILL"); } catch (e) {}
            chiuso = true;
            resolve(0);
        }, AI_TIMEOUT_MS);
    });
}
// ==========================================
// RIMOZIONE ECCESSO: toglie punti dalle foto con più punti
// ==========================================
// Versione semplificata: elimina foto con 0 punti dal conteggio
async function rimuoviEccesso(eccesso) {
    if (eccesso <= 0) return 0;
    const risultato = await db.run(
        "DELETE FROM log_birre WHERE tipo_file = 'foto' AND punti = 0"
    );
    console.log(`🗑️ Rimosse ${risultato.changes} foto con 0 punti.`);
    // Se serve ancora togliere punti, sottrai dalle foto con 1 punto
    let daRimuovere = eccesso - risultato.changes;
    if (daRimuovere > 0) {
        const foto = await db.all(
            "SELECT rowid FROM log_birre WHERE tipo_file = 'foto' AND punti = 1 ORDER BY rowid DESC LIMIT ?",
            [daRimuovere]
        );
        for (const f of foto) {
            await db.run("UPDATE log_birre SET punti = 0 WHERE rowid = ?", [f.rowid]);
        }
        console.log(`🔻 Azzerate altre ${foto.length} foto.`);
        return risultato.changes + foto.length;
    }
    return risultato.changes;
}

async function syncPeriodicoConChat() {
    try {
        const tutteLeChat = await client.getChats();
        const gruppo = tutteLeChat.find(c => c.name === NOME_GRUPPO_BERSAGLIO);
        if (!gruppo) return;

        // Raccogli tutti i totali scritti negli ultimi 50 messaggi
        const messaggi = await gruppo.fetchMessages({ limit: 50 });
        const totali = [];
        for (const m of messaggi) {
            const match = (m.body || "").match(/\b\d{5,6}\b/g);
            if (match) for (const n of match) {
                const v = parseInt(n);
                if (v > 10000) totali.push(v);
            }
        }
        if (totali.length === 0) return;

        // Filtro anti-outlier: solo valori entro una finestra plausibile
        const rowTotale = await db.get("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'");
        const dbTotal = rowTotale ? parseInt(rowTotale.valore) : 0;

        const plausibili = totali.filter(v => Math.abs(v - dbTotal) <= 500);
        if (plausibili.length === 0) return;

        plausibili.sort((a, b) => b - a);
        const massimo = plausibili[0];
        const secondo = plausibili.length > 1 ? plausibili[1] : null;

        // Richiede consenso: se c'è un secondo valore, deve essere vicino al massimo
        if (secondo !== null && (massimo - secondo) > 10) {
            console.log(`🔎 Sync: ${massimo} vs ${secondo} non consensuale. Salto.`);
            return;
        }

        const gap = massimo - dbTotal;

        // CASO A: il gruppo è AVANTI → allinea verso l'alto
        if (gap > 0 && gap <= 100) {
            console.log(`🔎 Sync ↑: allineo ${dbTotal} → ${massimo} (+${gap}).`);
            await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", massimo);
            await sincronizzaGit(`🤖 Auto-sync: totale a ${massimo}`);
            return;
        }

        // CASO B: il gruppo è INDIETRO → il DB ha contato troppo
        if (gap < 0) {
            const eccesso = -gap;  // quantità da rimuovere
            if (eccesso > 100) {
                console.log(`🔎 Sync ↓: gap troppo grande (${eccesso}), probabilmente outlier. Salto.`);
                return;
            }
            console.log(`🔎 Sync ↓: DB ha ${eccesso} punti in più. Li tolgo dalle foto più alte.`);
            const rimosso = await rimuoviEccessoPunti(eccesso);
            // Abbassa il totale al valore reale del gruppo
            await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", massimo);
            await sincronizzaGit(`🤖 Auto-sync: corretto eccesso, totale a ${massimo}`);
            return;
        }

        console.log(`🔎 Sync: totali già allineati (${dbTotal}).`);
    } catch (e) {
        console.log("⚠️ Sync periodico fallito:", e.message);
    }
}
// ==========================================
// DATABASE
// ==========================================
async function initDatabase() {
    db = await open({ filename: DB_PATH, driver: sqlite3.Database });
    await db.run('PRAGMA journal_mode=WAL');
    await db.run('PRAGMA busy_timeout = 30000');
    console.log('📦 Database SQLite pronto (WAL mode)');
}

// ==========================================
// CLIENT WHATSAPP
// ==========================================
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        executablePath: '/usr/bin/chromium',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    }
});

client.on('qr', (qr) => {
    console.log('🔐 QR generato: serve scansione.');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    tentativiRiconnessione = 0;
    console.log(`✅ Bot connesso come ${client.info.wid.user}`);
    console.log('✅ In attesa di birre...');
});

client.on('auth_failure', (msg) => {
    console.error('❌ Auth failure:', msg);
});

client.on('disconnected', (reason) => {
    console.log(`❌ Disconnesso. Motivo: ${reason}`);
    if (reason === 'LOGOUT') {
        console.log('🔐 Sessione invalidata: servirà il QR.');
        return;
    }
    if (tentativiRiconnessione < 10) {
        tentativiRiconnessione++;
        console.log(`🔄 Riconnessione ${tentativiRiconnessione}/10 tra 15s...`);
        setTimeout(() => { client.initialize().catch(e => console.log('Re-init err:', e.message)); }, 15000);
    } else {
        console.log('💀 Troppi tentativi. Riavvio processo.');
        process.exit(1);
    }
});

client.on('change_state', (state) => {
    console.log('📶 Stato client:', state);
});

// ==========================================
// SYNC GIORNALIERO alle 7:00 del mattino
// ==========================================
setInterval(async () => {
    const ora = new Date();
    const ore = ora.getHours();
    const oggi = ora.toISOString().slice(0, 10);  // formato "YYYY-MM-DD"

    // Esegui solo se sono passate le 7:00 E non è ancora stato fatto oggi
    if (ore >= 7 && ultimoSyncDate !== oggi) {
        console.log(`⏰ Sync giornaliero delle 7:00 - avviato il ${oggi}`);
        await syncPeriodicoConChat();
        ultimoSyncDate = oggi;
    }
}, 10 * 60 * 1000);  // controlla ogni 10 minuti se è ora di fare il sync
setInterval(async () => {
    const pronto = Boolean(client.info);
    const minutiSilenzio = Math.round((Date.now() - ultimoMessaggioVisto) / 60000);
    console.log(`❤️ Watchdog | ready=${pronto} | coda=${codaAI.length} | busy=${staProcessandoCoda} | silenzio=${minutiSilenzio}m`);

    if (!pronto) {
        erroriSondaConsecutivi = 0;
        if (tentativiRiconnessione === 0) {
            console.log('🤔 Client non pronto, provo initialize()...');
            client.initialize().catch(() => {});
        }
        return;
    }

    // SONDA: se c'è silenzio da 30+ minuti, verifica che la pagina risponda davvero
    if (minutiSilenzio >= 30) {
        try {
            await client.getChats();
            erroriSondaConsecutivi = 0;
        } catch (e) {
            erroriSondaConsecutivi++;
            console.log(`🩺 Sonda fallita (${erroriSondaConsecutivi}/2): ${e.message}`);
            if (erroriSondaConsecutivi >= 2) {
                console.log('💀 Pagina WhatsApp morta (zombie). Riavvio il processo.');
                process.exit(1); // PM2 lo rilancia, LocalAuth si riconnette senza QR
            }
        }
    } else {
        erroriSondaConsecutivi = 0;
    }
}, 5 * 60 * 1000);

// ==========================================
// RISOLUZIONE IDENTITÀ
// ==========================================
const cacheIdentita = new Map();

async function risolviIdentita(msg) {
    try {
        const rawId = msg.author;
        if (!rawId) return "Sconosciuto";
        const parti = rawId.split('@');
        const parteLocale = parti[0];
        const suffisso = parti[1] || '';

        if (suffisso === 'c.us') {
            const soloNumeri = parteLocale.replace(/[^0-9]/g, '');
            const pref = estraiPrefisso(soloNumeri);
            if (soloNumeri.length >= 7 && pref !== '+??') {
                return `${pref} *** ${soloNumeri.slice(-4)}`;
            }
        }

        if (cacheIdentita.has(parteLocale)) return cacheIdentita.get(parteLocale);

        try {
            const contact = await msg.getContact();
            if (contact && contact.id && contact.id.user) {
                const soloNumeri = String(contact.id.user).replace(/[^0-9]/g, '');
                const pref = estraiPrefisso(soloNumeri);
                if (soloNumeri.length >= 7 && soloNumeri.length <= 15 && pref !== '+??') {
                    const risultato = `${pref} *** ${soloNumeri.slice(-4)}`;
                    cacheIdentita.set(parteLocale, risultato);
                    return risultato;
                }
            }
        } catch (e) {}

        const cifre = parteLocale.replace(/[^0-9]/g, '');
        const risultato = `🔒 *** ${(cifre || parteLocale).slice(-4)}`;
        cacheIdentita.set(parteLocale, risultato);
        return risultato;
    } catch (e) {
        return "Sconosciuto";
    }
}

// ==========================================
// HANDLER MESSAGGI
// ==========================================
client.on('message_create', async msg => {
    try {
        if (!msg || !msg.from) return;
        ultimoMessaggioVisto = Date.now();
        if (['notification', 'revoked', 'reaction'].includes(msg.type)) return;

        let chat;
        for (let tentativo = 1; tentativo <= 2; tentativo++) {
            try { chat = await msg.getChat(); break; }
            catch (chatErr) {
                if (tentativo === 2) { console.log(`⚠️ getChat fallito: ${chatErr.message}`); return; }
                await new Promise(r => setTimeout(r, 500));
            }
        }
        if (!chat) return;
        if (!client.info) return;

        const myId = client.info.wid?._serialized;
        // FILTRO RISTRETTO: accetta SOLO messaggi dal gruppo target
// (niente DM, niente altri gruppi, niente messaggi propri)
if (chat.name !== NOME_GRUPPO_BERSAGLIO) {
    // Log opzionale per debug: vedi quali gruppi stanno arrivando
    if (msg.hasMedia) {
        console.log(`🚫 Ignorato media da chat "${chat.name}" (non è il gruppo target)`);
    }
    return;
}

        let testo = msg.body || "";

        // ---------- COMANDO RECUPERO STORICO ----------
        if (testo.startsWith('!recupero_storico')) {
            let parti = testo.split(' ');
            let limite = parti[1] ? parseInt(parti[1]) : 50;
            console.log(`🔄 Recupero storico: ${limite} messaggi...`);
            msg.reply(`🕵️‍♂️ Recupero ultimi ${limite} messaggi...`);
            try {
                const tutteLeChat = await client.getChats();
                const gruppoBersaglio = tutteLeChat.find(c => c.name === NOME_GRUPPO_BERSAGLIO);
                if (!gruppoBersaglio) { msg.reply(`❌ Gruppo non trovato.`); return; }
                const messaggi_passati = await gruppoBersaglio.fetchMessages({ limit: limite });
                let contatore_media = 0;
                for (let msg_vecchio of messaggi_passati) {
                    if (msg_vecchio.hasMedia) { client.emit('message_create', msg_vecchio); contatore_media++; }
                }
                msg.reply(`✅ Trovati ${contatore_media} media da analizzare.`);
            } catch (err) { msg.reply(`⚠️ Errore: ${err.message}`); }
            return;
        }

        // ---------- AUTORE ----------
        let data_ora = new Date(msg.timestamp * 1000).toLocaleString('it-IT', {
            timeZone: 'Europe/Rome', day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit'
        });
        let autore = await risolviIdentita(msg);
        let matchTotale = testo.match(regex_totale_globale);

        // ---------- MESSAGGIO SOLO TESTO CON TOTALE (mai bloccante) ----------
        if (matchTotale && !msg.hasMedia) {
            let nuovoValore = parseInt(matchTotale[matchTotale.length - 1]);
            const risultato = await allineaTotale(nuovoValore, "Testo");

            if (risultato.aggiornato) {
                // VAR retroattivo: corregge l'ultima foto dell'autore
                const fotoRecente = await db.get(
                    `SELECT rowid, punti FROM log_birre WHERE utente = ? AND tipo_file = 'foto' ORDER BY rowid DESC LIMIT 1`, [autore]
                );
                if (fotoRecente) {
                    await db.run("UPDATE log_birre SET punti = ? WHERE rowid = ?", [risultato.delta, fotoRecente.rowid]);
                    console.log(`🔄 VAR: ${autore} corretto da ${fotoRecente.punti} a ${risultato.delta}`);
                }
                await sincronizzaGit(`🤖 Auto-update: totale a ${nuovoValore}`);
            }
        }

        // ---------- GESTIONE MEDIA ----------
        if (msg.hasMedia) {
            console.log("⏳ Download media...");
            const media = await msg.downloadMedia();
            if (!media) return;

            let tipo_file = "";
            let estensione = "";
            if (media.mimetype.includes("image")) { tipo_file = "foto"; estensione = "jpg"; }
            else if (media.mimetype.includes("video")) { tipo_file = "video"; estensione = "mp4"; }

            if (tipo_file !== "") {
                let nome_file = `WA_${msg.timestamp}.${estensione}`;
                let percorso_file = `${CARTELLA_MEDIA}/${nome_file}`;
                fs.writeFileSync(percorso_file, media.data, 'base64');
                console.log(`📎 Salvato: ${nome_file}`);

                if (tipo_file === "video" && testo.match(regex_numeri_birra)) {
                    await inserisciNelDB(data_ora, autore, nome_file, 5, "video");
                } else if (tipo_file === "foto") {
                    console.log(`📥 Foto in coda AI: ${nome_file}`);
                    codaAI.push(async () => {
                        console.log(`🤖 Analisi AI (binaria): ${nome_file}`);
                        const totaleAttuale = await leggiTotale();
                        const conteggio = await chiamaAI(percorso_file, totaleAttuale, testo);
                        // L'AI ora risponde 0 (niente birra) o >=1 (birra presente)
                        const delta = conteggio >= 1 ? 1 : 0;
                        
                        if (delta > 0) {
                            await avanzaTotale(delta, `Foto ${nome_file}`);
                            console.log(`✅ FOTO: AI ha visto birra → +${delta} punto`);
                        } else {
                            console.log(`⛔ FOTO: AI non ha visto birra → 0 punti (foto scartata)`);
                        }
                        await inserisciNelDB(data_ora, autore, nome_file, delta, "foto");
                    });
                    smaltisciCoda();

                }
            }
        }
    } catch (erroreImprevisto) {
        console.log("🛡️ Errore globale:", erroreImprevisto.message);
    }
});

// ==========================================
// INSERIMENTO DB + SYNC GIT
// ==========================================
async function inserisciNelDB(d_ora, utente, file, punti, tipo) {
    try {
        await db.run(
            `INSERT OR IGNORE INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
            [d_ora, utente, file, punti, tipo]
        );
        const changes = await db.get('SELECT changes() as cnt');
        if (changes.cnt === 0) return;
        console.log(`🏅 PUNTI: ${utente} +${punti} (${file})`);
        await sincronizzaGit();
    } catch (err) {
        console.log("⚠️ Errore DB:", err.message);
    }
}

// ==========================================
// AVVIO
// ==========================================
(async () => {
    await initDatabase();
    client.initialize();
})();