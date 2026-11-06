import type { MarketState, Order } from './api'

type Side = 'BACK' | 'LAY'
import { money } from './maths'

/** The standard Betfair market view: one row per runner, three back and three lay prices, your position, click a price to bet at it with the stake in the toolbar. */
const size = (n: number) => (n >= 1000 ? `£${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : `£${Math.round(n)}`)
const LEVELS = 3

export default function MarketGrid({ market, orders, onClick, onLadder, onSlip }: {
  market: MarketState; orders: Order[]; onClick: (selectionId: string, side: Side, price: number) => void; onLadder: (selectionId: string) => void
  onSlip: (selectionId: string, side: Side, price: number) => void
}) {
  const ids = Object.keys(market.runners)
  const susp = market.status && market.status !== 'OPEN'
  const mine = (sid: string, side: Side, price: number) => orders.some(o => o.selection_id === sid && o.side === side && Math.abs(o.price - price) < 1e-9)
  return (
    <div className="card mgrid" aria-label={`Market grid for ${market.event}`}>
      <div className="mgrid-head muted small"><span>{susp ? `Market ${market.status!.toLowerCase()}` : market.in_play ? 'In play' : 'Pre-match'}</span><span>Back</span><span>Lay</span></div>
      <div className="mgrid-body">
        {ids.map(sid => {
          const s = market.selections[sid], out = market.outcomes?.[sid]
          const backs = (s?.backs ?? []).slice(0, LEVELS), lays = (s?.lays ?? []).slice(0, LEVELS)
          const cell = (side: Side, i: number) => {
            const lv = (side === 'BACK' ? backs : lays)[i]
            return lv
              ? <button key={side + i} className={'cell ' + (side === 'BACK' ? 'back' : 'lay') + (mine(sid, side, lv[0]) ? ' mine' : '')} disabled={!!susp} onClick={() => onClick(sid, side, lv[0])} onContextMenu={e => { e.preventDefault(); onSlip(sid, side, lv[0]) }}
                  title={`${side === 'BACK' ? 'Back' : 'Lay'} at ${lv[0]}`}><b>{lv[0]}</b><small>{size(lv[1])}</small></button>
              : <span key={side + i} className={'cell ' + (side === 'BACK' ? 'back' : 'lay')} />
          }
          return (
            <div key={sid} className="mgrid-row">
              <div className="mgrid-name"><b>{market.runners[sid]}</b>
                <span className="small muted">{s?.last != null ? `Last ${s.last}` : ''}{out != null && Math.abs(out) > 0.004 ? ' · ' : ''}{out != null && Math.abs(out) > 0.004 && <span className={out >= 0 ? 'gain' : 'loss'}>{money(out)} if wins</span>}</span></div>
              <button className="sm mgrid-lad" title="Bet slip: choose your own price, stake and what happens if unmatched" onClick={() => onSlip(sid, 'BACK', backs[0]?.[0] ?? lays[0]?.[0] ?? 2)}>Bet…</button>
              <button className="sm mgrid-lad" title="Open this runner's ladder" onClick={() => onLadder(sid)}>▦</button>
              <div className="mgrid-prices">{[2, 1, 0].map(i => cell('BACK', i))}{[0, 1, 2].map(i => cell('LAY', i))}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
