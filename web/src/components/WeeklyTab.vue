<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { View } from '../lib/view'
import { lbCols, type Col } from '../lib/columns'
import { fmt } from '../lib/time'
import DataTable from './DataTable.vue'

defineProps<{ v: View }>()
const report = ref<any>(null)
const error = ref('')

onMounted(async () => {
  try {
    const res = await fetch(`weekly.json?ts=${Date.now()}`, { cache: 'no-store' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    report.value = await res.json()
  } catch (e) {
    error.value = String(e)
  }
})

const board = computed(() => report.value?.leaderboard ?? [])
const overtakes = computed(() => (report.value?.overtakes ?? []).map((e: any) => ({
  when: e.at, by: e.by, over: e.over, file: e.file,
})))
const milestones = computed(() => report.value?.milestones ?? [])
const overCols: Col[] = [
  { key: 'when', label: 'When' },
  { key: 'by', label: 'Climber' },
  { key: 'over', label: 'Passed' },
  { key: 'file', label: 'Evidence' },
]
const msCols: Col[] = [
  { key: 'value', label: 'Milestone' },
  { key: 'name', label: 'Sniper' },
  { key: 'at', label: 'When' },
]
</script>

<template>
  <div v-if="error" class="card banner dry">Weekly report unavailable ({{ error }}).</div>
  <div v-else-if="!report" class="card banner">Loading the weekly report…</div>
  <template v-else>
    <div class="card">
      <h3>📰 Weekly report · {{ report.label }}</h3>
      <pre class="report-text">{{ report.message }}</pre>
    </div>
    <div class="grid g2">
      <div class="card">
        <h3>🏆 Top drinkers of the week</h3>
        <DataTable :cols="lbCols()" :rows="board" :pageSize="10" />
        <p class="small muted">↑/↓ = rank change vs the previous week.</p>
      </div>
      <div class="card">
        <h3>⚔️ Overtakes</h3>
        <DataTable :cols="overCols" :rows="overtakes" :pageSize="10" />
        <p class="small muted">Only overtakes that lasted until the end of the week are shown.</p>
      </div>
      <div class="card">
        <h3>🎯 Milestones reached</h3>
        <DataTable v-if="milestones.length" :cols="msCols" :rows="milestones" :pageSize="10" />
        <p v-else class="small muted">No milestone reached this week.</p>
        <p class="small muted">Milestone times are approximate: the official total has no history.</p>
      </div>
      <div class="card">
        <h3>🤖 Ghost beers</h3>
        <p>{{ fmt(report.ghost) }} beers are in the official total but not tracked by the bot: they come from the pre-bot era and from numbers written by the group in chat. They cannot be attributed to a drinker.</p>
        <p class="small muted">This week: {{ fmt(report.beers) }} beers · {{ fmt(report.videos) }} videos · {{ fmt(report.zero_photos) }} photos at zero points.</p>
      </div>
    </div>
  </template>
</template>

<style scoped>
.report-text { white-space: pre-wrap; font: inherit; margin: 0; }
</style>
