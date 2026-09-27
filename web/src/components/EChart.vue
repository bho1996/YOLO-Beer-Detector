<script setup lang="ts">
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, HeatmapChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent, VisualMapComponent,
  CalendarComponent, DataZoomComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, LineChart, HeatmapChart, GridComponent, TooltipComponent,
  LegendComponent, VisualMapComponent, CalendarComponent, DataZoomComponent])

// eslint-disable-next-line @typescript-eslint/no-explicit-any
withDefaults(defineProps<{ option: Record<string, any>; height?: string }>(), { height: '320px' })
</script>

<template>
  <VChart :option="option" :style="{ height, width: '100%' }" autoresize />
</template>
