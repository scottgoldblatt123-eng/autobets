import { useEffect, useMemo } from 'react'
import type { MarketState, Order, Trigger } from './api'
import { hedge, money, type Position, type Side } from './maths'
import { nearest, window } from './ticks'

export interface Props {
  market: MarketState; marketId: string; selectionId: string; orders: Order[]
  ticksShown: number; centre: number | null; autoCentre: boolean; active: boolean
  onSetCentre: (c: number) => void
  triggers: Trigger[]
  onHedge: (price: number) => void
  onContext: (price: number, x: number, y: number) => void
  onClick: (side: Side, price: number) => void
  onCancelAt: (price: number) => void
  onWheel: (dir: number) => void
  onHover: () => void
  onCancelAll: () => void
  onClose: () => void
  onRemove: () => void
  onRecentre: () => void
}

const fmtSize = (s: number) => (s >= 1000 ? (s / 1000).toFixed(1) + 'k' : s.toFixed(0))

export default function Ladder(p: Props) {
  const sel = p.market.selections[p.selectionId]
  const name = p.market.runners[p.selectionId] ?? p.selectionId
  const pos: Position | undefined = p.market.positions[p.selectionId]
  const mine = p.orders.filter(o => o.selection_id === p.selectionId)

  const ref = useMemo(() => {
    if (!sel) return null
    const bb = sel.backs[0]?.[0], bl = sel.lays[0]?.[0]
    return sel.last ?? (bb && bl ? (bb + bl) / 2 : bb ?? bl ?? null)
  }, [sel])
  // The ladder keeps its centre until the user recentres (Enter / ⌖), unless auto-recentre is switched on.
  useEffect(() => { if (!p.autoCentre && p.centre == null && ref != null) p.onSetCentre(nearest(ref)) }, [p.autoCentre, p.centre, ref]) // eslint-disable-line react-hooks/exhaustive-deps

  const view = useMemo(() => {
    if (!sel || ref == null) return null
    const centre = p.autoCentre || p.centre == null ? nearest(ref) : p.centre
    const rows = window(centre, p.ticksShown, p.ticksShown)
    const back = new Map(sel.backs), lay = new Map(sel.lays), traded = new Map(sel.traded)
    const maxTraded = Math.max(1, ...rows.map(r => traded.get(r) ?? 0))
    const ltp = sel.last
    const away = ltp == null ? '' : ltp > rows[0] ? '▲' : ltp < rows[rows.length - 1] ? '▼' : ''
    return { rows, back, lay, traded, maxTraded, ltp, away }
  }, [sel, ref, p.centre, p.autoCentre, p.ticksShown])

  if (!sel || !view) return <div className="ladder"><div className="ladder-head"><b>{name}</b> · no data</div></div>
  const open = pos && (Math.abs(pos.win) > 0.004 || Math.abs(pos.lose) > 0.004)

  return (
    <div className={'ladder' + (p.active ? ' active' : '')} onMouseEnter={p.onHover}
         onWheel={e => { p.onWheel(e.deltaY > 0 ? -1 : 1) }}>
      <div className="ladder-head">
        <div className="ladder-title">
          <b>{name}</b>
          <span className="muted">{p.market.event} · {p.market.name}{p.market.in_play ? ' · ● in play' : ''}</span>
        </div>
        <button className="icon" title="Remove ladder" onClick={p.onRemove}>✕</button>
      </div>
      <div className="ladder-pos">
        {open ? (<>
          <span title="Profit if this selection wins" className={pos!.win >= 0 ? 'gain' : 'loss'}>win {money(pos!.win)}</span>
          <span title="Profit if this selection loses" className={pos!.lose >= 0 ? 'gain' : 'loss'}>lose {money(pos!.lose)}</span>
        </>) : <span className="muted">no position</span>}
        {view.away && <span className="muted" title="The last traded price is outside the visible ladder — recentre (Enter)">{view.away} price {view.ltp?.toFixed(2)}</span>}
        <span className="spacer" />
        <button className="sm" onClick={p.onClose} disabled={!open} title="Close position (C)">Close</button>
        <button className="sm" onClick={p.onCancelAll} disabled={!mine.length} title="Cancel all unmatched">Cancel</button>
        <button className="sm" onClick={p.onRecentre} title="Recentre (Enter)">⌖</button>
      </div>
      <div className="grid head">
        <div>Green</div><div>Vol</div><div>Back</div><div>Price</div><div>Lay</div><div>Mine</div>
      </div>
      <div className="rows">
        {view.rows.map(price => {
          const b = view.back.get(price), l = view.lay.get(price), t = view.traded.get(price) ?? 0
          const here = mine.filter(o => o.price === price)
          const green = open ? hedge(pos!, price) : null
          const trg = p.triggers.filter(t => t.price === price)
          const isLtp = view.ltp === price
          return (
            <div key={price} className={'grid lrow' + (isLtp ? ' ltp' : '')} onContextMenu={e => { e.preventDefault(); p.onContext(price, e.clientX, e.clientY) }}>
              <button className={'cell green ' + (green ? (green.locked >= 0 ? 'gain' : 'loss') : '')} disabled={!green}
                      onClick={() => green && p.onHedge(price)} title={green ? `Hedge here: ${green.side} £${green.stake.toFixed(2)} at ${price.toFixed(2)}, locks ${money(green.locked)}` : ''}>
                {green ? green.locked.toFixed(2) : ''}</button>
              <div className="cell vol"><i style={{ width: `${(t / view.maxTraded) * 100}%` }} />{t ? <span>{fmtSize(t)}</span> : null}</div>
              <button className="cell back" onClick={() => p.onClick('BACK', price)} title={`Back at ${price}`}>{b ? fmtSize(b) : ''}</button>
              <div className="cell price">{price.toFixed(2)}</div>
              <button className="cell lay" onClick={() => p.onClick('LAY', price)} title={`Lay at ${price}`}>{l ? fmtSize(l) : ''}</button>
              <button className="cell mine" onClick={() => (here.length || trg.length) && p.onCancelAt(price)} title={here.length || trg.length ? 'Cancel the orders / stops here' : ''}>
                {here.map(o => <span key={o.order_id} className={'chip ' + o.side.toLowerCase()}>{o.side[0]}{o.remaining.toFixed(0)}</span>)}
                {trg.map(t => <span key={t.id} className={'chip trig ' + (t.label === 'stop loss' ? 'sl' : 'tp')} title={`${t.label}: greens up when the price reaches ${t.price.toFixed(2)} (click to remove)`}>{t.label === 'stop loss' ? 'SL' : 'TP'}</span>)}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
