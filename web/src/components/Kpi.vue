<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ label: string; value: string; delta?: number | null; deltaLabel?: string; hint?: string }>()
const cls = computed(() => props.delta == null ? 'flat' : props.delta > 0 ? 'up' : props.delta < 0 ? 'down' : 'flat')
const arrow = computed(() => props.delta == null ? '' : props.delta > 0 ? '▲' : props.delta < 0 ? '▼' : '•')
</script>

<template>
  <div class="card kpi" :title="hint">
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
    <div v-if="delta != null" class="delta" :class="cls">
      {{ arrow }} {{ Math.abs(delta).toLocaleString('en-US') }} {{ deltaLabel }}
    </div>
    <div v-else-if="deltaLabel" class="delta flat">{{ deltaLabel }}</div>
  </div>
</template>
