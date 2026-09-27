import { ref, shallowRef } from 'vue'
import { CONFIG } from '../config'
import { dayOf } from './time'

export interface User { name: string; nation: string; flag: string }
export interface Row {
  id: number
  t: number        // minuti naive Roma
  day: number
  u: number        // indice utente
  video: boolean
  beers: number    // contributo al totale globale (foto approvata = 1, video = 1)
  score: number    // punti classifica (foto approvata = 1, video = 5)
  punti: number    // valore grezzo salvato nel DB (solo per Data Health)
  file: string
}
export interface Potd { image: string; user: string; time: string; candidates: number }
export interface Report {
  rows: number; ts_fixed: number; swap_fixed: number; unparsable_dates: number
  aliases: Record<string, string>; alias_rows: number; whitespace_fixed: number
  zero_photos: number; photos_multi_pt: number; photos_multi_pt_extra: number
  videos_with_1pt: number; duplicate_files: number
}
export interface Dataset {
  generatedAt: number
  dbUpdatedAt: number
  officialTotal: number
  users: User[]
  rows: Row[]           // ordinate per t
  potd: Record<string, Potd>
  report: Report
}

interface RawData {
  generated_at: number; db_updated_at: number; official_total: number
  users: User[]; potd: Record<string, Potd>; report: Report
  rows: { id: number[]; t: number[]; u: number[]; v: number[]; b: number[]; s: number[]; p: number[]; f: string[] }
}

function parse(raw: RawData): Dataset {
  const r = raw.rows
  const rows: Row[] = r.t.map((t, i) => ({
    id: r.id[i], t, day: dayOf(t), u: r.u[i], video: r.v[i] === 1,
    beers: r.b[i], score: r.s[i], punti: r.p[i], file: r.f[i],
  }))
  rows.sort((a, b) => a.t - b.t || a.id - b.id)
  return {
    generatedAt: raw.generated_at, dbUpdatedAt: raw.db_updated_at, officialTotal: raw.official_total,
    users: raw.users, rows, potd: raw.potd, report: raw.report,
  }
}

/** Carica data.json e lo ricontrolla ogni CONFIG.refreshSeconds (aggiornamento automatico). */
export function useDataset() {
  const data = shallowRef<Dataset | null>(null)
  const error = ref<string | null>(null)
  const lastCheck = ref(0)

  async function load() {
    try {
      const res = await fetch(`data.json?ts=${Date.now()}`, { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const raw: RawData = await res.json()
      if (!data.value || raw.generated_at !== data.value.generatedAt) data.value = parse(raw)
      error.value = null
    } catch (e) {
      if (!data.value) error.value = String(e)
    } finally {
      lastCheck.value = Date.now()
    }
  }
  load()
  setInterval(() => { if (document.visibilityState === 'visible') load() }, CONFIG.refreshSeconds * 1000)
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') load() })
  return { data, error, lastCheck, reload: load }
}

/** Indice dell'ultima riga con t <= limit (ricerca binaria). Ritorna il numero di righe incluse. */
export function cutoff(rows: Row[], limit: number): number {
  let lo = 0, hi = rows.length
  while (lo < hi) { const m = (lo + hi) >> 1; if (rows[m].t <= limit) lo = m + 1; else hi = m }
  return lo
}
