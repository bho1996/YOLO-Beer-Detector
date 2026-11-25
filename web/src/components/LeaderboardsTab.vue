<script setup lang="ts">
import { computed, ref } from 'vue'
import type { View } from '../lib/view'
import { dayStart } from '../lib/view'
import { leaderboard, streaks, binges, milestones, wallOfShame, nerdStats, deathRow } from '../lib/stats'
import { lbCols, type Col } from '../lib/columns'
import { fmtDay, fmtDateTime, weekdayOf, monthKey, MIN_PER_DAY } from '../lib/time'
import { CONFIG } from '../config'
import DataTable from './DataTable.vue'

const props = defineProps<{ v: View }>()
const emit = defineEmits<{ player: [u: number] }>()

type Period = 'all' | 'month' | 'week' | 'fame' | 'shame' | 'nerd' | 'death'
const period = ref<Period>('all')
const q = ref('')
const deathMonths = ref(3)

const board = computed(() => {
  const { rows, refDay, refT } = props.v
  if (period.value === 'all') return props.v.lb
  if (period.value === 'week') {
    const from = dayStart(refDay - weekdayOf(refDay))
    const reference = rows.filter(r => r.t >= from - 7 * MIN_PER_DAY && r.t < from)
    return leaderboard(rows.filter(r => r.t >= from), props.v.data.users, reference)
  }
  const mk = monthKey(refT)
  const current = rows.filter(r => monthKey(r.t) === mk)
  const reference = current.length ? rows.filter(r => monthKey(r.t) === monthKey(current[0].t - 1)) : []
  return leaderboard(current, props.v.data.users, reference)
})
const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  return s ? board.value.filter(e => e.name.toLowerCase().includes(s) || e.nation.toLowerCase().includes(s)) : board.value
})

const st = computed(() => streaks(props.v.rows, props.v.refDay))
const withName = <T extends { u: number }>(xs: T[]) => xs.map(x => ({ ...x, name: `${props.v.flag(x.u)}  ${props.v.name(x.u)}` }))
const streakCols: Col[] = [{ key: 'name', label: 'Drinker' }, { key: 'length', label: 'Days in a row', num: true }]
const activeCols: Col[] = [...streakCols, { key: 'last', label: 'Last beer', fmt: (d: number) => fmtDay(d, false) }]
const bingeCols: Col[] = [{ key: 'name', label: 'Drinker' }, { key: 'day', label: 'Day', fmt: (d: number) => fmtDay(d) }, { key: 'score', label: 'Points', num: true }]
const ms = computed(() => milestones(props.v.rows, props.v.ghost, CONFIG.milestoneStep, props.v.milestoneSnipers))
const sniperKings = computed(() => {
  const m = new Map<number, { u: number; name: string; n: number }>()
  for (const e of ms.value) {
    const cur = m.get(e.u) || { u: e.u, name: props.v.name(e.u), n: 0 }
    cur.n++; m.set(e.u, cur)
  }
  return [...m.values()].sort((a, b) => b.n - a.n)
})
const kingCols: Col[] = [
  { key: 'name', label: 'Sniper' },
  { key: 'n', label: 'Milestones', num: true },
]
const msCols: Col[] = [
  { key: 'value', label: 'Milestone', fmt: (v: number) => `🎯 ${v.toLocaleString('en-US')}` },
  { key: 'name', label: 'Sniper' },
  { key: 't', label: 'When', fmt: (t: number) => fmtDateTime(t) },
]
const shame = computed(() => wallOfShame(props.v.rows, props.v.refDay, props.v.data.users))
const shameCols: Col[] = [
  { key: 'name', label: 'Drinker', fmt: (n: string, row: any) => `${row.flag}  ${n}` },
  { key: 'daysMIA', label: 'Days MIA', num: true },
  { key: 'uploads', label: 'Uploads', num: true },
  { key: 'lastSeen', label: 'Last seen' },
]
const nerd = computed(() => nerdStats(props.v.rows, props.v.data.users))
const nerdCols: Col[] = [
  { key: 'name', label: 'Drinker', fmt: (n: string, row: any) => `${row.flag}  ${n}` },
  { key: 'avg', label: 'Avg beers / upload', num: true },
  { key: 'uploads', label: 'Uploads', num: true },
]
const death = computed(() => deathRow(props.v.rows, props.v.data.members, props.v.data.memberSnapshot,
                                      props.v.refDay, deathMonths.value, props.v.data.users))
