<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ pct: number }>()   // 0..1
// livello minimo visibile, altrimenti all'inizio il bicchiere sembra vuoto
const level = computed(() => Math.max(4, Math.min(100, props.pct * 100)))
const bubbles = [12, 28, 44, 61, 77, 88]
</script>

<template>
  <div class="glass" aria-hidden="true">
    <div class="glass-body">
      <div class="glass-fill" :style="{ height: level + '%' }">
        <span v-for="(x, i) in bubbles" :key="i" class="bubble"
              :style="{ left: x + '%', animationDelay: (i * 0.7) + 's', animationDuration: (3 + (i % 3)) + 's' }" />
      </div>
      <div class="glass-foam" :style="{ bottom: `calc(${level}% - 6%)` }" />
      <div class="glass-pct">{{ (pct * 100).toFixed(2) }}%</div>
    </div>
  </div>
</template>
