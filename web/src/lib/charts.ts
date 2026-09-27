// Stile comune dei grafici ECharts (tema "birra scura")
export const AMBER = '#ffb02e'
export const AMBER2 = '#ff8a00'
export const RED = '#ff5d5d'
const MUTED = '#b8a58a'
const GRID_LINE = 'rgba(255,255,255,.06)'
export const HEAT = ['#231a10', '#5a3a12', '#9a5c10', '#d98a12', '#ffb02e', '#fff0c2']

export const base = {
  backgroundColor: 'transparent',
  textStyle: { color: MUTED, fontFamily: 'Inter, system-ui, sans-serif' },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#2a1f14', borderColor: 'rgba(255,176,46,.35)', textStyle: { color: '#f6ecdc' },
  },
  grid: { left: 8, right: 12, top: 24, bottom: 8, containLabel: true },
}

export const axisStyle = {
  axisLine: { lineStyle: { color: GRID_LINE } },
  axisTick: { show: false },
  splitLine: { lineStyle: { color: GRID_LINE } },
  axisLabel: { color: MUTED },
}
