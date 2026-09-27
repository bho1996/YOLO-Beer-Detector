<script setup lang="ts">
import { CONFIG, donateUrl } from '../config'

withDefaults(defineProps<{ source: string; label?: string; primary?: boolean }>(),
  { label: '🍻 Buy the Dev a Pint', primary: true })
</script>

<template>
  <div class="grid" style="gap:8px">
    <a class="btn block" :class="{ primary }" :href="donateUrl(source)" target="_blank" rel="noopener">{{ label }}</a>
    <div v-if="CONFIG.bmcLink || CONFIG.paypalLink" class="grid g2" style="gap:8px">
      <a v-if="CONFIG.bmcLink" class="btn sm" :href="CONFIG.bmcLink" target="_blank" rel="noopener">☕ Buy Me a Coffee</a>
      <a v-if="CONFIG.paypalLink" class="btn sm" :href="CONFIG.paypalLink" target="_blank" rel="noopener">💙 PayPal</a>
    </div>
  </div>
</template>
