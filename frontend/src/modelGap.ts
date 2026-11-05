import { tickIndex } from './ticks'
import type { MatchCtx, MarketState } from './api'

export interface Gap { name: string; model: number; back?: number; lay?: number; backTicks: number; layTicks: number; verdict: 'back' | 'lay' | 'none' }

const norm = (s: string) => s.toLowerCase().replace(/[^a-z ]/g, ' ').replace(/\s+/g, ' ').trim()
const same = (a: string, b: string) => { const x = norm(a), y = norm(b); return !!x && !!y && (x === y || x.includes(y) || y.includes(x) || x.split(' ').pop() === y.split(' ').pop()) }

/** Fair price per runner from the live model, in Betfair runner order. null if the model or names don't line up. */
export function modelOdds(ctx: MatchCtx | undefined, runners: Record<string, string>): Record<string, number> | null {
  const m = ctx?.model
  if (!ctx || !m) return null
  const out: Record<string, number> = {}
  if (ctx.kind === 'tennis' && m.odds && ctx.players) {
    for (const [sid, name] of Object.entries(runners)) {
      const i = ctx.players.findIndex(p => same(p, name))
      if (i >= 0 && m.odds[i]) out[sid] = m.odds[i]
    }
  } else if (ctx.kind === 'football' && m.home != null && ctx.teams) {
    for (const [sid, name] of Object.entries(runners)) {
      if (norm(name).includes('draw')) { if (m.draw) out[sid] = 1 / m.draw }
      else if (same(ctx.teams[0], name)) { if (m.home) out[sid] = 1 / m.home }
      else if (same(ctx.teams[1], name)) { if (m.away) out[sid] = 1 / m.away }
    }
  }
  return Object.keys(out).length === Object.keys(runners).length ? out : null
}

/** Model fair price against the best back and lay, in ticks. Back value: the market pays more than the model says is fair.
 *  Lay value: the market pays less than the model says is fair. Positive ticks = the size of the gap; a gap of 0-1 tick is noise. */
export function gaps(market: Pick<MarketState, 'selections' | 'runners'>, ctx: MatchCtx | undefined): Gap[] {
  const fair = modelOdds(ctx, market.runners)
  if (!fair) return []
  return Object.entries(fair).map(([sid, model]) => {
    const s = market.selections[sid], back = s?.backs[0]?.[0], lay = s?.lays[0]?.[0]
    const backTicks = back ? tickIndex(back) - tickIndex(model) : 0
    const layTicks = lay ? tickIndex(model) - tickIndex(lay) : 0
    const verdict = backTicks >= 2 && backTicks >= layTicks ? 'back' : layTicks >= 2 ? 'lay' : 'none'
    return { name: market.runners[sid], model, back, lay, backTicks, layTicks, verdict }
  })
}
