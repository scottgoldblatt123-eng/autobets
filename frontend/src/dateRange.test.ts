import { describe, expect, it } from 'vitest'
import { cmpRange, presetRange, rangeQuery, initialRange } from './DateRange'

const now = new Date(2026, 10, 6)           // Fri 6 Nov 2026
describe('date range presets', () => {
  it('works out the common presets', () => {
    expect(presetRange('7', now)).toEqual({ start: '2026-10-31', end: '2026-11-06' })
    expect(presetRange('week', now)).toEqual({ start: '2026-11-02', end: '2026-11-06' })
    expect(presetRange('lastweek', now)).toEqual({ start: '2026-10-26', end: '2026-11-01' })
    expect(presetRange('lastmonth', now)).toEqual({ start: '2026-10-01', end: '2026-10-31' })
    expect(presetRange('year', now)).toEqual({ start: '2026-01-01', end: '2026-11-06' })
  })
  it('compares against the previous period or last year', () => {
    expect(cmpRange('prev', { start: '2026-10-01', end: '2026-10-31' })).toEqual({ start: '2026-09-01', end: '2026-09-30' })
    expect(cmpRange('lastyear', { start: '2026-10-01', end: '2026-10-31' })).toEqual({ start: '2025-10-01', end: '2025-10-31' })
    expect(cmpRange('prev', { start: '2026-10-25', end: '2026-10-31' })).toEqual({ start: '2026-10-18', end: '2026-10-24' })
  })
  it('builds the query', () => {
    const s = initialRange()
    expect(rangeQuery(s)).toBe(`start=${s.range.start}&end=${s.range.end}`)
    expect(rangeQuery({ ...s, compare: true })).toContain('&cstart=')
  })
})
