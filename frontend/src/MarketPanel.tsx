import type { MarketState } from './api'
import { money } from './maths'

interface Props {
  marketId: string
  market: MarketState
  onGreen: (hard: boolean) => void
}

/** Whole-market view: what you make or lose for each result, and one-click Green up / Hard close. */
export default function MarketPanel({ market, onGreen }: Props) {
  const o = market.outcomes
  if (!o) return null
  const worst = Math.min(...Object.values(o)), best = Math.max(...Object.values(o))
  return (
    <div className="mpanel">
      <div className="mtitle"><b>{market.event}</b><span className="muted"> · {market.name}</span></div>
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
