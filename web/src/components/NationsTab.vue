<script setup lang="ts">
import { computed } from 'vue'
import type { View } from '../lib/view'
import type { Col } from '../lib/columns'
import { base, axisStyle, AMBER } from '../lib/charts'
import DataTable from './DataTable.vue'
import EChart from './EChart.vue'

const props = defineProps<{ v: View }>()

const nations = computed(() => {
  const m = new Map<string, { nation: string; score: number; beers: number; drinkers: number; top: string; topScore: number }>()
  for (const e of props.v.lb) {
    const n = m.get(e.nation) || { nation: e.nation, score: 0, beers: 0, drinkers: 0, top: '', topScore: -1 }
    n.score += e.score
    n.beers += e.pints + e.downs
    n.drinkers++
    if (e.score > n.topScore) { n.topScore = e.score; n.top = e.name }
    m.set(e.nation, n)
  }
  return [...m.values()].sort((a, b) => b.score - a.score).map((n, i) => ({ ...n, rank: i + 1, avg: n.score / n.drinkers }))
})

const cols: Col[] = [
  { key: 'rank', label: '#' },
  { key: 'nation', label: 'Nation' },
  { key: 'score', label: 'Score', num: true },
  { key: 'beers', label: 'Beers', num: true },
  { key: 'drinkers', label: 'Drinkers', num: true },
  { key: 'avg', label: 'Avg / drinker', num: true, fmt: (v: number) => v.toFixed(1) },
  { key: 'top', label: 'Top drinker' },
]

const opt = computed(() => {
  const top = nations.value.slice(0, 15).reverse()
  return {
    ...base,
    tooltip: { ...base.tooltip, axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', ...axisStyle },
    yAxis: { type: 'category', data: top.map(n => n.nation), ...axisStyle, splitLine: { show: false } },
    series: [{ type: 'bar', name: 'Score', data: top.map(n => n.score), itemStyle: { color: AMBER, borderRadius: [0, 4, 4, 0] } }],
  }
})
</script>

<template>
  <div class="grid g2">
    <div class="card"><h3>🌍 Top 15 nations</h3><EChart :option="opt" height="460px" /></div>
    <div class="card"><h3>🏳️ All nations</h3>
      <DataTable :cols="cols" :rows="nations" sortable :pageSize="20" />
      <p class="small muted">Nation comes from the phone prefix (numbers are masked).</p>
    </div>
  </div>
</template>
