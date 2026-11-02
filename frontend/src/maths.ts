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
