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
const SALTO_MAX_SICUREZZA = 150;    // un SINGOLO messaggio non può alzare il totale di più di così
                                    // (salti più grandi solo con consenso di più messaggi, vedi sync)
const SYNC_FINESTRA = 3000;         // il sync considera valori entro ±3000 dal totale del DB
const SYNC_CONSENSO_MIN = 3;        // messaggi concordi necessari per correzioni > 100
const SYNC_CONSENSO_TOLL = 30;      // "concordi" = entro 30 birre l'uno dall'altro
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
        // 1) commit locale  2) pull dei commit fatti da altri PC (es. modifiche al codice dal Mac)
        //    -X ours: in caso di conflitto sul DB vince SEMPRE la copia del NAS (quella viva)
        // 3) push. Senza il pull, un solo commit esterno blocca tutti i push successivi.
        const cmd = [
            `git add 1m_beers.db`,
            `(git add -A potd 2>/dev/null || true)`,
            `(git diff --cached --quiet || git commit -q -m "${messaggioCommit}")`,
            `(git pull -q --no-rebase --no-edit -X ours origin main || (git merge --abort 2>/dev/null; false))`,
            `git push -q origin main`,
        ].join(' && ');
        exec(cmd, (error, stdout, stderr) => {
            isSyncing = false;
            if (error) console.log("⚠️ Errore Git:", (stderr || error.message).trim());
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
            const output = stdout || '';
            // Prendi l'ULTIMA riga "BEERS_FOUND: n" (quella finale del Notaio, non i debug).
            // null = l'AI NON ha potuto giudicare (quota finita, 404, timeout, crash):
            // ai_judge.py in quel caso stampa [FATAL] ma termina comunque con BEERS_FOUND: 0.
            const occorrenze = [...output.matchAll(/^BEERS_FOUND:\s*(-?\d+)\s*$/gm)];
            const valore = occorrenze.length ? Number(occorrenze[occorrenze.length - 1][1]) : null;
            if (error || /\[FATAL\]|\[ERRORE\].*non esiste/.test(output) || valore === null || valore < 0) {
                const riga = output.split('\n').find(r => /\[FATAL\]|ha fallito|\[ERRORE\]/.test(r)) || '';
                console.log(`⚠️ Analisi AI fallita${error ? ` (${error.message})` : ''}: ${riga.trim().slice(0, 200)}`);
                resolve(null);
                return;
            }
            resolve(valore);
        });
        const timer = setTimeout(() => {
            if (chiuso) return;
            console.log(`⏱️ Timeout AI (${AI_TIMEOUT_MS / 1000}s). Kill.`);
            try { child.kill("SIGKILL"); } catch (e) {}
            chiuso = true;
            resolve(null);
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

        // Raccogli i totali scritti negli ultimi 50 messaggi (1 valore per messaggio: l'ultimo numero)
        const messaggi = await gruppo.fetchMessages({ limit: 50 });
        const totali = [];
        for (const m of messaggi) {
            const match = (m.body || "").match(/\b\d{5,6}\b/g);
            if (match) {
                const v = parseInt(match[match.length - 1]);
                if (v > 10000) totali.push(v);
            }
        }
        if (totali.length === 0) return;

        // Filtro anti-outlier: solo valori entro una finestra plausibile
        const rowTotale = await db.get("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'");
        const dbTotal = rowTotale ? parseInt(rowTotale.valore) : 0;

        const plausibili = totali.filter(v => Math.abs(v - dbTotal) <= SYNC_FINESTRA);
        if (plausibili.length === 0) return;
        plausibili.sort((a, b) => b - a);

        // Consenso: per ogni valore conta quanti messaggi stanno nei 30 sotto di lui.
        // Si sceglie il valore PIÙ ALTO sostenuto da almeno SYNC_CONSENSO_MIN messaggi
        // (il gruppo conta in avanti, quindi i messaggi più recenti hanno i numeri più alti).
        const supporto = v => plausibili.filter(x => x <= v && v - x <= SYNC_CONSENSO_TOLL).length;
        let massimo = plausibili.find(v => supporto(v) >= SYNC_CONSENSO_MIN) ?? null;
        let consensoForte = massimo !== null;

        if (massimo === null) {
            // Fallback (regola storica): massimo + secondo valore entro 10
            massimo = plausibili[0];
            const secondo = plausibili.length > 1 ? plausibili[1] : null;
            if (secondo !== null && (massimo - secondo) > 10) {
                console.log(`🔎 Sync: ${massimo} vs ${secondo} non consensuale. Salto.`);
                return;
            }
        }

        const gap = massimo - dbTotal;

        // CASO 0: scostamento grande (es. un messaggio sbagliato accettato in passato).
        // Si corregge SOLO con consenso forte di più messaggi, in entrambe le direzioni.
        if (Math.abs(gap) > 100) {
            if (!consensoForte) {
                console.log(`🔎 Sync: scostamento ${gap} senza consenso sufficiente. Salto.`);
                return;
            }
            console.log(`🔎 Sync ⚖️: ${supporto(massimo)} messaggi concordano su ~${massimo}. Correggo ${dbTotal} → ${massimo} (${gap > 0 ? '+' : ''}${gap}).`);
            await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('OFFICIAL_TOTAL', ?)", massimo);
            await sincronizzaGit(`🤖 Auto-sync (consenso): totale a ${massimo}`);
            return;
        }

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
            // NB: le righe delle foto NON vengono mai modificate/cancellate.
            // Si aggiorna solo il contatore ufficiale; la dashboard gestisce la differenza.
            console.log(`🔎 Sync ↓: DB ha ${eccesso} punti in più del gruppo. Aggiorno solo il totale ufficiale.`);
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
    // Foto che l'AI non ha potuto giudicare (quota finita, timeout, errore):
    // NON finiscono in log_birre a 0, restano qui finché riprova_foto_in_attesa.py le smaltisce.
    await db.run(`CREATE TABLE IF NOT EXISTS foto_in_attesa (
        nome_file TEXT PRIMARY KEY,
        data_ora TEXT,
        utente TEXT,
        testo TEXT,
        tentativi INTEGER DEFAULT 0,
        ultimo_errore TEXT,
        creato TEXT DEFAULT (datetime('now','localtime'))
    )`);
    // Istantanea giornaliera dei membri del gruppo (per la "Death Row" della dashboard).
    // Si salva SOLO l'etichetta mascherata ("+39 *** 1234"), mai il numero completo:
    // questo DB finisce su GitHub.
    await db.run(`CREATE TABLE IF NOT EXISTS membri_gruppo (
        utente TEXT PRIMARY KEY,
        prima_vista TEXT NOT NULL,
        ultima_vista TEXT NOT NULL,
        admin INTEGER NOT NULL DEFAULT 0
    )`);
    console.log('📦 Database SQLite pronto (WAL mode)');
}

// ==========================================
// MEMBRI DEL GRUPPO: istantanea giornaliera
// ==========================================
function oggiRoma() {
    return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Rome' }); // YYYY-MM-DD
}

async function etichettaPartecipante(partecipante) {
    // Stessa logica di risolviIdentita(), così l'etichetta coincide con quella in log_birre.
    const id = (partecipante && partecipante.id) || {};
    const parteLocale = String(id.user || '');
    const server = String(id.server || '');
    if (!parteLocale) return null;

    if (server === 'c.us') {
        const soloNumeri = parteLocale.replace(/[^0-9]/g, '');
        const pref = estraiPrefisso(soloNumeri);
        if (soloNumeri.length >= 7 && pref !== '+??') return `${pref} *** ${soloNumeri.slice(-4)}`;
    }
    if (cacheIdentita.has(parteLocale)) return cacheIdentita.get(parteLocale);

    try {
        const contact = await client.getContactById(id._serialized || `${parteLocale}@${server}`);
        const grezzo = contact && (contact.number || (contact.id && contact.id.user));
        const soloNumeri = String(grezzo || '').replace(/[^0-9]/g, '');
        const pref = estraiPrefisso(soloNumeri);
        if (soloNumeri.length >= 7 && soloNumeri.length <= 15 && pref !== '+??') {
            const risultato = `${pref} *** ${soloNumeri.slice(-4)}`;
            cacheIdentita.set(parteLocale, risultato);
            return risultato;
        }
    } catch (e) {}

    const cifre = parteLocale.replace(/[^0-9]/g, '');
    const risultato = `🔒 *** ${(cifre || parteLocale).slice(-4)}`;
    cacheIdentita.set(parteLocale, risultato);
    return risultato;
}

async function aggiornaMembriGruppo() {
    try {
        const tutteLeChat = await client.getChats();
        const gruppo = tutteLeChat.find(c => c.name === NOME_GRUPPO_BERSAGLIO);
        if (!gruppo) { console.log('👥 Membri: gruppo non trovato.'); return; }

        let chat = gruppo;
        try { chat = await client.getChatById(gruppo.id._serialized); } catch (e) {}
        const partecipanti = Array.isArray(chat.participants) && chat.participants.length
            ? chat.participants : (gruppo.participants || []);
        if (!partecipanti.length) { console.log('👥 Membri: elenco partecipanti vuoto, salto.'); return; }

        // Guardia: un elenco molto più corto dell'ultima istantanea è quasi certamente
        // un caricamento parziale di WhatsApp, non un'uscita di massa. Non segnare nessuno come uscito.
        const precedente = await db.get("SELECT valore FROM config WHERE chiave='MEMBRI_SNAPSHOT'");
        const snapshotPrecedente = precedente ? String(precedente.valore) : null;
        if (snapshotPrecedente) {
            const row = await db.get('SELECT COUNT(*) AS n FROM membri_gruppo WHERE ultima_vista = ?', [snapshotPrecedente]);
            const nPrec = row ? row.n : 0;
            if (nPrec >= 20 && partecipanti.length < nPrec * 0.5) {
                console.log(`👥 Membri: solo ${partecipanti.length} partecipanti contro ${nPrec} ieri. Elenco parziale? Salto.`);
                return;
            }
        }

        const oggi = oggiRoma();
        const etichette = new Map();
        for (const p of partecipanti) {
            const etichetta = await etichettaPartecipante(p);
            if (!etichetta) continue;
            const admin = Boolean(p.isAdmin || p.isSuperAdmin) ? 1 : 0;
            etichette.set(etichetta, Math.max(admin, etichette.get(etichetta) || 0));
        }

        await db.run('BEGIN IMMEDIATE');
        try {
            for (const [utente, admin] of etichette) {
                await db.run(
                    `INSERT INTO membri_gruppo (utente, prima_vista, ultima_vista, admin) VALUES (?, ?, ?, ?)
                     ON CONFLICT(utente) DO UPDATE SET ultima_vista = excluded.ultima_vista, admin = excluded.admin`,
                    [utente, oggi, oggi, admin]
                );
            }
            await db.run("INSERT OR REPLACE INTO config (chiave, valore) VALUES ('MEMBRI_SNAPSHOT', ?)", [oggi]);
            await db.run('COMMIT');
        } catch (e) {
            await db.run('ROLLBACK');
            throw e;
        }

        const usciti = await db.get('SELECT COUNT(*) AS n FROM membri_gruppo WHERE ultima_vista < ?', [oggi]);
        const nuovi = await db.get('SELECT COUNT(*) AS n FROM membri_gruppo WHERE prima_vista = ?', [oggi]);
        console.log(`👥 Membri: ${etichette.size} nel gruppo oggi | nuovi: ${nuovi ? nuovi.n : 0} | usciti/rimossi finora: ${usciti ? usciti.n : 0}`);
    } catch (e) {
        console.log('⚠️ Istantanea membri fallita:', e.message);
    }
}

async function mettiInAttesa(nome_file, data_ora, utente, testo, motivo) {
    try {
        await db.run(
            `INSERT OR IGNORE INTO foto_in_attesa (nome_file, data_ora, utente, testo, tentativi, ultimo_errore)
             VALUES (?, ?, ?, ?, 1, ?)`,
            [nome_file, data_ora, utente, (testo || "").slice(0, 500), motivo]
        );
        console.log(`⏸️ FOTO IN ATTESA: ${nome_file} (${motivo}). La riprova il job notturno.`);
    } catch (err) {
        console.log("⚠️ Errore DB (foto_in_attesa):", err.message);
    }
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
    // Prima istantanea membri dopo 2 minuti (WhatsApp deve finire di caricare le chat),
    // solo se oggi non è ancora stata fatta: così la Death Row ha dati subito dopo il deploy.
    setTimeout(async () => {
        try {
            const row = await db.get("SELECT valore FROM config WHERE chiave='MEMBRI_SNAPSHOT'");
            if (!row || String(row.valore) !== oggiRoma()) {
                await aggiornaMembriGruppo();
                await sincronizzaGit("👥 Istantanea membri del gruppo");
            }
        } catch (e) { console.log('⚠️ Istantanea membri all\'avvio fallita:', e.message); }
    }, 2 * 60 * 1000);
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
// PICTURE OF THE DAY: pubblica 1 foto (di ieri) per la dashboard
// ==========================================
const POTD_SCRIPT = "/srv/mergerfs/PoolArchivio/YOLO-Beer-Detector/publish_potd.py";
function pubblicaFotoDelGiorno() {
    return new Promise((resolve) => {
        execFile(PYTHON_PATH, [POTD_SCRIPT], { timeout: 60000 }, async (error, stdout) => {
            if (error) console.log("⚠️ POTD fallita:", error.message);
            else {
                console.log(`📸 ${stdout.trim()}`);
                await sincronizzaGit("📸 Picture of the Day");
            }
            resolve();
        });
    });
}

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
        await aggiornaMembriGruppo();      // prima della POTD: così il push include anche i membri
        await pubblicaFotoDelGiorno();
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
                // NB: il vecchio "VAR retroattivo" (scriveva il salto come punti dell'ultima foto
                // dell'autore) è disattivato: ogni foto conta sempre 1, il salto resta solo nel
                // totale ufficiale.
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
                        const conteggio = await runAiJudge(percorso_file, totaleAttuale, testo);
                        if (conteggio === null) {
                            // Nessun verdetto: non è "niente birra", è "non ho potuto guardare".
                            await mettiInAttesa(nome_file, data_ora, autore, testo, "AI non disponibile");
                            return;
                        }
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