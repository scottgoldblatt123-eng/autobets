/** Date range for Analyse: presets or a calendar pick, plus an optional comparison period (previous period, same period last year, or your own dates). */
export interface Range { start: string; end: string }
export interface RangeState { preset: string; range: Range; compare: boolean; cmpPreset: string; cmp: Range }

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const parse = (s: string) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d) }
const add = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x }
const days = (r: Range) => Math.round((parse(r.end).getTime() - parse(r.start).getTime()) / 86400000) + 1

export const PRESETS: [string, string][] = [['today', 'Today'], ['yesterday', 'Yesterday'], ['7', 'Last 7 days'], ['30', 'Last 30 days'], ['90', 'Last 90 days'], ['week', 'This week'],
  ['lastweek', 'Last week'], ['month', 'This month'], ['lastmonth', 'Last month'], ['year', 'This year'], ['custom', 'Custom…']]
export const CMP_PRESETS: [string, string][] = [['prev', 'Previous period'], ['lastyear', 'Same period last year'], ['custom', 'Custom…']]

export function presetRange(p: string, now = new Date()): Range {
  const t = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const mon = add(t, -((t.getDay() + 6) % 7))
  switch (p) {
    case 'today': return { start: iso(t), end: iso(t) }
    case 'yesterday': return { start: iso(add(t, -1)), end: iso(add(t, -1)) }
    case '7': return { start: iso(add(t, -6)), end: iso(t) }
    case '90': return { start: iso(add(t, -89)), end: iso(t) }
    case 'week': return { start: iso(mon), end: iso(t) }
    case 'lastweek': return { start: iso(add(mon, -7)), end: iso(add(mon, -1)) }
    case 'month': return { start: iso(new Date(t.getFullYear(), t.getMonth(), 1)), end: iso(t) }
    case 'lastmonth': return { start: iso(new Date(t.getFullYear(), t.getMonth() - 1, 1)), end: iso(new Date(t.getFullYear(), t.getMonth(), 0)) }
    case 'year': return { start: iso(new Date(t.getFullYear(), 0, 1)), end: iso(t) }
    default: return { start: iso(add(t, -29)), end: iso(t) }
  }
}

export function cmpRange(p: string, r: Range): Range {
  if (p === 'lastyear') { const s = parse(r.start), e = parse(r.end); return { start: iso(new Date(s.getFullYear() - 1, s.getMonth(), s.getDate())), end: iso(new Date(e.getFullYear() - 1, e.getMonth(), e.getDate())) } }
  const a = parse(r.start), b = parse(r.end)
  if (a.getDate() === 1 && iso(new Date(b.getFullYear(), b.getMonth() + 1, 0)) === r.end && a.getMonth() === b.getMonth()) {       // a whole calendar month compares to the month before
    return { start: iso(new Date(a.getFullYear(), a.getMonth() - 1, 1)), end: iso(new Date(a.getFullYear(), a.getMonth(), 0)) }
  }
  const n = days(r); return { start: iso(add(parse(r.start), -n)), end: iso(add(parse(r.start), -1)) }
}

export const initialRange = (): RangeState => { const range = presetRange('30'); return { preset: '30', range, compare: false, cmpPreset: 'prev', cmp: cmpRange('prev', range) } }
export const rangeQuery = (s: RangeState) => `start=${s.range.start}&end=${s.range.end}` + (s.compare ? `&cstart=${s.cmp.start}&cend=${s.cmp.end}` : '')
const fmt = (r: Range) => `${parse(r.start).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })} – ${parse(r.end).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })}`
export const rangeLabel = fmt

export default function DateRange({ value, onChange }: { value: RangeState; onChange: (s: RangeState) => void }) {
  const today = iso(new Date())
  const set = (patch: Partial<RangeState>) => {
    const n = { ...value, ...patch }
    if (patch.preset && patch.preset !== 'custom') n.range = presetRange(patch.preset)
    if (n.compare && n.cmpPreset !== 'custom' && (patch.preset || patch.range || patch.cmpPreset || patch.compare)) n.cmp = cmpRange(n.cmpPreset, n.range)
    onChange(n)
  }
  const pick = (k: 'start' | 'end', v: string, which: 'range' | 'cmp') => {
    if (!v) return
    const cur = value[which], next = { ...cur, [k]: v }
    if (next.end < next.start) { if (k === 'start') next.end = v; else next.start = v }
    which === 'range' ? set({ preset: 'custom', range: next }) : set({ cmpPreset: 'custom', cmp: next })
  }
  const row = (which: 'range' | 'cmp') => <>
    <input type="date" max={today} value={value[which].start} onChange={e => pick('start', e.target.value, which)} aria-label={which === 'range' ? 'From date' : 'Compare from date'} />
    <span className="muted">to</span>
    <input type="date" max={which === 'range' ? today : undefined} value={value[which].end} onChange={e => pick('end', e.target.value, which)} aria-label={which === 'range' ? 'To date' : 'Compare to date'} /></>
  return <div className="daterange" style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', justifyContent: 'flex-end' }}>
    <span className="muted small">Date range</span>
    <select value={value.preset} onChange={e => set({ preset: e.target.value })} aria-label="Date range preset">{PRESETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
    {row('range')}
    <label className="small" style={{ display: 'flex', gap: 4, alignItems: 'center' }}><input type="checkbox" checked={value.compare} onChange={e => set({ compare: e.target.checked })} />Compare</label>
    {value.compare && <><select value={value.cmpPreset} onChange={e => set({ cmpPreset: e.target.value })} aria-label="Comparison period">{CMP_PRESETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>{row('cmp')}</>}
  </div>
}
