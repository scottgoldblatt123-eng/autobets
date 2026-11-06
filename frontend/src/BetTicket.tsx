import { useEffect, useState } from 'react'
import type { MarketState } from './api'
import { move, nearest } from './ticks'
import { orderSize, type Side } from './maths'

export type Persist = 'CANCEL' | 'KEEP' | 'TAKE_SP'
export interface TicketBet { selectionId: string; side: Side; price: number; stake: number; layBasis: 'stake' | 'liability'; persistence: Persist; fokS: number }

/** A bet slip like Betfair's: choose back or lay, set any price (it can sit unmatched in the queue), the stake, and what happens to the unmatched part. */
export default function BetTicket({ market, selectionId, side: side0, price: price0, defaultStake, layBasis: basis0, persistence: pers0, onPlace, onClose }: {
  market: MarketState; selectionId: string; side: Side; price: number; defaultStake: number; layBasis: 'stake' | 'liability'; persistence: Persist
  onPlace: (b: TicketBet) => void; onClose: () => void
}) {
  const [sel, setSel] = useState(selectionId), [side, setSide] = useState<Side>(side0), [price, setPrice] = useState(String(price0))
  const [stake, setStake] = useState(String(defaultStake)), [basis, setBasis] = useState(basis0), [pers, setPers] = useState<Persist>(pers0), [fok, setFok] = useState('')
  useEffect(() => { setSel(selectionId); setSide(side0); setPrice(String(price0)) }, [selectionId, side0, price0])     // a new right-click reloads the slip
  const s = market.selections[sel], bestBack = s?.backs[0]?.[0], bestLay = s?.lays[0]?.[0]
  const p = Number(price), amount = Number(stake.replace(/[£,\s]/g, ''))
  const valid = Number.isFinite(p) && p >= 1.01 && p <= 1000, ok = valid && amount >= 1
  const snap = () => { if (valid) setPrice(String(nearest(p))) }
  const step = (n: number) => setPrice(String(move(valid ? nearest(p) : (bestBack ?? 2), n)))
  const size = ok ? (side === 'LAY' ? orderSize('LAY', nearest(p), amount, basis) : amount) : 0
  const pp = valid ? nearest(p) : 0
  const crosses = valid && ((side === 'BACK' && bestBack != null && pp <= bestBack) || (side === 'LAY' && bestLay != null && pp >= bestLay))
  const note = !valid ? 'Enter a price between 1.01 and 1000' : crosses ? 'This price is available now, so it should match straight away (at the best price on offer, which can be better than yours)' : 'This price is not available yet: the unmatched bet joins the queue at that price and waits'
  const susp = market.status && market.status !== 'OPEN'
  return (
    <div className="card bticket" aria-label="Bet slip">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <b>Bet slip</b>
        <button className="sm" aria-label="Close bet slip" onClick={onClose}>×</button>
      </div>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label>Runner<select value={sel} onChange={e => setSel(e.target.value)}>{Object.entries(market.runners).map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select></label>
        <div className="viewsw" role="group" aria-label="Side"><button className={side === 'BACK' ? 'on back' : ''} onClick={() => setSide('BACK')}>Back</button><button className={side === 'LAY' ? 'on lay' : ''} onClick={() => setSide('LAY')}>Lay</button></div>
        <label>Price<span className="row" style={{ gap: 2 }}><button className="sm" onClick={() => step(-1)} aria-label="One tick lower">−</button>
          <input inputMode="decimal" style={{ width: 70 }} value={price} onChange={e => setPrice(e.target.value)} onBlur={snap} /><button className="sm" onClick={() => step(1)} aria-label="One tick higher">+</button></span></label>
        <label>{side === 'LAY' && basis === 'liability' ? 'Liability £' : 'Stake £'}<input inputMode="decimal" style={{ width: 70 }} value={stake} onChange={e => setStake(e.target.value)} /></label>
        {side === 'LAY' && <label>Lay by<select value={basis} onChange={e => setBasis(e.target.value as 'stake' | 'liability')}><option value="stake">Stake</option><option value="liability">Liability</option></select></label>}
        <label>If not matched<select value={pers} onChange={e => setPers(e.target.value as Persist)}>
          <option value="CANCEL">Cancel when the market turns in play</option><option value="KEEP">Keep in play</option><option value="TAKE_SP">Take Starting Price at the off</option></select></label>
        <label>Cancel after (s)<input inputMode="numeric" style={{ width: 56 }} placeholder="off" value={fok} onChange={e => setFok(e.target.value)} title="Fill or kill: cancel whatever is still unmatched after this many seconds" /></label>
      </div>
      <div className="small muted" style={{ margin: '6px 0' }}>{note}{ok && side === 'LAY' ? ` · stake £${size.toFixed(2)}, liability £${(size * (pp - 1)).toFixed(2)}` : ok ? ` · profit if it wins £${(size * (pp - 1)).toFixed(2)}` : ''}
        {bestBack != null && ` · best back ${bestBack}`}{bestLay != null && ` · best lay ${bestLay}`}</div>
      <div className="row"><button className="primary" disabled={!ok || !!susp} onClick={() => onPlace({ selectionId: sel, side, price: pp, stake: amount, layBasis: basis, persistence: pers, fokS: Number(fok) > 0 ? Number(fok) : 0 })}>{side === 'BACK' ? 'Place back bet' : 'Place lay bet'}</button>
        <button onClick={onClose}>Cancel</button>{susp && <span className="small muted">Market {market.status!.toLowerCase()}</span>}</div>
    </div>
  )
}
