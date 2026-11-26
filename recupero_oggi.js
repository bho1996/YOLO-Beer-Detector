#!/usr/bin/env node
/**
 * recupero_oggi.js
 * Recupera le birre di un'intera giornata dal gruppo WhatsApp quando il bot è stato offline.
 *
 * Usa la STESSA sessione WhatsApp (LocalAuth), lo STESSO DB e la STESSA logica di bot.js:
 *   - testo con totale  → allineaTotale (no rollback, salto max SALTO_MAX_SICUREZZA)
 *   - foto              → ai_judge.py → 1 punto se vede birra, 0 altrimenti
 *   - video + numero    → 5 punti
 * Le foto/video già presenti nel DB (nome_file UNIQUE) vengono saltati, quindi è rilanciabile.
 *
 * USO (con il bot FERMO: la sessione Chromium non può essere aperta da due processi):
 *   pm2 stop BeerBot
 *   node recupero_oggi.js                 # oggi (ora di Roma)
 *   node recupero_oggi.js 2026-10-02      # un giorno specifico (dalle 00:00 di quel giorno a ora)
 *   node recupero_oggi.js --dry           # solo elenco, niente AI / niente inserimenti
 *   node recupero_oggi.js --no-total      # recupera senza modificare OFFICIAL_TOTAL
 *   pm2 start BeerBot
 */
