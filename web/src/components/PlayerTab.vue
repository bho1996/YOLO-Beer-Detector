<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { View } from '../lib/view'
import type { Col } from '../lib/columns'
import { badges, playerProfile } from '../lib/stats'
import { base, axisStyle, AMBER } from '../lib/charts'
import { fmt, fmtDay, fmtDateTime, isoDay } from '../lib/time'
import Kpi from './Kpi.vue'
import DataTable from './DataTable.vue'
import EChart from './EChart.vue'

const props = defineProps<{ v: View; player: number | null }>()
const emit = defineEmits<{ player: [u: number | null] }>()

const query = ref('')
watch(() => props.player, u => { query.value = u == null ? '' : props.v.name(u) }, { immediate: true })

const options = computed(() => props.v.lb.map(e => e.name))
function pick() {
  const e = props.v.lb.find(x => x.name === query.value)
  if (e) emit('player', e.u)
}

const entry = computed(() => props.player == null ? null : props.v.lb.find(e => e.u === props.player) ?? null)
const rows = computed(() => props.player == null ? [] : props.v.rows.filter(r => r.u === props.player))
const prof = computed(() => rows.value.length ? playerProfile(rows.value) : null)
const myBadges = computed(() => badges(rows.value))
const gapAbove = computed(() => {
  if (!entry.value || entry.value.rank === 1) return null
  const above = props.v.lb[entry.value.rank - 2]
  return { name: above.name, pts: above.score - entry.value.score }
})

const curveOpt = computed(() => {
  const c = prof.value?.curve ?? []
  return {
    ...base,
    xAxis: { type: 'category', data: rows.value.map(r => isoDay(r.day)), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: 'value', ...axisStyle },
    series: [{ name: 'Score', type: 'line', step: 'end', symbol: 'none', data: c.map(x => x[1]), lineStyle: { color: AMBER, width: 2 },
      areaStyle: { color: 'rgba(255,176,46,.15)' } }],
  }
})

const recentCols: Col[] = [
  { key: 't', label: 'When', fmt: (t: number) => fmtDateTime(t) },
  { key: 'video', label: 'Type', fmt: (v: boolean) => v ? '🎬 Down' : '📸 Photo' },
  { key: 'score', label: 'Points', num: true },
]
const recent = computed(() => [...rows.value].reverse())

const copied = ref(false)
async function share() {
  const url = new URL(location.href)
  url.searchParams.set('player', props.v.name(props.player!))
  try { await navigator.clipboard.writeText(url.toString()); copied.value = true; setTimeout(() => (copied.value = false), 2000) } catch { /* ignore */ }
}
</script>

<template>
  <div class="card">
    <div style="display:flex; gap:10px">
      <input v-model="query" type="search" list="players" placeholder="🔎 Type a drinker (e.g. +39 *** 1234 or a nickname)…" @change="pick" @input="pick" />
      <button v-if="player != null" class="btn sm" @click="share">{{ copied ? '✅ Copied' : '🔗 Share' }}</button>
    </div>
    <datalist id="players"><option v-for="o in options" :key="o" :value="o" /></datalist>
  </div>

  <template v-if="entry && prof">
    <h2 class="section-title mt">{{ entry.flag }} {{ entry.name }} <span class="muted small">{{ entry.nation }}</span></h2>
    <div class="grid g4">
      <Kpi label="🏆 Rank" :value="'#' + fmt(entry.rank)" :deltaLabel="`of ${fmt(v.lb.length)} drinkers`" />
      <Kpi label="⭐ Score" :value="fmt(entry.score)" :deltaLabel="gapAbove ? `${fmt(gapAbove.pts)} pts behind ${gapAbove.name}` : '👑 Leader!'" />
      <Kpi label="🍺 Pints · 🎬 Downs" :value="`${fmt(entry.pints)} · ${fmt(entry.downs)}`" />
      <Kpi label="📅 Active days" :value="fmt(prof.activeDays)" :deltaLabel="`since ${fmtDay(Math.floor(prof.first / 1440))}`" />
    </div>
    <div class="grid g32 mt">
      <div class="card"><h3>📈 Score over time</h3><EChart :option="curveOpt" height="260px" /></div>
      <div class="card">
        <h3>🎖️ Badges</h3>
        <div class="badges"><span v-for="b in myBadges" :key="b" class="badge">{{ b }}</span></div>
        <p class="small muted mt">🕐 Favourite hour: <b>{{ prof.favHour }}:00</b><br />
          🍻 Best day: <b>{{ fmtDay(prof.bestDay) }}</b> ({{ prof.bestPts }} pts)</p>
      </div>
    </div>
    <div class="card mt"><h3>🧾 Uploads</h3><DataTable :cols="recentCols" :rows="recent" :pageSize="10" /></div>
  </template>
  <p v-else class="muted mt">Pick a drinker to see their profile, or click any name in the leaderboards.</p>
</template>
