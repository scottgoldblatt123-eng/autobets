import { describe, expect, it } from 'vitest'
import { gaps, modelOdds } from './modelGap'

const sel = (b: number, l: number) => ({ backs: [[b, 100]] as [number, number][], lays: [[l, 100]] as [number, number][], traded: [], last: null })
const ctx = { kind: 'tennis', live: true, source: 'x', status: 'Set 1', players: ['Paul', 'Halys'] as [string, string], model: { odds: [1.5, 3.0], p: [66, 34], version: 'v' } }

describe('model gap', () => {
  it('maps model prices onto runners by name and flags back / lay value in ticks', () => {
    const market = { runners: { '1': 'Paul', '2': 'Halys' }, selections: { '1': sel(1.62, 1.63), '2': sel(2.8, 2.82) } } as never
    const g = gaps(market, ctx as never)
    expect(g).toHaveLength(2)
    expect(g[0].verdict).toBe('back'); expect(g[0].backTicks).toBeGreaterThan(5)      // market 1.62 vs fair 1.50
    expect(g[1].verdict).toBe('lay'); expect(g[1].layTicks).toBeGreaterThan(2)         // market 2.82 lay vs fair 3.00
  })
  it('shows nothing when names do not line up or there is no model', () => {
    expect(modelOdds(ctx as never, { '1': 'Smith', '2': 'Jones' })).toBeNull()
    expect(gaps({ runners: { '1': 'Paul', '2': 'Halys' }, selections: {} } as never, { ...ctx, model: null } as never)).toEqual([])
  })
  it('handles football home / draw / away', () => {
    const f = { kind: 'football', live: true, source: 'x', status: '2H', teams: ['Arsenal', 'Chelsea'] as [string, string], model: { home: 0.5, draw: 0.3, away: 0.2, version: 'v' } }
    const o = modelOdds(f as never, { '1': 'Arsenal', '2': 'Chelsea', '3': 'The Draw' })
    expect(o).toEqual({ '1': 2, '2': 5, '3': 1 / 0.3 })
  })
})
