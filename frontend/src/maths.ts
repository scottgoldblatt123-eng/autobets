export interface Position { win: number; lose: number }
export type Side = 'BACK' | 'LAY'
const r2 = (x: number) => Math.round(x * 100) / 100

export function applyFill(p: Position, side: Side, price: number, size: number): Position {
  const [w, l] = side === 'BACK' ? [size * (price - 1), -size] : [-size * (price - 1), size]
  return { win: r2(p.win + w), lose: r2(p.lose + l) }
}

/** Hedge that levels the position at `price` (mirror of backend pnl.hedge). */
export function hedge(p: Position, price: number): { side: Side; stake: number; locked: number } | null {
  const diff = p.lose - p.win
  if (Math.abs(diff) < 0.005) return null
  const stake = r2(Math.abs(diff) / price)
  const side: Side = diff > 0 ? 'BACK' : 'LAY'
  const after = applyFill(p, side, price, stake)
  return { side, stake, locked: r2(Math.min(after.win, after.lose)) }
}

/** Order size for a click: a stake, or a liability converted to a lay stake. */
export function orderSize(side: Side, price: number, amount: number, layBasis: 'stake' | 'liability'): number {
  if (side === 'LAY' && layBasis === 'liability') return r2(amount / (price - 1))
  return r2(amount)
}

export const money = (x: number) => (x < 0 ? '-' : x > 0 ? '+' : '') + '£' + Math.abs(x).toFixed(2)

/** Weight of money: share of the money waiting in the best `levels` prices on each side. */
export function weightOfMoney(backs: [number, number][], lays: [number, number][], levels: number): { back: number; lay: number } | null {
  const b = backs.slice(0, levels).reduce((a, x) => a + x[1], 0)
  const l = lays.slice(0, levels).reduce((a, x) => a + x[1], 0)
  if (b + l <= 0) return null
  const back = Math.round((b / (b + l)) * 100)
  return { back, lay: 100 - back }
}

/** Matched volume on a selection, and its share of the market's matched volume across all selections. */
export function matchedShare(traded: [number, number][], all: [number, number][][]): { volume: number; pct: number } {
  const sum = (t: [number, number][]) => t.reduce((a, x) => a + x[1], 0)
  const v = sum(traded), tot = all.reduce((a, t) => a + sum(t), 0)
  return { volume: Math.round(v), pct: tot > 0 ? Math.round((v / tot) * 1000) / 10 : 0 }
}

/** Parse a typed stake like "65", "£65", "12.50". Returns null unless it is at least £1 (two decimals at most are kept). */
export function parseStake(text: string): number | null {
  const t = text.replace(/[£,\s]/g, '')
  if (!/^\d+(\.\d+)?$/.test(t)) return null
  const v = Math.round(Number(t) * 100) / 100
  return v >= 1 ? v : null
}

/** Whole-market worst case if `stake` is placed on one runner at `price`: the figure the market P&L column shows. */
export function marketAfter(outcomes: Record<string, number>, selectionId: string, side: Side, stake: number, price: number): number {
  const vals = Object.entries(outcomes).map(([id, v]) => v + (side === 'BACK' ? (id === selectionId ? stake * (price - 1) : -stake) : (id === selectionId ? -stake * (price - 1) : stake)))
  return r2(Math.min(...vals))
}
