// Betfair price ladder (mirror of backend/autobets/ticks.py)
const BANDS: [number, number, number][] = [
  [1.01, 2.0, 0.01], [2.0, 3.0, 0.02], [3.0, 4.0, 0.05], [4.0, 6.0, 0.1], [6.0, 10.0, 0.2],
  [10.0, 20.0, 0.5], [20.0, 30.0, 1.0], [30.0, 50.0, 2.0], [50.0, 100.0, 5.0], [100.0, 1000.0, 10.0],
]
const r2 = (x: number) => Math.round(x * 100) / 100

export const LADDER: number[] = (() => {
  const out: number[] = []
  for (const [lo, hi, inc] of BANDS) {
    const n = Math.round((hi - lo) / inc)
    for (let i = 0; i < n; i++) out.push(r2(lo + i * inc))
  }
  out.push(1000)
  return out
})()
const INDEX = new Map(LADDER.map((p, i) => [p, i]))

export const isValid = (p: number) => INDEX.has(r2(p)) && Math.abs(p - r2(p)) < 1e-9
export function nearest(p: number): number {
  let best = LADDER[0]
  for (const x of LADDER) if (Math.abs(x - p) < Math.abs(best - p) - 1e-12 || (Math.abs(Math.abs(x - p) - Math.abs(best - p)) < 1e-12 && x > best)) best = x
  return best
}
export function move(p: number, n: number): number {
  const i = INDEX.get(r2(p))
  if (i === undefined) return nearest(p)
  return LADDER[Math.max(0, Math.min(LADDER.length - 1, i + n))]
}
/** Prices from `above` ticks over the centre down to `below` ticks under it (highest first). */
export function window(centre: number, above: number, below: number): number[] {
  const c = INDEX.get(r2(centre)) ?? INDEX.get(nearest(centre))!
  const hi = Math.min(LADDER.length - 1, c + above), lo = Math.max(0, c - below)
  const rows: number[] = []
  for (let i = hi; i >= lo; i--) rows.push(LADDER[i])
  return rows
}
