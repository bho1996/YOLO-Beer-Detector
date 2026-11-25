<script setup lang="ts">
import { computed } from 'vue'
import type { View } from '../lib/view'
import { dayStart } from '../lib/view'
import { sumBeers } from '../lib/stats'
import { fmt, fmtTime, MIN_PER_DAY, weekdayOf } from '../lib/time'
import { CONFIG } from '../config'
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

const missions = computed(() => {
  const { rows, refT, refDay, total } = props.v
  const step = CONFIG.milestoneStep
  const nextMs = (Math.floor(total / step) + 1) * step
  const toNext = nextMs - total
  const last7 = sumBeers(rows, refT - 7 * MIN_PER_DAY, refT + 1)
  const pace = last7 / 7
  const week0 = dayStart(refDay - weekdayOf(refDay))
  const prevWeek = sumBeers(rows, week0 - 7 * MIN_PER_DAY, week0)
  const goal = prevWeek > 0 ? Math.max(500, Math.ceil(prevWeek * 1.1 / 100) * 100) : 1500
  const week = k.value.week
  const daysLeft = 7 - weekdayOf(refDay)
  return {
    nextMs, toNext, progress: Math.max(0, Math.min(1, 1 - toNext / step)),
    etaHours: pace > 0 ? Math.round(toNext / (pace / 24)) : null,
    goal, week, weekProgress: Math.min(week / goal, 1),
    needPerDay: week < goal ? Math.ceil((goal - week) / daysLeft) : 0,
  }
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
    <div class="grid g2">
      <div class="card mission">
        <div class="mission-title">🚩 Next Milestone: <b>{{ fmt(missions.nextMs) }}</b></div>
        <div class="bar"><div :style="{ width: missions.progress * 100 + '%' }" /></div>
        <div class="bar-caption">
          <span>{{ fmt(missions.toNext) }} to go</span>
          <span v-if="missions.etaHours !== null">ETA ≈ {{ fmt(missions.etaHours) }}h at this week's pace</span>
        </div>
        <p v-if="missions.toNext <= 10" class="mission-alert">🚨 ONLY {{ missions.toNext }} TO GO! Who is going to snipe it?</p>
      </div>
      <div class="card mission">
        <div class="mission-title">📅 Weekly Mission: <b>{{ fmt(missions.goal) }}</b></div>
        <div class="bar"><div :style="{ width: missions.weekProgress * 100 + '%' }" /></div>
        <div class="bar-caption">
          <span v-if="missions.week >= missions.goal" class="mission-done">🎉 MISSION ACCOMPLISHED! ({{ fmt(missions.week) }} this week)</span>
          <template v-else>
            <span>{{ fmt(missions.week) }} so far · {{ fmt(missions.goal - missions.week) }} left</span>
            <span>need ~{{ fmt(missions.needPerDay) }}/day</span>
          </template>
        </div>
      </div>
    </div>
    <div class="grid g5">
      <Kpi label="🍺 Today" :value="fmt(k.today)" :delta="k.today - k.ySame" deltaLabel="vs yesterday at this time" />
      <Kpi label="📅 This week" :value="fmt(k.week)" :delta="k.week - k.lastWeekSame" deltaLabel="vs last week so far" />
      <Kpi label="🙋 Drinkers today" :value="fmt(k.drinkers)" />
      <Kpi label="🆕 New drinkers this week" :value="fmt(k.newThisWeek)" />
      <Kpi label="🤖 Ghost beers" :value="fmt(props.v.ghost)" deltaLabel="not tracked by the bot"
           hint="Beers counted before the bot existed, plus totals written by the group in chat. They are not attributed to any drinker." />
    </div>
    <div class="banner" :class="status.cls">{{ status.text }}</div>
  </section>
</template>
