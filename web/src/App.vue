<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDataset } from './lib/data'
import { buildView } from './lib/view'
import { romeNow, dayOf, fmtDay, isoDay, dayFromIso, MIN_PER_DAY } from './lib/time'
import HeroSection from './components/HeroSection.vue'
import MissionControl from './components/MissionControl.vue'
import PotdCard from './components/PotdCard.vue'
import TodayTop from './components/TodayTop.vue'
import LeaderboardsTab from './components/LeaderboardsTab.vue'
import StatsTab from './components/StatsTab.vue'
import NationsTab from './components/NationsTab.vue'
import PlayerTab from './components/PlayerTab.vue'
import HealthTab from './components/HealthTab.vue'
import SupportFooter from './components/SupportFooter.vue'

const { data, error, lastCheck } = useDataset()

// "adesso" (ora di Roma) che avanza da solo
const now = ref(romeNow())
let timer: number | undefined
onMounted(() => { timer = window.setInterval(() => (now.value = romeNow()), 30_000) })
onUnmounted(() => clearInterval(timer))

// ---------- stato da/verso URL (link condivisibili) ----------
const TABS = [
  { id: 'leaderboards', label: '🏆 Leaderboards' },
  { id: 'stats', label: '📊 Stats' },
  { id: 'nations', label: '🌍 Nations' },
  { id: 'player', label: '👤 Player' },
  { id: 'health', label: '🩺 Data Health' },
] as const
type TabId = typeof TABS[number]['id']
const params = new URLSearchParams(location.search)
const tab = ref<TabId>((TABS.find(t => t.id === params.get('tab'))?.id) ?? 'leaderboards')
const playerName = ref<string | null>(params.get('player'))
const pinnedDay = ref<number | null>(params.get('date') ? dayFromIso(params.get('date')!) : null)

watch([tab, playerName, pinnedDay], () => {
  const p = new URLSearchParams()
  if (tab.value !== 'leaderboards') p.set('tab', tab.value)
  if (playerName.value && tab.value === 'player') p.set('player', playerName.value)
  if (pinnedDay.value != null) p.set('date', isoDay(pinnedDay.value))
  const qs = p.toString()
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname)
})

// ---------- time machine ----------
const firstDay = computed(() => data.value?.rows.length ? data.value.rows[0].day : dayOf(now.value))
const today = computed(() => dayOf(now.value))
const sliderDay = computed({
  get: () => pinnedDay.value ?? today.value,
  set: (d: number) => { pinnedDay.value = d >= today.value ? null : d },
})
const isLive = computed(() => pinnedDay.value == null)
const refT = computed(() => isLive.value ? now.value : pinnedDay.value! * MIN_PER_DAY + MIN_PER_DAY - 1)

const view = computed(() => data.value ? buildView(data.value, refT.value, isLive.value) : null)

const playerU = computed(() => {
  if (!data.value || !playerName.value) return null
  const i = data.value.users.findIndex(u => u.name === playerName.value)
  return i >= 0 ? i : null
})
function openPlayer(u: number | null) {
  playerName.value = u == null ? null : data.value!.users[u].name
  tab.value = 'player'
  if (u != null) document.getElementById('tabs')?.scrollIntoView({ behavior: 'smooth' })
}

const updatedAgo = computed(() => {
  if (!data.value) return ''
  const mins = Math.max(0, Math.round((Date.now() / 1000 - data.value.dbUpdatedAt) / 60))
  void now.value; void lastCheck.value  // ricalcola quando passa il tempo
  return mins < 1 ? 'just now' : mins < 60 ? `${mins} min ago` : `${Math.round(mins / 60)} h ago`
})
</script>

<template>
  <div v-if="!view" class="loading">
    <div>
      <div class="big">🍺</div>
      <p v-if="error">Couldn't load the data ({{ error }}). Retrying automatically…</p>
      <p v-else>Pouring the numbers…</p>
    </div>
  </div>

  <template v-else>
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">🍻 1M Beers</div>
        <span class="pill" :title="'Database updated ' + updatedAgo">
          <span class="dot" :class="{ off: !isLive }" />{{ isLive ? 'LIVE · updated ' + updatedAgo : 'TIME MACHINE' }}
        </span>
        <div class="spacer" />
        <div class="timemachine">
          <span class="tm-label">⏳ {{ isLive ? 'Now' : fmtDay(sliderDay) }}</span>
          <input v-model.number="sliderDay" type="range" :min="firstDay" :max="today" step="1" aria-label="Time machine" />
          <button v-if="!isLive" class="btn sm" @click="pinnedDay = null">Back to live</button>
        </div>
      </div>
    </header>

    <main class="container">
      <div v-if="!isLive" class="banner tt">
        ⏳ Time machine: you're looking at the group as it was at the end of {{ fmtDay(sliderDay) }}.
      </div>

      <HeroSection :v="view" />
      <MissionControl :v="view" />

      <section class="section grid g2">
        <PotdCard :v="view" />
        <TodayTop :v="view" @player="openPlayer" />
      </section>

      <section id="tabs" class="section">
        <nav class="tabs">
          <button v-for="t in TABS" :key="t.id" :class="{ active: tab === t.id }" @click="tab = t.id">{{ t.label }}</button>
        </nav>
        <LeaderboardsTab v-if="tab === 'leaderboards'" :v="view" @player="openPlayer" />
        <StatsTab v-else-if="tab === 'stats'" :v="view" />
        <NationsTab v-else-if="tab === 'nations'" :v="view" />
        <PlayerTab v-else-if="tab === 'player'" :v="view" :player="playerU" @player="openPlayer" />
        <HealthTab v-else-if="tab === 'health'" :v="view" />
      </section>

      <SupportFooter />
    </main>
  </template>
</template>
