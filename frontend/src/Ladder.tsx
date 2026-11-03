import { useEffect, useMemo, useRef } from 'react'
import type { MarketState, Order, Trigger } from './api'
import { hedge, matchedShare, money, weightOfMoney, type Position, type Side } from './maths'
import PriceChart from './PriceChart'
import { nearest, window as tickWindow } from './ticks'

export interface Props {
  market: MarketState; marketId: string; selectionId: string; orders: Order[]
  presets: number[]; stakeText: string; defaultStake: number; stakeBad: boolean; onStakeText: (t: string) => void; pnlSide: 'left' | 'right'
  reverse: boolean; rows: number; onRows: (n: number) => void; womLevels: number; showChart: boolean; showTotal: boolean; centre: number | null; autoCentre: boolean; active: boolean
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
  onRecentre: () => void
}

const fmtSize = (s: number) => (s >= 1000 ? (s / 1000).toFixed(1) + 'k' : s.toFixed(0))

const MIN_ROWS = 7, MIN_CHART = 70

export default function Ladder(p: Props) {
  const card = useRef<HTMLDivElement>(null), rowsEl = useRef<HTMLDivElement>(null), chartEl = useRef<HTMLDivElement>(null)
  /** Drag the bar under the ladder: down adds price rows and shrinks the chart, up does the reverse. */
  const startDrag = (e: React.PointerEvent) => {
    e.preventDefault()
    const startY = e.clientY, startRows = p.rows
    const rowH = rowsEl.current && p.rows ? rowsEl.current.clientHeight / p.rows : 23
    const chrome = card.current && rowsEl.current ? card.current.clientHeight - rowsEl.current.clientHeight - (chartEl.current?.clientHeight ?? 0) : 0
    const maxRows = card.current ? Math.floor((card.current.clientHeight - chrome - (p.showChart ? MIN_CHART : 0)) / rowH) : 61
    const move = (ev: PointerEvent) => p.onRows(Math.max(MIN_ROWS, Math.min(Math.max(MIN_ROWS, maxRows), 61, startRows + Math.round((ev.clientY - startY) / rowH))))
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); document.body.classList.remove('dragging') }
    document.body.classList.add('dragging')
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
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
    const above = Math.floor((p.rows - 1) / 2)
    let rows = tickWindow(centre, above, p.rows - 1 - above)           // highest price first
    if (p.reverse) rows = [...rows].reverse()                            // reversed ladder: lowest price at the top
    const back = new Map(sel.backs), lay = new Map(sel.lays), traded = new Map(sel.traded)
    const maxTraded = Math.max(1, ...rows.map(r => traded.get(r) ?? 0))
    const ltp = sel.last
    const hi = Math.max(...rows), lo = Math.min(...rows)
    const away = ltp == null ? '' : ltp > hi ? '▲' : ltp < lo ? '▼' : ''
    const rs = new Map(sel.recent?.short ?? []), rl = new Map(sel.recent?.long ?? [])
    const maxRecent = Math.max(1, ...rows.map(r => rl.get(r) ?? 0))
    return { rows, back, lay, traded, maxTraded, ltp, away, rs, rl, maxRecent }
  }, [sel, ref, p.centre, p.autoCentre, p.rows, p.reverse])
  const wom = useMemo(() => (sel ? weightOfMoney(sel.backs, sel.lays, p.womLevels) : null), [sel, p.womLevels])
  const share = useMemo(() => matchedShare(sel?.traded ?? [], Object.values(p.market.selections).map(s => s.traded)), [sel, p.market.selections])

  const noVolume = Object.values(p.market.selections).every(s => s.traded.length === 0)

  if (!sel || !view) return <div className="ladder"><div className="ladder-head"><b>{name}</b> · no data</div></div>
  const open = pos && (Math.abs(pos.win) > 0.004 || Math.abs(pos.lose) > 0.004)
  const bestBack = sel.backs[0]?.[0], bestLay = sel.lays[0]?.[0]
  const nBack = mine.filter(o => o.side === 'BACK').length, nLay = mine.filter(o => o.side === 'LAY').length
  // The figure Bet Angel shows beside the runner name: what you make if this runner's result is the one that lands worst/best, kept simple as win / lose.
  const level = open ? Math.min(pos!.win, pos!.lose) : 0

  return (
    <div ref={card} className={'ladder ba' + (p.active ? ' active' : '') + (p.showTotal ? ' with-total' : '') + (p.pnlSide === 'right' ? ' pnl-right' : '')} onMouseEnter={p.onHover}
         onWheel={e => { p.onWheel((e.deltaY > 0 ? -1 : 1) * (p.reverse ? -1 : 1)) }}>
      <div className="ladder-head">
        <div className="ladder-title"><b>{name}</b></div>
        <span className={'pnl ' + (level > 0.004 ? 'gain' : level < -0.004 ? 'loss' : 'muted')} title="Worst case on this runner (the smaller of 'win' and 'lose')">{money(level).replace('+', '')}</span>
        <button className="sm" onClick={p.onClose} disabled={!open} title="Close this runner's position (C)">Close</button>
        <button className="sm" onClick={p.onCancelAll} disabled={!mine.length} title="Cancel all unmatched orders on this runner">Cancel</button>
        <button className="sm" onClick={p.onRecentre} title="Recentre (Enter)">⌖</button>
      </div>
      <div className="ladder-pos">
        {open ? (<>
          <span title="Profit if this selection wins" className={pos!.win >= 0 ? 'gain' : 'loss'}>win {money(pos!.win)}</span>
          <span title="Profit if this selection loses" className={pos!.lose >= 0 ? 'gain' : 'loss'}>lose {money(pos!.lose)}</span>
        </>) : <span className="muted">no position</span>}
        {view.away && <span className="muted" title="The last traded price is outside the visible ladder — recentre (Enter)">{view.away} price {view.ltp?.toFixed(2)}</span>}
      </div>
      <div className="stakes" title="This ladder's stake. Keys 1–8 pick a preset while the mouse is over the ladder. Empty = the toolbar stake.">
        {p.presets.map(v => <button key={v} className={'chipbtn tiny' + (Number(p.stakeText) === v ? ' on' : '')} onClick={() => p.onStakeText(Number(p.stakeText) === v ? '' : String(v))}>{v}</button>)}
        <input inputMode="decimal" className={(p.stakeBad ? 'bad ' : '') + (p.stakeText.trim() !== '' && !p.stakeBad ? 'on' : '')} placeholder={String(p.defaultStake)}
               value={p.stakeText} onChange={e => p.onStakeText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') (e.target as HTMLInputElement).blur() }} />
      </div>
      <div className="wom" title={wom ? `Weight of money: ${wom.back}% of the money in the best ${p.womLevels} prices is available to back, ${wom.lay}% to lay. ${wom.back >= wom.lay ? '▲ back side heavier' : '▼ lay side heavier'}` : 'No money in the book'}>
        <span className="bets">{nBack} bets</span>
        <span className="b">{wom ? wom.back + '%' : '–'}</span>
        <span className="arrow">{wom ? (wom.back >= wom.lay ? '▲' : '▼') : ''}</span>
        <span className="l">{wom ? wom.lay + '%' : '–'}</span>
        <span className="bets">{nLay} bets</span>
      </div>
      <div className="rows" ref={rowsEl}>
        {view.rows.map(price => {
          const b = view.back.get(price), l = view.lay.get(price), t = view.traded.get(price) ?? 0
          const here = mine.filter(o => o.price === price)
          const hereB = here.filter(o => o.side === 'BACK'), hereL = here.filter(o => o.side === 'LAY')
          const green = open ? hedge(pos!, price) : null
          const trg = p.triggers.filter(t => t.price === price)
          const isLtp = view.ltp === price
          const backZone = bestBack != null && price <= bestBack, layZone = bestLay != null && price >= bestLay
          const cancel = (e: React.MouseEvent) => { e.stopPropagation(); (here.length || trg.length) && p.onCancelAt(price) }
          return (
            <div key={price} className={'grid lrow' + (isLtp ? ' ltp' : '')} onContextMenu={e => { e.preventDefault(); p.onContext(price, e.clientX, e.clientY) }}>
              <button className={'cell green ' + (green ? (green.locked >= 0 ? 'gain' : 'loss') : '')} disabled={!green}
                      onClick={() => green && p.onHedge(price)} title={green ? `Hedge here: ${green.side} £${green.stake.toFixed(2)} at ${price.toFixed(2)}, locks ${money(green.locked)}` : ''}>
                {green ? green.locked.toFixed(2) : ''}</button>
              <button className="cell minecol" onClick={cancel} title={hereB.length ? 'Your back bets here (click to cancel)' : ''}>
                {hereB.map(o => <span key={o.order_id} className="chip back">{o.remaining.toFixed(0)}</span>)}</button>
              <button className={'cell back' + (b ? '' : backZone ? ' zone' : ' none')} onClick={() => p.onClick('BACK', price)} title={`Back at ${price}`}>{b ? fmtSize(b) : ''}</button>
              <div className={'cell price' + (isLtp ? ' last' : '')}>{price.toFixed(2)}</div>
              <button className={'cell lay' + (l ? '' : layZone ? ' zone' : ' none')} onClick={() => p.onClick('LAY', price)} title={`Lay at ${price}`}>{l ? fmtSize(l) : ''}</button>
              <button className="cell minecol" onClick={cancel} title={hereL.length || trg.length ? 'Your lay bets / stops here (click to cancel)' : ''}>
                {hereL.map(o => <span key={o.order_id} className="chip lay">{o.remaining.toFixed(0)}</span>)}
                {trg.map(t => <span key={t.id} className={'chip trig ' + (t.label === 'stop loss' ? 'sl' : 'tp')} title={`${t.label}: greens up when the price reaches ${t.price.toFixed(2)} (click to remove)`}>{t.label === 'stop loss' ? 'SL' : 'TP'}</span>)}</button>
              <div className="cell recent" title={`Matched here: £${(view.rs.get(price) ?? 0).toFixed(0)} in the last ${sel.recent?.short_s ?? 0}s, £${(view.rl.get(price) ?? 0).toFixed(0)} in the last ${Math.round((sel.recent?.long_s ?? 0) / 60)} min${sel.recent && sel.recent.long_span < sel.recent.long_s ? ` (only ${Math.round(sel.recent.long_span)}s of history so far)` : ''}`}>
                <i className="long" style={{ width: `${((view.rl.get(price) ?? 0) / view.maxRecent) * 100}%` }} />
                <i className="short" style={{ width: `${((view.rs.get(price) ?? 0) / view.maxRecent) * 100}%` }} />
                {(view.rs.get(price) ?? 0) > 0 ? <span>{fmtSize(view.rs.get(price)!)}</span> : null}
              </div>
              {p.showTotal && <div className="cell vol" title="Total matched at this price"><i style={{ width: `${(t / view.maxTraded) * 100}%` }} />{t ? <span>{fmtSize(t)}</span> : null}</div>}
            </div>
          )
        })}
      </div>
      <div className="foot" title="Matched on this runner, and its share of everything matched in the market">
        {noVolume ? <span className="muted" title="Betfair is not sending matched volumes for this market (a delayed key may withhold them)">volume not available</span>
          : <>£{share.volume.toLocaleString('en-GB')} <span className="muted">({share.pct.toFixed(1)}%)</span></>}
      </div>
      {p.showChart && <div className="dragbar" onPointerDown={startDrag} title="Drag down for more price rows, up for a bigger chart"><i /></div>}
      {p.showChart && <div className="chartwrap" ref={chartEl}><PriceChart marketId={p.marketId} selectionId={p.selectionId} /></div>}
    </div>
  )
}
