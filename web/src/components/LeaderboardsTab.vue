<script setup lang="ts">
import { computed, ref } from 'vue'
import type { View } from '../lib/view'
import { dayStart } from '../lib/view'
import { leaderboard, streaks, binges, milestones } from '../lib/stats'
import { lbCols, type Col } from '../lib/columns'
import { fmtDay, fmtDateTime, weekdayOf, monthKey } from '../lib/time'
import { CONFIG } from '../config'
import DataTable from './DataTable.vue'

const props = defineProps<{ v: View }>()
const emit = defineEmits<{ player: [u: number] }>()

type Period = 'all' | 'month' | 'week' | 'fame'
const period = ref<Period>('all')
const q = ref('')

const board = computed(() => {
  const { rows, refDay, refT } = props.v
  if (period.value === 'all') return props.v.lb
  if (period.value === 'week') {
    const from = dayStart(refDay - weekdayOf(refDay))
    return leaderboard(rows.filter(r => r.t >= from), props.v.data.users)
  }
  const mk = monthKey(refT)
  return leaderboard(rows.filter(r => monthKey(r.t) === mk), props.v.data.users)
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
const ms = computed(() => milestones(props.v.rows, props.v.ghost, CONFIG.milestoneStep))
const msCols: Col[] = [
  { key: 'value', label: 'Milestone', fmt: (v: number) => `🎯 ${v.toLocaleString('en-US')}` },
  { key: 'name', label: 'Sniper' },
  { key: 't', label: 'When', fmt: (t: number) => fmtDateTime(t) },
]
</script>

<template>
  <div class="tabs sub">
    <button :class="{ active: period === 'all' }" @click="period = 'all'">🏆 All-time</button>
    <button :class="{ active: period === 'month' }" @click="period = 'month'">🗓️ This month</button>
    <button :class="{ active: period === 'week' }" @click="period = 'week'">📅 This week</button>
    <button :class="{ active: period === 'fame' }" @click="period = 'fame'">🏛️ Hall of Fame</button>
  </div>

  <div v-if="period !== 'fame'" class="card">
    <input v-model="q" type="search" placeholder="🔎 Search a drinker or a country…" style="margin-bottom:12px" />
    <DataTable :cols="lbCols(true)" :rows="filtered" clickable sortable :pageSize="25" @select="r => emit('player', r.u)" />
    <p class="small muted">{{ board.length.toLocaleString('en-US') }} drinkers · photo = 1 point, down video = 5 points.</p>
  </div>

  <div v-else class="grid g2">
    <div class="card"><h3>🔥 Longest streaks ever</h3>
      <DataTable :cols="streakCols" :rows="withName(st.best)" clickable @select="r => emit('player', r.u)" /></div>
    <div class="card"><h3>⚡ Active streaks</h3>
      <DataTable :cols="activeCols" :rows="withName(st.active)" clickable @select="r => emit('player', r.u)" /></div>
    <div class="card"><h3>🍻 Biggest single-day sessions</h3>
      <DataTable :cols="bingeCols" :rows="withName(binges(v.rows))" clickable @select="r => emit('player', r.u)" /></div>
    <div class="card"><h3>🎯 Milestone snipers (every {{ CONFIG.milestoneStep }})</h3>
      <DataTable :cols="msCols" :rows="withName(ms)" clickable :pageSize="10" @select="r => emit('player', r.u)" /></div>
  </div>
</template>