const deathCols: Col[] = [
  { key: 'name', label: 'Drinker', fmt: (n: string, row: any) => `${row.admin ? '⭐ ' : ''}${n}` },
  { key: 'status', label: 'Status' },
  { key: 'monthsSilent', label: 'Months silent', num: true },
  { key: 'lastUpload', label: 'Last upload' },
  { key: 'seenSince', label: 'Seen since' },
  { key: 'uploads', label: 'Uploads', num: true },
]
</script>

<template>
  <div class="tabs sub">
    <button :class="{ active: period === 'all' }" @click="period = 'all'">🏆 All-time</button>
    <button :class="{ active: period === 'month' }" @click="period = 'month'">🗓️ This month</button>
    <button :class="{ active: period === 'week' }" @click="period = 'week'">📅 This week</button>
    <button :class="{ active: period === 'fame' }" @click="period = 'fame'">🏛️ Hall of Fame</button>
    <button :class="{ active: period === 'shame' }" @click="period = 'shame'">🚨 Wall of Shame</button>
    <button :class="{ active: period === 'nerd' }" @click="period = 'nerd'">🤓 Nerd Stats</button>
    <button :class="{ active: period === 'death' }" @click="period = 'death'">💀 Death Row</button>
  </div>

  <div v-if="period === 'all' || period === 'month' || period === 'week'" class="card">
    <input v-model="q" type="search" placeholder="🔎 Search a drinker or a country…" style="margin-bottom:12px" />
    <DataTable :cols="lbCols(true)" :rows="filtered" clickable sortable :pageSize="25" @select="r => emit('player', r.u)" />
    <p class="small muted">{{ board.length.toLocaleString('en-US') }} drinkers · photo = 1 point, down video = 5 points. ↑/↓ = rank change vs the previous period.</p>
  </div>

  <div v-else-if="period === 'shame'" class="card">
    <h3>🚨 Wall of Shame</h3>
    <p class="small muted">Regulars (10+ uploads) who have gone quiet for more than 2 days. We're worried. 🥺</p>
    <div v-if="shame.length"><DataTable :cols="shameCols" :rows="shame" :pageSize="10" /></div>
    <p v-else class="small">Everyone is drinking! Great job! 🍻</p>
  </div>

  <div v-else-if="period === 'nerd'" class="card">
    <h3>🤓 Nerd Stats</h3>
    <p class="small muted">Most beers per upload, among regulars (10+ uploads).</p>
    <DataTable :cols="nerdCols" :rows="nerd" :pageSize="10" />
  </div>

  <div v-else-if="period === 'death'" class="card">
    <h3>💀 Death Row</h3>
    <label class="small muted">Months of silence: <b>{{ deathMonths }}</b>
      <input v-model.number="deathMonths" type="range" min="1" max="12" style="vertical-align:middle;margin-left:8px" />
    </label>
    <p class="small muted" v-if="death.known">
      Membership from the bot snapshot of <b>{{ v.data.memberSnapshot }}</b> ({{ death.inGroup }} members). “Unknown” = posted under a label the snapshot can't match.
    </p>
    <p class="small muted" v-else>No membership snapshot yet: this list is built from uploads only.</p>
    <p v-if="!death.candidates.length" class="small">Nobody on death row. The group is alive and drinking! 🍻</p>
    <DataTable v-else :cols="deathCols" :rows="death.candidates" :pageSize="10" />
    <details v-if="death.gone.length" style="margin-top:12px">
      <summary class="small">👻 Already gone: {{ death.gone.length }} former drinkers no longer in the group</summary>
      <DataTable :cols="deathCols" :rows="death.gone" :pageSize="10" />
    </details>
  </div>

  <div v-else-if="period === 'fame'" class="grid g2">
    <div class="card"><h3>🔥 Longest streaks ever</h3>
      <DataTable :cols="streakCols" :rows="withName(st.best)" clickable @select="r => emit('player', r.u)" /></div>
    <div class="card"><h3>⚡ Active streaks</h3>
      <DataTable :cols="activeCols" :rows="withName(st.active)" clickable @select="r => emit('player', r.u)" /></div>
    <div class="card"><h3>🍻 Biggest single-day sessions</h3>
      <DataTable :cols="bingeCols" :rows="withName(binges(v.rows))" clickable @select="r => emit('player', r.u)" /></div>
    <div class="card"><h3>🎯 Milestone snipers (every {{ CONFIG.milestoneStep }})</h3>
      <DataTable :cols="msCols" :rows="withName(ms)" clickable :pageSize="10" @select="r => emit('player', r.u)" /></div>
    <div class="card"><h3>👑 Sniper Kings</h3>
      <DataTable :cols="kingCols" :rows="sniperKings" clickable :pageSize="10" @select="r => emit('player', r.u)" /></div>
  </div>
</template>
