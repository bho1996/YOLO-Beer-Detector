<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Col } from '../lib/columns'

const props = withDefaults(defineProps<{
  cols: Col[]
  rows: any[]
  clickable?: boolean
  pageSize?: number
  sortable?: boolean
  showAll?: boolean
}>(), { clickable: false, pageSize: 15, sortable: false, showAll: false })
const emit = defineEmits<{ select: [row: any] }>()

const sortKey = ref<string | null>(null)
const sortDir = ref<1 | -1>(-1)
const shown = computed(() => props.showAll ? sorted.value.length : shownRaw.value)
const shownRaw = ref(props.pageSize)
watch(() => props.rows, () => { shownRaw.value = props.pageSize })

const sorted = computed(() => {
  if (!sortKey.value) return props.rows
  const k = sortKey.value
  const col = props.cols.find(c => c.key === k)
  const get = col?.sortVal ? col.sortVal : (r: any) => r[k]
  return [...props.rows].sort((a, b) => {
    const av = get(a), bv = get(b)
    if (av === bv) return 0
    if (av == null) return 1
    if (bv == null) return -1
    return (av > bv ? 1 : -1) * sortDir.value
  })
})

function sortBy(k: string) {
  if (!props.sortable) return
  if (sortKey.value === k) sortDir.value = sortDir.value === 1 ? -1 : 1
  else { sortKey.value = k; sortDir.value = -1 }
}
const cell = (c: Col, r: any) => {
  const v = r[c.key]
  if (c.fmt) return c.fmt(v, r)
  return typeof v === 'number' ? v.toLocaleString('en-US') : v ?? ''
}
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th v-for="c in cols" :key="c.key" :class="{ num: c.num, sortable }" @click="sortBy(c.key)">
            {{ c.label }}<span v-if="sortKey === c.key">{{ sortDir === 1 ? ' ▲' : ' ▼' }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(r, i) in sorted.slice(0, shown)" :key="i" :class="{ clickable }" @click="clickable && emit('select', r)">
          <td v-for="c in cols" :key="c.key" :class="{ num: c.num }">{{ cell(c, r) }}</td>
        </tr>
        <tr v-if="!rows.length"><td :colspan="cols.length" class="muted">Nothing here yet 🍺</td></tr>
      </tbody>
    </table>
  </div>
  <div v-if="!showAll && sorted.length > shownRaw" class="mt" style="text-align:center">
    <button class="btn sm" @click="shownRaw += pageSize * 2">Show more ({{ (sorted.length - shownRaw).toLocaleString('en-US') }} left)</button>
  </div>
</template>
