import type { Row, User, Member } from './data'
import { dayOf, hourOf, weekdayOf, fmtDay, fmtDateTime, monthKey, dayFromIso, MIN_PER_DAY } from './time'

export interface LbEntry {
  rank: number; u: number; name: string; flag: string; nation: string
  score: number; pints: number; downs: number; uploads: number; delta: number
}

export function sumBeers(rows: Row[], from = -Infinity, to = Infinity): number {
  let s = 0
  for (const r of rows) if (r.t >= from && r.t < to) s += r.beers
  return s
}

export function leaderboard(rows: Row[], users: User[], referenceRows: Row[] = []): LbEntry[] {
  const m = new Map<number, LbEntry>()
  for (const r of rows) {
    let e = m.get(r.u)
    if (!e) {
      const us = users[r.u]
      e = { rank: 0, u: r.u, name: us.name, flag: us.flag, nation: us.nation, score: 0, pints: 0, downs: 0, uploads: 0, delta: 0 }
      m.set(r.u, e)
    }
    e.score += r.score
    e.uploads++
    if (r.video) e.downs++
    else e.pints += r.beers
  }
  const lb = [...m.values()].sort((a, b) => b.score - a.score || a.name.localeCompare(b.name))
  lb.forEach((e, i) => { e.rank = i + 1 })
  if (referenceRows.length) {
    const prev = leaderboard(referenceRows, users)
    const ranks = new Map(prev.map(e => [e.u, e.rank]))
    for (const e of lb) e.delta = (ranks.get(e.u) ?? 0) - e.rank
  }
  return lb
}

/** Serie giornaliera continua [giorno, birre] (giorni vuoti = 0). */
export function dailySeries(rows: Row[], lastDay?: number): [number, number][] {
  if (!rows.length) return []
  const m = new Map<number, number>()
  for (const r of rows) m.set(r.day, (m.get(r.day) || 0) + r.beers)
  const first = rows[0].day
  const last = lastDay ?? rows[rows.length - 1].day
  const out: [number, number][] = []
  for (let d = first; d <= last; d++) out.push([d, m.get(d) || 0])
  return out
}

export function rollingAvg(values: number[], w = 7): number[] {
  const out: number[] = []
  let s = 0
  values.forEach((v, i) => { s += v; if (i >= w) s -= values[i - w]; out.push(s / Math.min(i + 1, w)) })
  return out
}

export interface Streak { u: number; length: number; last: number }
export function streaks(rows: Row[], refDay: number) {
  const days = new Map<number, Set<number>>()
  for (const r of rows) { if (!days.has(r.u)) days.set(r.u, new Set()); days.get(r.u)!.add(r.day) }
  const best: Streak[] = [], active: Streak[] = []
  for (const [u, set] of days) {
    const ds = [...set].sort((a, b) => a - b)
    let run = 1, bestRun = 1, bestLast = ds[0]
    for (let i = 1; i < ds.length; i++) {
      run = ds[i] - ds[i - 1] === 1 ? run + 1 : 1
      if (run > bestRun) { bestRun = run; bestLast = ds[i] }
    }
    best.push({ u, length: bestRun, last: bestLast })
    const lastDay = ds[ds.length - 1]
    if (refDay - lastDay <= 1 && run >= 2) active.push({ u, length: run, last: lastDay })
  }
  best.sort((a, b) => b.length - a.length)
  active.sort((a, b) => b.length - a.length)
  return { best: best.slice(0, 10), active: active.slice(0, 10) }
}

export interface Milestone { value: number; u: number; t: number }
export function milestones(rows: Row[], ghost: number, step: number, overrides: Record<number, number> = {}): Milestone[] {
  const out: Milestone[] = []
  let running = ghost
  let next = (Math.floor(ghost / step) + 1) * step
  for (const r of rows) {
    running += r.beers
    while (running >= next) { out.push({ value: next, u: overrides[next] ?? r.u, t: r.t }); next += step }
  }
  return out.reverse()
}

export function hourWeekHeatmap(rows: Row[]): number[][] {
  const hm = Array.from({ length: 7 }, () => new Array(24).fill(0))
  for (const r of rows) hm[weekdayOf(r.day)][hourOf(r.t)] += r.beers
  return hm
}

export function monthlyTotals(rows: Row[]): [string, number][] {
  const m = new Map<string, number>()
  for (const r of rows) { const k = monthKey(r.t); m.set(k, (m.get(k) || 0) + r.beers) }
  return [...m.entries()]
}

export function communityGrowth(rows: Row[], members: Member[] = [], refDay = 0): [number, number][] {
  if (!members.length) {
    const seen = new Set<number>(), out: [number, number][] = []
    for (const r of rows) {
      if (!seen.has(r.u)) {
        seen.add(r.u)
        if (out.length && out[out.length - 1][0] === r.day) out[out.length - 1][1] = seen.size
        else out.push([r.day, seen.size])
      }
    }
    return out
  }
  const changes = new Map<number, number>()
  for (const m of members) {
    const first = dayFromIso(m.first), last = dayFromIso(m.last)
    changes.set(first, (changes.get(first) || 0) + 1)
    changes.set(last + 1, (changes.get(last + 1) || 0) - 1)
  }
  const days = [...changes.keys()]
  const start = Math.min(...days)
  const end = refDay > 0 ? refDay : Math.max(...days)
  const out: [number, number][] = []
  let count = 0
  for (let d = start; d <= end; d++) {
    count += changes.get(d) || 0
    out.push([d, count])
  }
  return out
}

export function binges(rows: Row[], n = 10) {
  const m = new Map<string, { u: number; day: number; score: number }>()
  for (const r of rows) {
    const k = `${r.u}|${r.day}`
    const e = m.get(k) || { u: r.u, day: r.day, score: 0 }
    e.score += r.score
    m.set(k, e)
  }
  return [...m.values()].sort((a, b) => b.score - a.score).slice(0, n)
}

