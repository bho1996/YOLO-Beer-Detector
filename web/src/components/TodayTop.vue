<script setup lang="ts">
import { computed } from 'vue'
import type { View } from '../lib/view'
import { dayStart } from '../lib/view'
import { leaderboard } from '../lib/stats'
import { lbCols } from '../lib/columns'
import DataTable from './DataTable.vue'

const props = defineProps<{ v: View }>()
const emit = defineEmits<{ player: [u: number] }>()

const today = computed(() => {
  const from = dayStart(props.v.refDay)
  return leaderboard(props.v.rows.filter(r => r.t >= from), props.v.data.users)
})
</script>

<template>
  <div class="card">
    <h3>🔥 Today's top drinkers</h3>
    <DataTable :cols="lbCols()" :rows="today" clickable :pageSize="10" @select="r => emit('player', r.u)" />
    <p class="small muted">Photo = 1 point · Down video = 5 points. Click a name for their profile.</p>
  </div>
</template>
