import { useEffect, useState } from 'react'
import type { MarketState } from './api'
import { money } from './maths'

interface Props {
  marketId: string
  market: MarketState
  onGreen: (hard: boolean) => void
}

/** Whole-market view: what you make or lose for each result, and one-click Green up / Hard close. */
function countdown(start: string | null, inPlay: boolean, now: number): string {
  if (inPlay) return 'In play'
  if (!start) return ''
  const s = Math.round((new Date(start).getTime() - now) / 1000)
  if (s <= 0) return 'Due off'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`
}

/** Strip above the ladders (as in Bet Angel): time to the off, matched total, and the back / lay book percentages. */
function Strip({ market }: { market: MarketState }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t) }, [])
  const sels = Object.values(market.selections)
  const matched = Math.round(sels.reduce((a, s) => a + s.traded.reduce((x, y) => x + y[1], 0), 0))
  const bb = sels.map(s => s.backs[0]?.[0]), ll = sels.map(s => s.lays[0]?.[0])
  const book = (xs: (number | undefined)[]) => {
    const v = xs.filter((x): x is number => !!x)
    return v.length && v.length === xs.length ? v.reduce((a, x) => a + 100 / x, 0).toFixed(1) + '%' : '–'
  }
  return (
    <div className="mstrip">
      <b>{market.event}</b><span className="muted"> · {market.name}</span>
      <span className={'clock' + (market.in_play ? ' live' : '')}>{countdown(market.start, market.in_play, now)}</span>
      <span className="muted">Matched <b>£{matched.toLocaleString('en-GB')}</b></span>
      <span className="spacer" />
      <span className="book" title="Back book: add up 1/price of the best back prices. Over 100% is normal."><i>Back</i> {book(bb)}</span>
      <span className="book" title="Lay book: add up 1/price of the best lay prices. Under 100% is normal."><i>Lay</i> {book(ll)}</span>
    </div>
  )
}

export function MarketHeader({ market }: { market: MarketState }) { return <Strip market={market} /> }

export default function MarketPanel({ market, onGreen }: Props) {
  const o = market.outcomes
  if (!o) return null
  const worst = Math.min(...Object.values(o)), best = Math.max(...Object.values(o))
  return (
    <div className="mpanel">
      <div className="mtitle muted small">P&L by result</div>
      <div className="outcomes">
        {Object.entries(o).map(([sid, v]) => (
          <div key={sid} className={'outcome ' + (v >= 0 ? 'gain-box' : 'loss-box')} title={`If ${market.runners[sid] ?? sid} wins`}>
            <small>{market.runners[sid] ?? sid} wins</small><b>{money(v)}</b>
          </div>
        ))}
      </div>
      <div className="mactions">
        {market.green && market.green.bets.length > 0
          ? <button className={'primary' + (market.green.locked < 0 ? ' lossbtn' : '')} onClick={() => onGreen(false)}
                    title="Places the hedge bets at the prices available now">Green up · {money(market.green.locked)}{market.green.level ? '' : ' (approx)'}</button>
          : <span className="muted small">{best - worst < 0.005 ? 'Level — nothing to green' : market.green ? 'Level to within the £1 minimum stake' : 'No prices to green at'}</span>}
        <button onClick={() => onGreen(true)} title="Cancel all unmatched orders, then green up at once">Hard close</button>
      </div>
    </div>
  )
}
