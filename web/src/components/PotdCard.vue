<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { View } from '../lib/view'
import { dayFromIso, fmtDay } from '../lib/time'

const props = defineProps<{ v: View }>()

// Solo le foto già pubblicate fino al giorno della time machine
const available = computed(() =>
  Object.entries(props.v.data.potd)
    .map(([day, p]) => ({ day: dayFromIso(day), ...p }))
    .filter(p => p.day <= props.v.refDay)
    .sort((a, b) => b.day - a.day)
    .slice(0, 14))

const selected = ref(0)
watch(available, () => { selected.value = 0 })
const current = computed(() => available.value[selected.value])

const label = computed(() => {
  if (!current.value) return ''
  const diff = props.v.refDay - current.value.day
  return diff === 0 ? 'today' : diff === 1 ? 'yesterday' : fmtDay(current.value.day)
})
</script>

<template>
  <div class="card">
    <h3>📸 Picture of the Day <span v-if="current" class="muted small">({{ label }})</span></h3>
    <template v-if="current">
      <img class="potd-img" :src="current.image" :alt="`Beer by ${current.user}`" loading="lazy" />
      <p class="small muted" style="margin:10px 0 0">
        🏅 <b style="color:var(--text)">{{ current.user }}</b> · {{ current.time }} ·
        picked from {{ current.candidates.toLocaleString('en-US') }} approved beers
      </p>
      <div v-if="available.length > 1" class="thumbs">
        <button v-for="(p, i) in available" :key="p.day" :class="{ active: i === selected }" @click="selected = i">
          <img :src="p.image" :alt="fmtDay(p.day)" loading="lazy" />
          <small>{{ fmtDay(p.day, false) }}</small>
        </button>
      </div>
    </template>
    <div v-else class="potd-empty">
      <div class="big">🍺</div>
      <p class="muted">The picture of the day will appear here soon!</p>
    </div>
  </div>
</template>