const { Client, LocalAuth } = require('whatsapp-web.js');
const fs = require('fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { execFile, exec } = require('child_process');

// --- CONFIGURAZIONI (identiche a bot.js) ---
const PROJ_DIR = "/srv/mergerfs/PoolArchivio/YOLO-Beer-Detector";
const NOME_GRUPPO_BERSAGLIO = "1 million beers 🍻";
const CARTELLA_MEDIA = "./photo_folder";
const PYTHON_PATH = `${PROJ_DIR}/venv/bin/python`;
const SCRIPT_PATH = `${PROJ_DIR}/ai_judge.py`;
const DB_PATH = `${PROJ_DIR}/1m_beers.db`;
const AI_TIMEOUT_MS = 120000;
const SALTO_MAX_SICUREZZA = 150;

// --- Parametri solo di questo script ---
const DELAY_AI_MS = 2000;         // pausa tra una foto e l'altra per non saturare la quota AI
const LIMITE_MAX_MESSAGGI = 6000; // tetto di sicurezza ai messaggi da scaricare dalla chat

// bot.js usa percorsi relativi (./photo_folder, .wwebjs_auth, git): lavoriamo dalla cartella progetto
process.chdir(PROJ_DIR);
if (!fs.existsSync(CARTELLA_MEDIA)) fs.mkdirSync(CARTELLA_MEDIA);

const regex_numeri_birra = /\b[1-9]\d{4,5}\b/g;
const regex_totale_globale = /\b\d{5,6}\b/g;

// --- Argomenti ---
const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry');
const NO_TOTAL = args.includes('--no-total');
const argGiorno = args.find(a => /^\d{4}-\d{2}-\d{2}$/.test(a));
const argSince = args.find(a => /^--since=\d+$/.test(a));
const SINCE_TS = argSince ? Number(argSince.split('=')[1]) : 0;

// ==========================================
// PREFISSI INTERNAZIONALI (copiati da bot.js, longest-first)
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
// RISOLUZIONE IDENTITÀ (copiata da bot.js)
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
// DATE (ora di Roma, come data_ora in bot.js)
// ==========================================
function oggiRoma() {
    return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Rome' }); // YYYY-MM-DD
}

function inizioGiornoRoma(yyyy_mm_dd) {
    // Prova gli offset possibili (ora legale/solare) e tieni quello che dà le 00:00 a Roma
    for (const off of ['+02:00', '+01:00']) {
        const d = new Date(`${yyyy_mm_dd}T00:00:00${off}`);
        const s = d.toLocaleString('sv-SE', { timeZone: 'Europe/Rome' });
        if (s.startsWith(`${yyyy_mm_dd} 00:00`)) return Math.floor(d.getTime() / 1000);
    }
    throw new Error(`Data non valida: ${yyyy_mm_dd}`);
}

function formattaDataOra(timestamp) {
    return new Date(timestamp * 1000).toLocaleString('it-IT', {
        timeZone: 'Europe/Rome', day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit'
    });
}

// ==========================================
// DB + MOTORE DEL TOTALE (identici a bot.js, con guardia DRY_RUN)
// ==========================================
let db;

async function initDatabase() {
    db = await open({ filename: DB_PATH, driver: sqlite3.Database });
    await db.run('PRAGMA journal_mode=WAL');
    await db.run('PRAGMA busy_timeout = 30000');
    await db.run(`CREATE TABLE IF NOT EXISTS foto_in_attesa (
        nome_file TEXT PRIMARY KEY,
        data_ora TEXT,
        utente TEXT,
        testo TEXT,
        tentativi INTEGER DEFAULT 0,
        ultimo_errore TEXT,
        creato TEXT DEFAULT (datetime('now','localtime')),
        aggiungi_totale INTEGER NOT NULL DEFAULT 1
    )`);
    const colonneAttesa = await db.all('PRAGMA table_info(foto_in_attesa)');
    if (!colonneAttesa.some(c => c.name === 'aggiungi_totale')) {
        await db.run('ALTER TABLE foto_in_attesa ADD COLUMN aggiungi_totale INTEGER NOT NULL DEFAULT 1');
    }
    console.log('📦 Database SQLite pronto (WAL mode)');
}

async function mettiInAttesa(nome_file, data_ora, utente, testo, motivo) {
    if (DRY_RUN) return;
    await db.run(
        `INSERT OR IGNORE INTO foto_in_attesa (nome_file, data_ora, utente, testo, tentativi, ultimo_errore, aggiungi_totale)
         VALUES (?, ?, ?, ?, 1, ?, ?)`,
        [nome_file, data_ora, utente, (testo || "").slice(0, 500), motivo, NO_TOTAL ? 0 : 1]
    );
}

async function leggiTotale() {
    const row = await db.get("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'");
    return row ? parseInt(row.valore) : 0;
}

async function avanzaTotale(delta, fonte) {
    if (delta < 1) delta = 1;
    const totaleAttuale = await leggiTotale();
    const nuovoTotale = totaleAttuale + delta;
    if (!DRY_RUN) await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", nuovoTotale);
    console.log(`🏆 [${fonte}] Totale: ${totaleAttuale} → ${nuovoTotale} (+${delta})`);
    return nuovoTotale;
}

async function allineaTotale(nuovoValore, fonte) {
    if (NO_TOTAL) {
        console.log(`ℹ️ [${fonte}] Totale storico ${nuovoValore}: nessuna modifica a OFFICIAL_TOTAL (--no-total).`);
        return { aggiornato: false, delta: 0 };
    }
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
    if (!DRY_RUN) await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", nuovoValore);
    console.log(`🏆 [${fonte}] Totale: ${totaleAttuale} → ${nuovoValore} (+${salto})`);
    return { aggiornato: true, delta: salto };
}

async function giaNelDB(nomeFile) {
    const row = await db.get(
        "SELECT 1 AS c FROM log_birre WHERE nome_file = ? UNION ALL SELECT 1 FROM foto_in_attesa WHERE nome_file = ?",
        [nomeFile, nomeFile]
    );
    return Boolean(row);
}

async function inserisciNelDB(d_ora, utente, file, punti, tipo) {
    if (DRY_RUN) { console.log(`🏅 [DRY] PUNTI: ${utente} +${punti} (${file})`); return true; }
    try {
        await db.run(
            `INSERT OR IGNORE INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)`,
            [d_ora, utente, file, punti, tipo]
        );
        const changes = await db.get('SELECT changes() as cnt');
        if (changes.cnt === 0) return false;
        console.log(`🏅 PUNTI: ${utente} +${punti} (${file})`);
        return true;
    } catch (err) {
        console.log("⚠️ Errore DB:", err.message);
        return false;
    }
}

// ==========================================
// AI JUDGE: null = analisi fallita, NON un verdetto negativo
// ==========================================
function runAiJudge(percorso_file, totaleAttuale, testoUtente) {
    return new Promise((resolve) => {
        let chiuso = false;
        const args = [SCRIPT_PATH, percorso_file, String(totaleAttuale || 0), (testoUtente || "").slice(0, 500)];
        const child = execFile(PYTHON_PATH, args, { maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
            if (chiuso) return;
            chiuso = true;
            clearTimeout(timer);
            const output = stdout || '';
            // L'attuale ai_judge.py stampa FATAL ma può terminare con codice 0 e BEERS_FOUND: 0.
            // Anche il caso file mancante è un errore, non una foto senza birra.
            const occorrenze = [...output.matchAll(/^BEERS_FOUND:\s*(-?\d+)\s*$/gm)];
            const valore = occorrenze.length
                ? Number(occorrenze[occorrenze.length - 1][1]) : null;
            if (error || /\[FATAL\]|\[ERRORE\].*non esiste/.test(output)
                    || valore === null || valore < 0) {
                console.log(`⚠️ Analisi AI fallita: ${percorso_file}`);
                if (error) console.log(error.message);
                if (output.trim()) console.log(output.trim());
                if (stderr && stderr.trim()) console.log(stderr.trim());
                resolve(null);
                return;
            }
            resolve(valore);
        });
        const timer = setTimeout(() => {
            if (chiuso) return;
            console.log(`⏱️ Timeout AI (${AI_TIMEOUT_MS / 1000}s). Foto da riprovare.`);
            try { child.kill("SIGKILL"); } catch (e) {}
            chiuso = true;
            resolve(null);
        }, AI_TIMEOUT_MS);
    });
}

// ==========================================
// SYNC GIT (stesso comando di bot.js, una sola volta alla fine)
// ==========================================
function sincronizzaGit(messaggioCommit) {
    return new Promise(async (resolve) => {
        try { await db.run('PRAGMA wal_checkpoint(TRUNCATE)'); } catch (e) {}
        const cmd = [
            `git add 1m_beers.db`,
            `(git add -A potd 2>/dev/null || true)`,
            `(git diff --cached --quiet || git commit -q -m "${messaggioCommit}")`,
            `(git pull -q --no-rebase --no-edit -X ours origin main || (git merge --abort 2>/dev/null; false))`,
            `git push -q origin main`,
        ].join(' && ');
        exec(cmd, { cwd: PROJ_DIR }, (error, stdout, stderr) => {
            if (error) console.log("⚠️ Errore Git:", (stderr || error.message).trim());
            else console.log("🚀 Dashboard aggiornata!");
            resolve();
        });
    });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ==========================================
// RECUPERO MESSAGGI DEL GIORNO
// ==========================================
async function scaricaMessaggiDa(gruppo, daTimestamp) {
    // fetchMessages carica all'indietro: aumento il limite finché il messaggio più vecchio
    // scaricato è precedente all'inizio del giorno (o finché la chat non ha più nulla).
    let limite = 200;
    let messaggi = [];
    while (true) {
        messaggi = await gruppo.fetchMessages({ limit: limite });
        const piuVecchio = messaggi.length ? Math.min(...messaggi.map(m => m.timestamp || 0)) : 0;
        console.log(`📥 Scaricati ${messaggi.length} messaggi (limite ${limite}), il più vecchio: ${piuVecchio ? formattaDataOra(piuVecchio) : '-'}`);
        if (messaggi.length && piuVecchio < daTimestamp) break;   // ho superato l'inizio del giorno
        if (messaggi.length < limite) break;                      // la chat non ha altri messaggi
        if (limite >= LIMITE_MAX_MESSAGGI) {
            console.log(`⚠️ Raggiunto il tetto di ${LIMITE_MAX_MESSAGGI} messaggi: potrei non aver coperto tutto il giorno.`);
            break;
        }
        limite = Math.min(limite * 2, LIMITE_MAX_MESSAGGI);
    }
    return messaggi
        .filter(m => (m.timestamp || 0) >= daTimestamp)
        .sort((a, b) => a.timestamp - b.timestamp);
}

// ==========================================
// MESSAGGI LIVE: arrivano mentre il recupero è in corso (il bot è fermo, li prendiamo noi)
// ==========================================
const codaLive = [];
const idVisti = new Set();

function idDi(msg) {
    return (msg.id && msg.id._serialized) || `${msg.from}|${msg.timestamp}|${msg.type}`;
}

// ==========================================
// LOGICA PER SINGOLO MESSAGGIO (identica al blocco media/testo di bot.js)
// ==========================================
async function processaMessaggio(msg, tag, stat) {
    try {
        if (SINCE_TS && (msg.timestamp || 0) <= SINCE_TS) return;
        if (['notification', 'revoked', 'reaction'].includes(msg.type)) return;

        const testo = msg.body || "";
        const data_ora = formattaDataOra(msg.timestamp);
        const matchTotale = testo.match(regex_totale_globale);

        // ---------- MESSAGGIO SOLO TESTO CON TOTALE ----------
        if (matchTotale && !msg.hasMedia) {
            const nuovoValore = parseInt(matchTotale[matchTotale.length - 1]);
            await allineaTotale(nuovoValore, `Testo ${data_ora}`);
            stat.testi++;
            return;
        }

        // ---------- GESTIONE MEDIA ----------
        if (!msg.hasMedia) return;

        // bot.js salva come WA_<timestamp>.jpg|mp4: se uno dei due è già nel DB, è già stato contato
        const base = `WA_${msg.timestamp}`;
        if (await giaNelDB(`${base}.jpg`) || await giaNelDB(`${base}.mp4`)) {
            console.log(`${tag} ⏭️ ${base} già nel DB, salto.`);
            stat.giaPresenti++;
            return;
        }

        const autore = await risolviIdentita(msg);

        if (DRY_RUN) {
            console.log(`${tag} 📎 [DRY] ${base} (${msg.type}) | ${autore} | "${testo.slice(0, 60)}"`);
            if (msg.type === 'video') { if (testo.match(regex_numeri_birra)) stat.video++; }
            else stat.fotoNuove++;
            return;
        }

        console.log(`${tag} ⏳ Download media...`);
        const media = await msg.downloadMedia();
        if (!media) { console.log(`${tag} ⚠️ Media non scaricabile: ${base}`); stat.mediaNonScaricabili++; return; }

        // Tipo deciso dal mimetype, esattamente come bot.js
        let tipo_file = "", estensione = "";
        if (media.mimetype.includes("image")) { tipo_file = "foto"; estensione = "jpg"; }
        else if (media.mimetype.includes("video")) { tipo_file = "video"; estensione = "mp4"; }
        if (tipo_file === "") return;

        const nome_file = `${base}.${estensione}`;
        const percorso_file = `${CARTELLA_MEDIA}/${nome_file}`;
        fs.writeFileSync(percorso_file, media.data, 'base64');
        console.log(`${tag} 📎 Salvato: ${nome_file}`);

        if (tipo_file === "video") {
            if (!testo.match(regex_numeri_birra)) return;  // video senza numero: bot.js non lo registra
            await inserisciNelDB(data_ora, autore, nome_file, 5, "video");
            stat.video++;
            return;
        }

        // ---------- FOTO ----------
        console.log(`${tag} 🤖 Analisi AI (binaria): ${nome_file}`);
        const totaleAttuale = NO_TOTAL ? 0 : await leggiTotale();
        // Nel recupero senza totale il verdetto deve dipendere solo dalla foto,
        // non dal numero storico o da un typo nella didascalia.
        const conteggio = await runAiJudge(percorso_file, totaleAttuale, NO_TOTAL ? '' : testo);
        if (conteggio === null) {
            stat.erroriAI++;
            await mettiInAttesa(nome_file, data_ora, autore, testo, "AI non disponibile (recupero)");
            console.log(`${tag} ⏸️ ${nome_file}: messa in foto_in_attesa, la riprova il job notturno.`);
            await sleep(DELAY_AI_MS);
            return;
        }
        const delta = conteggio >= 1 ? 1 : 0;

        if (delta > 0) {
            if (!NO_TOTAL) await avanzaTotale(delta, `Foto ${nome_file}`);
            console.log(`${tag} ✅ FOTO: AI ha visto birra → +${delta} punto`);
            stat.fotoConBirra++;
        } else {
            console.log(`${tag} ⛔ FOTO: AI non ha visto birra → 0 punti (foto scartata)`);
        }
        await inserisciNelDB(data_ora, autore, nome_file, delta, "foto");
        stat.fotoNuove++;
        await sleep(DELAY_AI_MS);
    } catch (e) {
        console.log(`${tag} 🛡️ Errore sul messaggio: ${e.message}`);
    }
}

async function processaGiornata(client) {
    const giorno = argGiorno || oggiRoma();
    const daTimestamp = inizioGiornoRoma(giorno);
    console.log(`📅 Recupero dal ${giorno} 00:00 (Roma) a ora${DRY_RUN ? '  [DRY RUN: nessun inserimento di foto]' : ''}`);
    if (NO_TOTAL) console.log('🔒 --no-total: OFFICIAL_TOTAL resta invariato, anche per le foto recuperate dal cron.');

    const tutteLeChat = await client.getChats();
    const gruppo = tutteLeChat.find(c => c.name === NOME_GRUPPO_BERSAGLIO);
    if (!gruppo) throw new Error(`Gruppo "${NOME_GRUPPO_BERSAGLIO}" non trovato.`);
    const idGruppo = gruppo.id._serialized;

    const messaggi = await scaricaMessaggiDa(gruppo, daTimestamp);
    console.log(`🔎 Messaggi del giorno da esaminare: ${messaggi.length}`);

    const totaleIniziale = await leggiTotale();
    const stat = { testi: 0, fotoNuove: 0, fotoConBirra: 0, video: 0, giaPresenti: 0, mediaNonScaricabili: 0, erroriAI: 0, live: 0 };

    // 1) Storico del giorno
    for (let i = 0; i < messaggi.length; i++) {
        idVisti.add(idDi(messaggi[i]));
        await processaMessaggio(messaggi[i], `[${i + 1}/${messaggi.length}]`, stat);
    }

    // 2) Messaggi arrivati LIVE nel frattempo (il listener li ha accodati).
    //    Continuo finché la coda non resta vuota: mentre processo possono arrivarne altri.
    while (codaLive.length > 0) {
        const msg = codaLive.shift();
        const id = idDi(msg);
        if (idVisti.has(id)) continue;
        idVisti.add(id);

        // Stesso filtro di bot.js: solo il gruppo bersaglio
        let chat;
        try { chat = await msg.getChat(); } catch (e) { continue; }
        if (!chat || chat.id._serialized !== idGruppo) continue;

        stat.live++;
        console.log(`📡 Messaggio live (${formattaDataOra(msg.timestamp)}), in coda ancora ${codaLive.length}`);
        await processaMessaggio(msg, `[live ${stat.live}]`, stat);
    }

    const totaleFinale = await leggiTotale();
    console.log(`\n🏁 Fine recupero ${giorno}`);
    console.log(`   📝 testi con totale: ${stat.testi}`);
    console.log(DRY_RUN
        ? `   📷 candidati mancanti classificati come foto: ${stat.fotoNuove} (non analizzati, non inseriti)`
        : `   📷 foto nuove: ${stat.fotoNuove} (con birra: ${stat.fotoConBirra})`);
    console.log(`   🎬 video (5pt): ${stat.video}`);
    console.log(`   📡 messaggi live gestiti durante il recupero: ${stat.live}`);
    console.log(`   ⏭️ già nel DB: ${stat.giaPresenti} | ⚠️ media non scaricabili: ${stat.mediaNonScaricabili}`);
    console.log(`   ⏸️ foto messe in attesa (AI non disponibile): ${stat.erroriAI}`);
    console.log(`   🏆 Totale: ${totaleIniziale} → ${totaleFinale}`);

    if (!DRY_RUN && (stat.fotoNuove || stat.video || totaleFinale !== totaleIniziale)) {
        await sincronizzaGit(`🤖 Recupero giornata ${giorno}: totale a ${totaleFinale}`);
    }
}

// ==========================================
// CLIENT WHATSAPP (stessa sessione e stesse opzioni di bot.js)
// ==========================================
const lock = '.wwebjs_auth/session/SingletonLock';
if (fs.existsSync(lock)) {
    console.log(`⚠️ Trovato ${lock}: se BeerBot è ancora in esecuzione (pm2 stop BeerBot) Chromium non partirà.`);
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        executablePath: '/usr/bin/chromium', ignoreHTTPSErrors: true, acceptInsecureCerts: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--ignore-certificate-errors']
    }
});

