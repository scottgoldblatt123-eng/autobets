import { describe, expect, it } from 'vitest'
import { hedge, applyFill, orderSize, parseStake, weightOfMoney, matchedShare } from './maths'
import { move, nearest, isValid, window } from './ticks'

describe('ticks', () => {
  it('moves across band edges', () => {
    expect(move(1.99, 1)).toBe(2.0)
    expect(move(2.0, 1)).toBe(2.02)
    expect(move(3.95, 1)).toBe(4.0)
    expect(move(1.01, -3)).toBe(1.01)
  })
  it('validates prices', () => {
    expect(isValid(2.02)).toBe(true)
    expect(isValid(2.01)).toBe(false)
    expect(isValid(1.015)).toBe(false)
    expect(nearest(2.01)).toBe(2.02)
  })
  it('windows the ladder highest first', () => {
    const w = window(2.0, 3, 2)
    expect(w).toEqual([2.06, 2.04, 2.02, 2.0, 1.99, 1.98])
  })
})

describe('maths', () => {
  it('hedge levels the position', () => {
    const p = applyFill({ win: 0, lose: 0 }, 'BACK', 2.5, 10)   // win +15, lose -10
    const h = hedge(p, 2.0)!
    expect(h.side).toBe('LAY')
    const after = applyFill(p, h.side, 2.0, h.stake)
    expect(Math.abs(after.win - after.lose)).toBeLessThan(0.1)
    expect(h.locked).toBeGreaterThan(0)
  })
  it('liability converts to lay stake', () => {
    expect(orderSize('LAY', 3.0, 10, 'liability')).toBe(5)
    expect(orderSize('LAY', 3.0, 10, 'stake')).toBe(10)
    expect(orderSize('BACK', 3.0, 10, 'liability')).toBe(10)
  })
})

describe('stake box, weight of money, matched share', () => {
  it('parses typed stakes', () => {
    expect(parseStake('65')).toBe(65)
    expect(parseStake('£65')).toBe(65)
    expect(parseStake(' 12.505 ')).toBe(12.51)
    expect(parseStake('0.5')).toBeNull()
    expect(parseStake('abc')).toBeNull()
    expect(parseStake('')).toBeNull()
    expect(parseStake('-5')).toBeNull()
  })
  it('weight of money uses the best levels each side', () => {
    const w = weightOfMoney([[2, 300], [1.99, 100], [1.98, 100], [1.97, 9999]], [[2.02, 200], [2.04, 100], [2.06, 100], [2.08, 9999]], 3)
    expect(w).toEqual({ back: 56, lay: 44 })
    expect(weightOfMoney([], [], 3)).toBeNull()
  })
  it('matched share across the market', () => {
    const a: [number, number][] = [[2, 6200]], b: [number, number][] = [[3, 6700]]
    expect(matchedShare(a, [a, b])).toEqual({ volume: 6200, pct: 48.1 })
  })
})