export function nerdStats(rows: Row[], users: User[], n = 10) {
  const m = new Map<number, { u: number; beers: number; uploads: number }>()
  for (const r of rows) {
    const e = m.get(r.u) || { u: r.u, beers: 0, uploads: 0 }
    e.beers += r.beers; e.uploads++
    m.set(r.u, e)
  }
  return [...m.values()].filter(e => e.uploads >= 10)
    .map(e => ({ ...e, name: users[e.u]?.name ?? '?', flag: users[e.u]?.flag ?? '🍺',
                 avg: Math.round(e.beers / e.uploads * 100) / 100 }))
    .sort((a, b) => b.avg - a.avg).slice(0, n)
}

export function deathRow(rows: Row[], members: Member[], snapshot: string, refDay: number, months: number, users: User[]) {
  const cutoff = refDay - Math.round(months * 30.4)
  const activity = new Map<number, { last: number | null; uploads: number }>()
  for (const r of rows) {
    const e = activity.get(r.u) || { last: null, uploads: 0 }
    e.uploads++
    if (e.last == null || r.day > e.last) e.last = r.day
    activity.set(r.u, e)
  }
  const idx = new Map(users.map((u, i) => [u.name, i]))
  const memberByName = new Map(members.map(m => [m.name, m]))
  const known = !!snapshot && members.length > 0
  const nameOf = (u: number) => users[u]?.name ?? '?'
  const flagOf = (u: number) => users[u]?.flag ?? '🍺'
  const candidates: any[] = []
  const gone: any[] = []

  function consider(u: number, name: string, member?: Member) {
    const a = activity.get(u)
    const last = a?.last ?? null
    const inGroup = known && !!member ? member.last === snapshot : null
    const status = inGroup === null ? 'Unknown' : inGroup ? 'In group' : 'Left'
    const firstDay = member ? dayFromIso(member.first) : null
    const inactive = last !== null && last < cutoff
    const silent = last === null && firstDay !== null && firstDay < cutoff
    const entry = {
      u, name, flag: flagOf(u), status, uploads: a?.uploads ?? 0,
      monthsSilent: last === null ? null : Math.round((refDay - last) / 30.4 * 10) / 10,
      lastUpload: last === null ? 'never' : fmtDay(last),
      seenSince: member?.first ?? '?', admin: !!member?.admin,
    }
    if (status === 'Left' && a) gone.push(entry)
    else if (inactive || silent) candidates.push(entry)
  }

  for (const [u] of activity) {
    if (memberByName.has(nameOf(u))) continue
    consider(u, nameOf(u))
  }
  for (const m of members) consider(idx.get(m.name) ?? -1, m.name, m)
  candidates.sort((a, b) => (b.monthsSilent ?? Infinity) - (a.monthsSilent ?? Infinity) || b.uploads - a.uploads)
  return { candidates, gone, known, inGroup: members.filter(m => m.last === snapshot).length }
}

export function badges(rows: Row[]): string[] {
  if (!rows.length) return []
  const out: string[] = []
  const beers = rows.reduce((s, r) => s + r.beers, 0)
  const videos = rows.filter(r => r.video).length
  for (const [thr, b] of [[1, '🍺 First Sip'], [50, '🍻 Regular'], [100, '💯 Centurion'], [200, '🏆 Double Century'],
    [500, '👑 Half-K Legend'], [1000, '💎 The 1000 Club']] as const) if (beers >= thr) out.push(b)
  for (const [thr, b] of [[1, '🎬 First Down'], [5, '🎥 Action Hero'], [15, '🤙 Down Machine']] as const)
    if (videos >= thr) out.push(b)
  if (rows.length >= 30) out.push('📸 Paparazzo')
  if (rows.length >= 100) out.push('📷 Influencer')
  const hours = rows.map(r => hourOf(r.t))
  if (hours.some(h => h <= 5)) out.push('🌙 Night Owl')
  if (hours.some(h => h >= 6 && h <= 9)) out.push('🌅 Breakfast Champ')
  if (hours.some(h => h >= 11 && h <= 13)) out.push('🍔 Lunch Break Legend')
  if (rows.length > 5 && rows.filter(r => weekdayOf(r.day) >= 5).length / rows.length > 0.6) out.push('🎉 Weekend Warrior')
  if (new Set(rows.map(r => r.day)).size >= 30) out.push('📅 Loyal Liver (30+ days)')
  return out
}

export function playerProfile(rows: Row[]) {
  const perDay = new Map<number, number>()
  const hourCount = new Array(24).fill(0)
  for (const r of rows) { perDay.set(r.day, (perDay.get(r.day) || 0) + r.score); hourCount[hourOf(r.t)]++ }
  let bestDay = rows[0].day, bestPts = 0
  for (const [d, p] of perDay) if (p > bestPts) { bestPts = p; bestDay = d }
  const favHour = hourCount.indexOf(Math.max(...hourCount))
  let cum = 0
  const curve = rows.map(r => [r.t * 60000, (cum += r.score)] as [number, number])
  return { first: rows[0].t, activeDays: perDay.size, favHour, bestDay, bestPts, curve }
}

export function funFacts(total: number, pintPrice: number) {
  const liters = total * 0.568
  return { liters, bathtubs: liters / 150, kcal: total * 215, bigMacs: total * 215 / 550, money: total * pintPrice }
}

export const fmtMilestoneDate = (t: number) => fmtDateTime(t)
export const dayLabel = (day: number) => fmtDay(day)
export const endOfDay = (day: number) => day * MIN_PER_DAY + MIN_PER_DAY - 1
export { dayOf }
