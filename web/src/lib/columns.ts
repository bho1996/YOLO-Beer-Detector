export interface Col {
  key: string
  label: string
  num?: boolean
  fmt?: (v: any, row: any) => string
}

const MEDALS = ['🥇', '🥈', '🥉']

export const lbCols = (showUploads = false): Col[] => [
  { key: 'rank', label: '#', fmt: (r: number) => MEDALS[r - 1] ?? String(r) },
  { key: 'name', label: 'Drinker', fmt: (n: string, row: any) => `${row.flag}  ${n}` },
  { key: 'score', label: 'Score', num: true },
  { key: 'pints', label: '🍺 Pints', num: true },
  { key: 'downs', label: '🎬 Downs (×5)', num: true },
  ...(showUploads ? [{ key: 'uploads', label: 'Uploads', num: true }] : []),
]
