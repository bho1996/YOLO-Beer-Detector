<script setup lang="ts">
import { computed } from 'vue'
import type { View } from '../lib/view'
import type { Col } from '../lib/columns'
import { fmt, fmtDateTime, unixToRome } from '../lib/time'
import DataTable from './DataTable.vue'

const props = defineProps<{ v: View }>()
const r = computed(() => props.v.data.report)
const tracked = computed(() => props.v.data.rows.reduce((s, x) => s + x.beers, 0))

const checks = computed(() => [
  { what: 'Rows in database', value: r.value.rows, note: 'Database is read-only; every fix below is applied in memory.' },
  { what: 'Dates fixed from WhatsApp timestamp', value: r.value.ts_fixed, note: 'File name WA_<unix> is the source of truth.' },
  { what: 'Swapped day/month fixed', value: r.value.swap_fixed, note: 'Historic conversion bug (e.g. 05/09 ↔ 09/05).' },
  { what: 'Identities merged (truncated prefix)', value: r.value.alias_rows, note: `${Object.keys(r.value.aliases).length} aliases: old bot versions saved truncated prefixes (e.g. +97 → +971) for the same person.` },
  { what: 'Photos rejected by AI (0 points)', value: r.value.zero_photos, note: 'Not counted anywhere.' },
  { what: 'Photos stored with more than 1 point', value: r.value.photos_multi_pt, note: `Old VAR corrections (+${fmt(r.value.photos_multi_pt_extra)} extra points) are counted as 1.` },
  { what: 'Unparsable dates', value: r.value.unparsable_dates, note: 'Excluded from charts.' },
  { what: 'Duplicate files', value: r.value.duplicate_files, note: '' },
])
const cols: Col[] = [{ key: 'what', label: 'Check' }, { key: 'value', label: 'Rows', num: true }, { key: 'note', label: 'Notes' }]

const audit = computed(() => [...props.v.rows].slice(-300).reverse().map(x => ({
  ...x, name: props.v.name(x.u),
})))
const auditCols: Col[] = [
  { key: 't', label: 'When', fmt: (t: number) => fmtDateTime(t) },
  { key: 'name', label: 'Drinker' },
  { key: 'video', label: 'Type', fmt: (v: boolean) => v ? '🎬 Down' : '📸 Photo' },
  { key: 'punti', label: 'DB points', num: true },
  { key: 'beers', label: 'Counted beers', num: true },
  { key: 'score', label: 'Leaderboard pts', num: true },
  { key: 'file', label: 'File' },
]
</script>

<template>
  <div class="grid g3">
    <div class="card kpi"><div class="label">👥 Official group total</div><div class="value">{{ fmt(v.data.officialTotal) }}</div>
      <div class="small muted">Counter kept by the bot, aligned to the numbers written in the group.</div></div>
    <div class="card kpi"><div class="label">📸 Beers tracked by the bot</div><div class="value">{{ fmt(tracked) }}</div>
      <div class="small muted">1 per approved photo + 1 per down video.</div></div>
    <div class="card kpi"><div class="label">👻 Untracked beers</div><div class="value">{{ fmt(v.ghost) }}</div>
      <div class="small muted">Before the bot existed, or only written as text in the group.</div></div>
  </div>

  <div class="card mt">
    <h3>📏 Counting rules</h3>
    <ul class="small" style="margin:0; padding-left:18px; line-height:1.7">
      <li><b>Global counter:</b> every approved photo = 1 beer, every down video = 1 beer.</li>
      <li><b>Leaderboards:</b> approved photo = 1 point, down video = 5 points.</li>
      <li>Data is refreshed automatically: the bot publishes the database, this page checks for updates every minute.</li>
      <li>Last database update: <b>{{ fmtDateTime(unixToRome(v.data.dbUpdatedAt)) }}</b> (Rome time).</li>
    </ul>
  </div>

  <div class="card mt"><h3>🩺 Data health</h3><DataTable :cols="cols" :rows="checks" /></div>
  <div class="card mt"><h3>🧾 Beer audit log (latest 300)</h3><DataTable :cols="auditCols" :rows="audit" :pageSize="20" /></div>
</template>