client.on('qr', async () => {
    console.log('🔐 La sessione salvata non è valida: serve una scansione QR. Falla riavviando il bot (pm2 start BeerBot), poi rilancia questo script. Esco.');
    try { await client.destroy(); } catch (e) {}
    process.exit(1);
});

client.on('auth_failure', (msg) => {
    console.error('❌ Auth failure:', msg);
    process.exit(1);
});

// Stesso evento usato da bot.js. Qui NON processo subito: accodo e basta, così lo storico
// viene elaborato in ordine e i live vengono presi dopo, senza doppioni (idVisti).
client.on('message_create', (msg) => {
    if (!msg || !msg.from) return;
    if (['notification', 'revoked', 'reaction'].includes(msg.type)) return;
    codaLive.push(msg);
});

client.on('ready', async () => {
    console.log(`✅ Connesso come ${client.info.wid.user}`);
    let codice = 0;
    try {
        await processaGiornata(client);
    } catch (e) {
        console.log('❌ Errore:', e.message);
        codice = 1;
    } finally {
        try { await client.destroy(); } catch (e) {}
        try { await db.close(); } catch (e) {}
        process.exit(codice);
    }
});

// ==========================================
// AVVIO
// ==========================================
(async () => {
    await initDatabase();
    client.initialize();
})();
