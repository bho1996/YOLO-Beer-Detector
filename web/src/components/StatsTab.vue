<script setup lang="ts">
import { computed } from 'vue'
import type { View } from '../lib/view'
import { dailySeries, rollingAvg, hourWeekHeatmap, monthlyTotals, communityGrowth, funFacts } from '../lib/stats'
import { base, axisStyle, AMBER, AMBER2, HEAT } from '../lib/charts'
import { fmt, isoDay, WEEKDAYS } from '../lib/time'
import { CONFIG } from '../config'
import EChart from './EChart.vue'

const props = defineProps<{ v: View }>()

const daily = computed(() => dailySeries(props.v.rows, props.v.refDay))

const dailyOpt = computed(() => {
  const d = daily.value
  const vals = d.map(x => x[1])
  return {
    ...base,
    legend: { top: 0, textStyle: { color: '#b8a58a' } },
    grid: { ...base.grid, top: 34, bottom: 44 },
    xAxis: { type: 'category', data: d.map(x => isoDay(x[0])), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: 'value', ...axisStyle },
    dataZoom: [{ type: 'inside', start: Math.max(0, 100 - 9000 / Math.max(1, d.length)) }, { type: 'slider', height: 18, bottom: 6, borderColor: 'transparent', textStyle: { color: '#b8a58a' } }],
    series: [
      { name: 'Beers per day', type: 'bar', data: vals, itemStyle: { color: AMBER2, borderRadius: [3, 3, 0, 0] } },
      { name: '7-day average', type: 'line', data: rollingAvg(vals).map(x => +x.toFixed(1)), smooth: true, symbol: 'none', lineStyle: { color: '#fff0c2', width: 2 } },
    ],
  }
})

const cumOpt = computed(() => {
  const d = daily.value
  let run = props.v.ghost
  return {
    ...base,
    xAxis: { type: 'category', data: d.map(x => isoDay(x[0])), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: 'value', ...axisStyle, min: (x: { min: number }) => Math.floor(x.min / 1000) * 1000 },
    series: [{
      name: 'Total', type: 'line', symbol: 'none', smooth: true, data: d.map(x => (run += x[1])),
      lineStyle: { color: AMBER, width: 3 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(255,176,46,.35)' }, { offset: 1, color: 'rgba(255,176,46,0)' }] } },
    }],
  }
})

const calOpt = computed(() => {
  const d = daily.value.slice(-371)
  if (!d.length) return {}
  const max = Math.max(1, ...d.map(x => x[1]))
  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'item', formatter: (p: any) => `${p.value[0]}<br/><b>${fmt(p.value[1])}</b> beers` },
    visualMap: { min: 0, max, show: false, inRange: { color: HEAT } },
    calendar: {
      range: [isoDay(d[0][0]), isoDay(d[d.length - 1][0])], top: 28, left: 36, right: 8, cellSize: ['auto', 15],
      itemStyle: { color: '#1b140b', borderColor: '#120d07', borderWidth: 2 }, splitLine: { show: false },
      dayLabel: { color: '#b8a58a', firstDay: 1, nameMap: ['S', 'M', 'T', 'W', 'T', 'F', 'S'] },
      monthLabel: { color: '#b8a58a' }, yearLabel: { show: false },
    },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', data: d.map(x => [isoDay(x[0]), x[1]]) }],
  }
})

const hourOpt = computed(() => {
  const hm = hourWeekHeatmap(props.v.rows)
  const data: [number, number, number][] = []
  hm.forEach((row, wd) => row.forEach((val, h) => data.push([h, wd, val])))
  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'item', formatter: (p: any) => `${WEEKDAYS[p.value[1]]} ${p.value[0]}:00<br/><b>${fmt(p.value[2])}</b> beers` },
    grid: { ...base.grid, top: 8 },
    xAxis: { type: 'category', data: [...Array(24).keys()].map(h => `${h}h`), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: 'category', data: WEEKDAYS, inverse: true, ...axisStyle, splitLine: { show: false } },
    visualMap: { min: 0, max: Math.max(1, ...data.map(x => x[2])), show: false, inRange: { color: HEAT } },
    series: [{ type: 'heatmap', data, itemStyle: { borderColor: '#120d07', borderWidth: 2, borderRadius: 3 } }],
  }
})

const monthOpt = computed(() => {
  const m = monthlyTotals(props.v.rows)
  return {
    ...base,
    xAxis: { type: 'category', data: m.map(x => x[0]), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: 'value', ...axisStyle },
    series: [{ name: 'Beers', type: 'bar', data: m.map(x => x[1]), itemStyle: { color: AMBER, borderRadius: [4, 4, 0, 0] } }],
  }
})

const communityOpt = computed(() => {
  const c = communityGrowth(props.v.rows)
  return {
    ...base,
    xAxis: { type: 'category', data: c.map(x => isoDay(x[0])), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: 'value', ...axisStyle },
    series: [{ name: 'Drinkers', type: 'line', step: 'end', symbol: 'none', data: c.map(x => x[1]), lineStyle: { color: '#5eb3ff', width: 2 } }],
  }
})

const facts = computed(() => funFacts(props.v.total, CONFIG.pintPriceEur))
</script>

<template>
  <div class="grid">
    <div class="card"><h3>📈 Beers per day</h3><EChart :option="dailyOpt" height="340px" /></div>
    <div class="grid g2">
      <div class="card"><h3>🚀 Road to 1M</h3><EChart :option="cumOpt" /></div>
      <div class="card"><h3>🗓️ Beers per month</h3><EChart :option="monthOpt" /></div>
    </div>
    <div class="card"><h3>🟧 The beer calendar</h3><EChart :option="calOpt" height="170px" /></div>
    <div class="grid g2">
      <div class="card"><h3>🕐 When does the group drink?</h3><EChart :option="hourOpt" height="280px" /></div>
      <div class="card"><h3>👥 Community growth</h3><EChart :option="communityOpt" height="280px" /></div>
    </div>
    <div class="grid g4">
      <div class="card fact"><div class="emoji">🛁</div><div class="value">{{ fmt(facts.bathtubs) }}</div><div class="small muted">bathtubs of beer ({{ fmt(facts.liters) }} L)</div></div>
      <div class="card fact"><div class="emoji">🔥</div><div class="value">{{ fmt(facts.kcal / 1e6, 1) }}M</div><div class="small muted">kcal</div></div>
      <div class="card fact"><div class="emoji">🍔</div><div class="value">{{ fmt(facts.bigMacs) }}</div><div class="small muted">Big Mac equivalents</div></div>
      <div class="card fact"><div class="emoji">💶</div><div class="value">€{{ fmt(facts.money) }}</div><div class="small muted">spent at €{{ CONFIG.pintPriceEur }}/pint</div></div>
    </div>
  </div>
</template>
