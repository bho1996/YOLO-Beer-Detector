<script setup lang="ts">
import { computed } from 'vue'
import { CONFIG } from '../config'
import DonateButtons from './DonateButtons.vue'

const funding = computed(() => {
  if (!CONFIG.monthlyCostsEur) return null
  const got = CONFIG.donatedThisMonthEur ?? 0
  return { got, need: CONFIG.monthlyCostsEur, pct: Math.min(1, got / CONFIG.monthlyCostsEur) }
})
</script>

<template>
  <footer class="footer grid g32">
    <div>
      <h3 style="margin-top:0">🍺 Keep the counter running</h3>
      <p class="muted small">
        This tracker runs 24/7 on a home server: an AI checks every photo, the bot keeps the official count,
        and this page updates by itself. It's a hobby project, built for fun, for the group.
        If it made you smile, a pint for the dev keeps the servers humming. 🙏
      </p>
      <div v-if="funding" class="donate-box">
        <b>This month's server costs</b>
        <div class="bar mt"><div :style="{ width: funding.pct * 100 + '%' }" /></div>
        <div class="bar-caption"><span>€{{ funding.got }} raised</span><span>€{{ funding.need }} needed</span></div>
      </div>
      <p v-if="CONFIG.supporters.length" class="small mt">💛 Thanks to: {{ CONFIG.supporters.join(' · ') }}</p>
    </div>
    <div>
      <DonateButtons source="footer" />
      <p class="small muted mt">Numbers are masked (+39 *** 1234). No personal data is published.</p>
    </div>
  </footer>
</template>
