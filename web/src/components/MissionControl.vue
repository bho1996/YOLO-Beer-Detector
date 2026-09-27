<script setup lang="ts">
import { computed } from 'vue'
import type { View } from '../lib/view'
import { dayStart } from '../lib/view'
import { sumBeers } from '../lib/stats'
import { fmt, fmtTime, MIN_PER_DAY, weekdayOf } from '../lib/time'
import Kpi from './Kpi.vue'

const props = defineProps<{ v: View }>()

const k = computed(() => {
  const { rows, refT, refDay } = props.v
  const today0 = dayStart(refDay)
  const today = sumBeers(rows, today0, refT + 1)
  const ySame = sumBeers(rows, today0 - MIN_PER_DAY, refT - MIN_PER_DAY + 1)
  const week0 = dayStart(refDay - weekdayOf(refDay))
  const week = sumBeers(rows, week0, refT + 1)
  const lastWeekSame = sumBeers(rows, week0 - 7 * MIN_PER_DAY, refT - 7 * MIN_PER_DAY + 1)

  const todayUsers = new Set<number>(), before = new Set<number>(), weekNew = new Set<number>()
  for (const r of rows) {
    if (r.t < week0) before.add(r.u)
    else if (!before.has(r.u)) weekNew.add(r.u)
    if (r.t >= today0) todayUsers.add(r.u)
  }
  const last = rows.length ? rows[rows.length - 1] : null
  const minsSinceLast = last ? refT - last.t : Infinity
  return { today, ySame, week, lastWeekSame, drinkers: todayUsers.size, newThisWeek: weekNew.size, last, minsSinceLast }
})

const status = computed(() => {
  const m = k.value.minsSinceLast
  if (!k.value.last) return { cls: 'dry', text: '🍺 No beers tracked yet at this point in time.' }
  if (m <= 30) return { cls: 'live', text: `🔥 The bar is open! Last beer ${m < 1 ? 'just now' : m + ' min ago'} by ${props.v.name(k.value.last!.u)}.` }
  if (m <= 180) return { cls: 'warm', text: `🍺 Last beer ${Math.round(m / 60 * 10) / 10}h ago (${fmtTime(k.value.last!.t)}) by ${props.v.name(k.value.last!.u)}.` }
  return { cls: 'dry', text: `🏜️ Dry spell: no beers in the last ${Math.round(m / 60)}h. Someone save us!` }
})
</script>

<template>
  <section class="section">
    <h2 class="section-title">🎯 Mission Control</h2>
    <div class="grid g4">
      <Kpi label="🍺 Today" :value="fmt(k.today)" :delta="k.today - k.ySame" deltaLabel="vs yesterday at this time" />
      <Kpi label="📅 This week" :value="fmt(k.week)" :delta="k.week - k.lastWeekSame" deltaLabel="vs last week so far" />
      <Kpi label="🙋 Drinkers today" :value="fmt(k.drinkers)" />
      <Kpi label="🆕 New drinkers this week" :value="fmt(k.newThisWeek)" />
    </div>
    <div class="banner" :class="status.cls">{{ status.text }}</div>
  </section>
</template>
