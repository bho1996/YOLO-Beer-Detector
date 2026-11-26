<script setup lang="ts">
import { computed, ref } from 'vue'
import type { View } from '../lib/view'
import { dayStart } from '../lib/view'
import { leaderboard, streaks, binges, milestones, deathRow } from '../lib/stats'
import { lbCols, type Col } from '../lib/columns'
import { fmtDay, fmtDateTime, weekdayOf, monthKey, MIN_PER_DAY } from '../lib/time'
import { CONFIG } from '../config'
import DataTable from './DataTable.vue'

const props = defineProps<{ v: View }>()
const emit = defineEmits<{ player: [u: number] }>()

type Period = 'all' | 'month' | 'week' | 'fame' | 'death'
const period = ref<Period>('all')
const q = ref('')
const deathMonths = ref(3)
const deathShowAll = ref(false)

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
const death = computed(() => deathRow(props.v.rows, props.v.data.members, props.v.data.memberSnapshot,
                                      props.v.refDay, deathMonths.value, props.v.data.users))
const deathCols: Col[] = [
  { key: 'name', label: 'Drinker', fmt: (n: string, row: any) => `${row.admin ? '⭐ ' : ''}${n}` },
  { key: 'status', label: 'Status' },
  { key: 'monthsSilent', label: 'Months silent', num: true, fmt: (v: number | null) => v == null ? 'never' : v.toLocaleString('en-US'), sortVal: (r: any) => r.monthsSilent ?? Infinity },
  { key: 'lastUpload', label: 'Last upload', sortVal: (r: any) => r.lastDay ?? -Infinity },
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
    <button :class="{ active: period === 'death' }" @click="period = 'death'">💀 Death Row</button>
  </div>

  <div v-if="period === 'all' || period === 'month' || period === 'week'" class="card">
    <input v-model="q" type="search" placeholder="🔎 Search a drinker or a country…" style="margin-bottom:12px" />
    <DataTable :cols="lbCols(true)" :rows="filtered" clickable sortable :pageSize="25" @select="r => emit('player', r.u)" />
    <p class="small muted">{{ board.length.toLocaleString('en-US') }} drinkers · photo = 1 point, down video = 5 points · 💛 = project supporter. ↑/↓ = rank change vs the previous period.</p>
  </div>

  <div v-else-if="period === 'death'" class="card">
    <h3>💀 Death Row</h3>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px">
      <label class="small muted" for="death-months">Months of silence: <b>{{ deathMonths }}</b></label>
      <input
        id="death-months"
        :value="deathMonths"
        @input="deathMonths = Number(($event.target as HTMLInputElement).value)"
        @change="deathMonths = Number(($event.target as HTMLInputElement).value)"
        type="range"
        min="1"
        max="12"
        step="1"
        style="accent-color:var(--amber);flex:0 1 220px"
      />
      <span class="small muted"><b>{{ death.candidates.length.toLocaleString('en-US') }}</b> candidates · no beer since <b>{{ fmtDay(death.cutoff) }}</b></span>
    </div>
    <p class="small muted" v-if="death.known">
      Membership from the bot snapshot of <b>{{ v.data.memberSnapshot }}</b> ({{ death.inGroup }} members). Only people confirmed in the group are listed.
    </p>
    <p class="small muted" v-else>No membership snapshot yet: this list is built from uploads only.</p>
    <p v-if="!death.candidates.length" class="small">Nobody on death row. The group is alive and drinking! 🍻</p>
    <template v-else>
      <button class="btn sm" style="margin-bottom:8px" @click="deathShowAll = !deathShowAll">
        {{ deathShowAll ? 'Show 10 at a time' : `Show all ${death.candidates.length.toLocaleString('en-US')}` }}
      </button>
      <DataTable :cols="deathCols" :rows="death.candidates" :pageSize="10" sortable :showAll="deathShowAll" />
    </template>
    <details v-if="death.gone.length" style="margin-top:12px">
      <summary class="small">👻 Already gone: {{ death.gone.length }} former drinkers no longer in the group</summary>
      <DataTable :cols="deathCols" :rows="death.gone" :pageSize="10" sortable :showAll="deathShowAll" />
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
