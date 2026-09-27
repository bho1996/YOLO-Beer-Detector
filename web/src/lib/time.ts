// Tutti i tempi sono "minuti dall'epoch in ora locale Europe/Rome" (naive).
// Si usano SOLO i metodi getUTC* così il fuso del browser non conta.
export const MIN_PER_DAY = 1440
export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
export const WEEKDAYS_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const dayOf = (t: number) => Math.floor(t / MIN_PER_DAY)
export const hourOf = (t: number) => Math.floor((t % MIN_PER_DAY) / 60)
/** 0 = Monday (1970-01-01 era giovedì) */
export const weekdayOf = (day: number) => (day + 3) % 7

const d = (t: number) => new Date(t * 60000)
const pad = (n: number) => String(n).padStart(2, '0')

/** "adesso" a Roma, come minuti naive */
export function romeNow(): number {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date()).map(p => [p.type, p.value]),
  )
  return Math.floor(Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute) / 60000)
}

/** unix (secondi, UTC reale) -> minuti naive Roma */
export function unixToRome(sec: number): number {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date(sec * 1000)).map(p => [p.type, p.value]),
  )
  return Math.floor(Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute) / 60000)
}

export const fmtTime = (t: number) => `${pad(d(t).getUTCHours())}:${pad(d(t).getUTCMinutes())}`
export const fmtDay = (day: number, year = true) => {
  const x = d(day * MIN_PER_DAY)
  return `${x.getUTCDate()} ${MONTHS[x.getUTCMonth()]}${year ? ' ' + x.getUTCFullYear() : ''}`
}
export const fmtDateTime = (t: number) => `${fmtDay(dayOf(t))}, ${fmtTime(t)}`
export const isoDay = (day: number) => d(day * MIN_PER_DAY).toISOString().slice(0, 10)
export const dayFromIso = (s: string) => Math.floor(Date.parse(s + 'T00:00:00Z') / 86400000)
export const monthKey = (t: number) => { const x = d(t); return `${x.getUTCFullYear()}-${pad(x.getUTCMonth() + 1)}` }
export const fmtMonthYear = (t: number) => { const x = d(t); return `${MONTHS[x.getUTCMonth()]} ${x.getUTCFullYear()}` }

export const fmt = (n: number, digits = 0) =>
  n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })
