import type { Dataset, Row } from './data'
import { cutoff } from './data'
import { leaderboard, type LbEntry } from './stats'
import { dayOf, MIN_PER_DAY } from './time'

/** Tutto ciò che i tab devono sapere, calcolato una volta per "istante" della time machine. */
export interface View {
  data: Dataset
  rows: Row[]          // righe fino a refT
  refT: number
  refDay: number
  isLive: boolean
  ghost: number        // birre del gruppo non tracciate dal bot (prima del bot, testo, ecc.)
  total: number        // totale globale all'istante refT
  lb: LbEntry[]
  name: (u: number) => string
  flag: (u: number) => string
  sumDay: (day: number) => number
}

export function buildView(data: Dataset, refT: number, isLive: boolean): View {
  const n = cutoff(data.rows, refT)
  const rows = data.rows.slice(0, n)
  let all = 0
  for (const r of data.rows) all += r.beers
  // Il totale ufficiale arriva dal gruppo (OFFICIAL_TOTAL): la differenza con le birre
  // tracciate è il "ghost" costante, così la serie storica termina esattamente sul totale ufficiale.
  const ghost = Math.max(0, data.officialTotal - all)
  let upTo = 0
  for (const r of rows) upTo += r.beers

  const perDay = new Map<number, number>()
  for (const r of rows) perDay.set(r.day, (perDay.get(r.day) || 0) + r.beers)

  return {
    data, rows, refT, refDay: dayOf(refT), isLive,
    ghost, total: ghost + upTo,
    lb: leaderboard(rows, data.users),
    name: u => data.users[u]?.name ?? '?',
    flag: u => data.users[u]?.flag ?? '🏴‍☠️',
    sumDay: day => perDay.get(day) || 0,
  }
}

export const dayStart = (day: number) => day * MIN_PER_DAY
