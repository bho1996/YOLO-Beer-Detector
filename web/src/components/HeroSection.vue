<script setup lang="ts">
import { computed } from 'vue'
import type { View } from '../lib/view'
import { CONFIG } from '../config'
import { fmt, fmtDay } from '../lib/time'
import BeerGlass from './BeerGlass.vue'
import DonateButtons from './DonateButtons.vue'

const props = defineProps<{ v: View }>()

const pct = computed(() => props.v.total / CONFIG.goal)
const last30 = computed(() => {
  let s = 0
  for (let d = props.v.refDay - 29; d <= props.v.refDay; d++) s += props.v.sumDay(d)
  return s / 30
})
const eta = computed(() => {
  if (last30.value <= 0) return null
  const days = Math.ceil((CONFIG.goal - props.v.total) / last30.value)
  return { days, date: fmtDay(props.v.refDay + days), years: days / 365 }
})
</script>

<template>
  <section class="hero">
    <div>
      <h1>🍻 The 1 Million Beers Project</h1>
      <p class="sub">One million pints. One legendary group. Every beer counts.</p>
      <div class="counter-label">{{ v.isLive ? 'Beers so far' : 'Beers at ' + fmtDay(v.refDay) }}</div>
      <div class="counter">{{ fmt(v.total) }}</div>
      <div class="counter-sub">
        {{ fmt(CONFIG.goal - v.total) }} to go ·
        <template v-if="eta">at the last-30-days pace ({{ fmt(last30, 0) }}/day) we hit 1M around
          <b>{{ eta.date }}</b> ({{ eta.years >= 1 ? fmt(eta.years, 1) + ' years' : eta.days + ' days' }})</template>
      </div>
      <div class="mt">
        <div class="bar"><div :style="{ width: Math.min(100, pct * 100) + '%' }" /></div>
        <div class="bar-caption"><span>0</span><span>{{ (pct * 100).toFixed(2) }}% of the way</span><span>1,000,000</span></div>
      </div>
      <div class="hero-actions">
        <div style="min-width:240px"><DonateButtons source="hero" label="🍻 Keep the tracker alive — buy the dev a pint" /></div>
      </div>
    </div>
    <BeerGlass :pct="pct" />
  </section>
</template>
