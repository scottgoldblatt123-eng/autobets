import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { MarketState, Order, Trigger } from './api'
import { hedge, marketAfter, matchedShare, money, weightOfMoney, type Position, type Side } from './maths'
import PriceChart from './PriceChart'
import { nearest, window as tickWindow } from './ticks'

export interface Props {
  market: MarketState; marketId: string; selectionId: string; orders: Order[]
  presets: number[]; stakeText: string; defaultStake: number; stakeBad: boolean; onStakeText: (t: string) => void; pnlSide: 'left' | 'right'; pnlBasis: 'runner' | 'market'
  reverse: boolean; rows: number; onRows: (n: number) => void; womLevels: number; showChart: boolean; showTotal: boolean; centre: number | null; autoCentre: boolean; active: boolean
  onSetCentre: (c: number) => void
  triggers: Trigger[]
  onHedge: (price: number) => void
  onContext: (price: number, x: number, y: number) => void
  onClick: (side: Side, price: number) => void
  onCancelAt: (price: number) => void
  onMoveOrder: (orderId: string, price: number) => void
  onWheel: (dir: number) => void
  onHover: () => void
  onCancelAll: () => void
  onClose: () => void
  onRecentre: () => void
  runners: Record<string, string>; openIds: string[]; onSwitch: (selectionId: string) => void
}

const fmtSize = (s: number) => (s >= 1000 ? (s / 1000).toFixed(1) + 'k' : s.toFixed(0))

const MIN_ROWS = 7
const MIN_RH = 15, MAX_RH = 26, CHART_MIN = 96   // row height limits (px) and the smallest chart worth keeping before rows take its space

export default function Ladder(p: Props) {
  const card = useRef<HTMLDivElement>(null), rowsEl = useRef<HTMLDivElement>(null), chartEl = useRef<HTMLDivElement>(null)
  /** Vertical room (px) in this ladder's card for price rows plus chart, measured so the ladder never needs a scrollbar of its own. */
  const [avail, setAvail] = useState(61 * 22)
  const [chartH, setChartH] = useState(999)
  const chartMin = p.showChart ? CHART_MIN : 0
  const fit = Math.max(MIN_ROWS, Math.floor(avail / MIN_RH))                                        // most rows that can ever fit (rows squeezed to their smallest)
  const want = p.rows > 0 ? p.rows : Math.floor((avail - chartMin) / 22)                          // 0 = as many normal-sized rows as fit, leaving room for the chart
  const er = Math.max(MIN_ROWS, Math.min(want, fit, 61))                                          // rows actually shown
  const rh = Math.max(MIN_RH, Math.min(MAX_RH, Math.floor((avail - chartMin) / er)))             // row height: the ladder compresses (or relaxes) so the chosen number of ticks fits
  const rf = rh >= 21 ? 12 : rh >= 18 ? 11 : 10                                                    // text shrinks with the rows
  useLayoutEffect(() => {
    const el = card.current; if (!el) return
    const measure = () => {
      const rowsH = rowsEl.current?.clientHeight ?? 0, chartH = chartEl.current?.clientHeight ?? 0
      if (!rowsH) return
      const total = Math.max(el.clientHeight, el.scrollHeight)
      const chrome = total - rowsH - chartH
      const a = Math.max(MIN_ROWS * MIN_RH, el.clientHeight - chrome)
      setAvail(v => (Math.abs(v - a) < 1 ? v : a)); setChartH(chartH_ => (chartH_ === chartH ? chartH_ : chartH))
    }
    const ro = new ResizeObserver(measure); ro.observe(el); measure()
    return () => ro.disconnect()
  })
  /** Mouse wheel over the price rows moves the ladder and must never also scroll the page, which needs a non-passive listener (React's onWheel is passive). */
  const wheelRef = useRef(p.onWheel); wheelRef.current = p.onWheel
  const revRef = useRef(p.reverse); revRef.current = p.reverse
  useEffect(() => {
    const el = rowsEl.current; if (!el) return
    const onWheel = (e: WheelEvent) => { e.preventDefault(); if (e.deltaY) wheelRef.current((e.deltaY > 0 ? -1 : 1) * (revRef.current ? -1 : 1)) }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])
  /** Drag the bar under the ladder: down adds price rows and shrinks the chart (right down to no chart), up does the reverse. */
  const startDrag = (e: React.PointerEvent) => {
    e.preventDefault()
    const startY = e.clientY, startRows = er
    const rowH = rh
    const maxRows = fit
    const move = (ev: PointerEvent) => p.onRows(Math.max(MIN_ROWS, Math.min(maxRows, 61, startRows + Math.round((ev.clientY - startY) / rowH))))
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); document.body.classList.remove('dragging') }
    document.body.classList.add('dragging')
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const sel = p.market.selections[p.selectionId]
  const name = p.market.runners[p.selectionId] ?? p.selectionId
  const pos: Position | undefined = p.market.positions[p.selectionId]
  const mine = p.orders.filter(o => o.selection_id === p.selectionId)
  /** The net position in words, when it is a plain back or a plain lay (a lay: you keep the stake if it loses, pay out if it wins). */
  const plain = pos && pos.win < -0.004 && pos.lose > 0.004 ? { side: 'LAY' as const, stake: pos.lose, price: 1 - pos.win / pos.lose, tip: `You have laid £${pos.lose.toFixed(2)}: you keep it if this runner loses, and pay ${money(pos.win).replace('-', '')} if it wins.` }
    : pos && pos.win > 0.004 && pos.lose < -0.004 ? { side: 'BACK' as const, stake: -pos.lose, price: 1 + pos.win / -pos.lose, tip: `You have backed £${(-pos.lose).toFixed(2)}: you win ${money(pos.win)} if this runner wins, and lose the stake if it loses.` } : null

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
    const above = Math.floor((er - 1) / 2)
    let rows = tickWindow(centre, above, er - 1 - above)           // highest price first
    if (p.reverse) rows = [...rows].reverse()                            // reversed ladder: lowest price at the top
    const back = new Map(sel.backs), lay = new Map(sel.lays), traded = new Map(sel.traded)
    const maxTraded = Math.max(1, ...rows.map(r => traded.get(r) ?? 0))
    const ltp = sel.last
    const hi = Math.max(...rows), lo = Math.min(...rows)
    const away = ltp == null ? '' : ltp > hi ? '▲' : ltp < lo ? '▼' : ''
    const rs = new Map(sel.recent?.short ?? []), rl = new Map(sel.recent?.long ?? [])
    const maxRecent = Math.max(1, ...rows.map(r => rl.get(r) ?? 0))
    return { rows, back, lay, traded, maxTraded, ltp, away, rs, rl, maxRecent }
  }, [sel, ref, p.centre, p.autoCentre, er, p.reverse])
  const wom = useMemo(() => (sel ? weightOfMoney(sel.backs, sel.lays, p.womLevels) : null), [sel, p.womLevels])
  const share = useMemo(() => matchedShare(sel?.traded ?? [], Object.values(p.market.selections).map(s => s.traded)), [sel, p.market.selections])

  const noVolume = Object.values(p.market.selections).every(s => s.traded.length === 0)
  const mstatus = p.market.status ?? 'OPEN', rstatus = sel?.status ?? 'ACTIVE'
  const blocked = mstatus !== 'OPEN' || rstatus !== 'ACTIVE'

  if (!sel || !view) return <div className="ladder"><div className="ladder-head"><b>{name}</b> · no data</div></div>
  const open = pos && (Math.abs(pos.win) > 0.004 || Math.abs(pos.lose) > 0.004)
  const bestBack = sel.backs[0]?.[0], bestLay = sel.lays[0]?.[0]
  const nBack = mine.filter(o => o.side === 'BACK').length, nLay = mine.filter(o => o.side === 'LAY').length
  // The figure Bet Angel shows beside the runner name: what you make if this runner's result is the one that lands worst/best, kept simple as win / lose.
  const level = open ? Math.min(pos!.win, pos!.lose) : 0

  return (
    <div ref={card} className={'ladder ba' + (p.active ? ' active' : '') + (p.showTotal ? ' with-total' : '') + (p.pnlSide === 'right' ? ' pnl-right' : '') + (blocked ? ' blocked' : '')} onMouseEnter={p.onHover}>
      <div className="ladder-head">
        <div className="ladder-title"><b>{name}</b>
          {Object.keys(p.runners).length > 1 && (
            <select className="switch" value="" onChange={e => e.target.value && p.onSwitch(e.target.value)} title="Switch this ladder to another runner in the market">
              <option value="">⇄</option>
              {Object.entries(p.runners).filter(([id]) => id !== p.selectionId).map(([id, n]) => <option key={id} value={id}>{n}{p.openIds.includes(id) ? ' (swap)' : ''}</option>)}
            </select>)}
        </div>
        <span className={'pnl ' + (level > 0.004 ? 'gain' : level < -0.004 ? 'loss' : 'muted')} title="Worst case on this runner (the smaller of 'win' and 'lose')">{money(level).replace('+', '')}</span>
        <button className="sm" onClick={p.onClose} disabled={!open} title="Close this runner's position (C)">Close</button>
        <button className="sm" onClick={p.onCancelAll} disabled={!mine.length} title="Cancel all unmatched orders on this runner">Cancel</button>
        <button className="sm" onClick={p.onRecentre} title="Recentre (Enter)">⌖</button>
      </div>
      <div className="ladder-pos">
        {open ? (<>
          {plain && <b className={'sidetag ' + plain.side.toLowerCase()} title={plain.tip}>{plain.side} £{plain.stake.toFixed(2)} @ {plain.price.toFixed(2)}</b>}
          <span title="Profit if this selection wins" className={pos!.win >= 0 ? 'gain' : 'loss'}>if {name.split(' ').pop()} wins {money(pos!.win)}</span>
          <span title="Profit if this selection loses" className={pos!.lose >= 0 ? 'gain' : 'loss'}>if {name.split(' ').pop()} loses {money(pos!.lose)}</span>
        </>) : <span className="muted">no position</span>}
        {view.away && <span className="muted" title="The last traded price is outside the visible ladder — recentre (Enter)">{view.away} price {view.ltp?.toFixed(2)}</span>}
      </div>
      <div className="stakes" title="This ladder's stake. Keys 1–8 pick a preset while the mouse is over the ladder. Empty = the toolbar stake.">
        {p.presets.map(v => <button key={v} className={'chipbtn tiny' + (Number(p.stakeText) === v ? ' on' : '')} onClick={() => p.onStakeText(Number(p.stakeText) === v ? '' : String(v))}>{v}</button>)}
        <input inputMode="decimal" className={(p.stakeBad ? 'bad ' : '') + (p.stakeText.trim() !== '' && !p.stakeBad ? 'on' : '')} placeholder={String(p.defaultStake)}
               value={p.stakeText} onChange={e => p.onStakeText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') (e.target as HTMLInputElement).blur() }} />
      </div>
      <div className="wom" title={wom ? `Weight of money: ${wom.back}% of the money in the best ${p.womLevels} prices is available to back, ${wom.lay}% to lay. ${wom.back >= wom.lay ? '▲ back side heavier' : '▼ lay side heavier'}` : 'No money in the book'}>
        <span className="bets">{nBack} bet{nBack === 1 ? "" : "s"}</span>
        <span className="b">{wom ? wom.back + '%' : '–'}</span>
        <span className="arrow">{wom ? (wom.back >= wom.lay ? '▲' : '▼') : ''}</span>
        <span className="l">{wom ? wom.lay + '%' : '–'}</span>
        <span className="bets">{nLay} bet{nLay === 1 ? "" : "s"}</span>
      </div>
      {blocked && <div className="blockedbar">{rstatus !== 'ACTIVE' ? `Runner ${rstatus.toLowerCase()}` : mstatus === 'SUSPENDED' ? 'SUSPENDED' : mstatus === 'CLOSED' ? 'MARKET CLOSED' : mstatus}</div>}
      <div className="rows" ref={rowsEl} style={{ ["--rh" as string]: rh + "px", ["--rf" as string]: rf + "px" }}>
        {view.rows.map(price => {
          const b = view.back.get(price), l = view.lay.get(price), t = view.traded.get(price) ?? 0
          const here = mine.filter(o => o.price === price)
          const hereB = here.filter(o => o.side === 'BACK'), hereL = here.filter(o => o.side === 'LAY')
          const sum = (os: Order[]) => os.reduce((a, o) => a + o.remaining, 0)
          const fmtSum = (os: Order[]) => '£' + (Math.abs(sum(os) - Math.round(sum(os))) < 0.005 ? sum(os).toFixed(0) : sum(os).toFixed(2))
          const ids = (os: Order[]) => os.map(o => o.order_id).join(',')
          const hg = open ? hedge(pos!, price) : null
          const green = hg && p.pnlBasis === 'market' && p.market.outcomes ? { ...hg, locked: marketAfter(p.market.outcomes, p.selectionId, hg.side, hg.stake, price) } : hg
          const trg = p.triggers.filter(t => t.price === price)
          const isLtp = view.ltp === price
          const backZone = bestBack != null && price <= bestBack, layZone = bestLay != null && price >= bestLay
          const cancel = (e: React.MouseEvent) => { e.stopPropagation(); (here.length || trg.length) && p.onCancelAt(price) }
          return (
            <div key={price} className={'grid lrow' + (isLtp ? ' ltp' : '')}
                 onDragOver={e => { if (e.dataTransfer.types.includes('text/order')) e.preventDefault() }}
                 onDrop={e => { const got = e.dataTransfer.getData('text/order'); const ok = got.split(',').filter(id => id && mine.some(o => o.order_id === id)); if (ok.length) { e.preventDefault(); ok.forEach(id => p.onMoveOrder(id, price)) } }}
                 onContextMenu={e => { e.preventDefault(); p.onContext(price, e.clientX, e.clientY) }}>
              <button className={'cell green ' + (green ? (green.locked >= 0 ? 'gain' : 'loss') : '')} disabled={!green}
                      onClick={() => green && p.onHedge(price)} title={green ? `Hedge here: ${green.side} £${green.stake.toFixed(2)} at ${price.toFixed(2)}, locks ${money(green.locked)} ${p.pnlBasis === 'market' ? 'across the whole market' : 'on this runner'}` : ''}>
                {green ? green.locked.toFixed(2) : ''}</button>
              <div className="cell minecol" onClick={cancel} title={hereB.length ? `${hereB.length} unmatched BACK bet${hereB.length > 1 ? 's' : ''} waiting at ${price.toFixed(2)}, ${fmtSum(hereB)} in all (click to cancel, drag to move)` : ''}>
                {hereB.length > 0 && <span className="chip back draggable sum" draggable onDragStart={e => { e.dataTransfer.setData('text/order', ids(hereB)); e.dataTransfer.effectAllowed = 'move' }}>{fmtSum(hereB)}{hereB.length > 1 && <sup>×{hereB.length}</sup>}</span>}</div>
              <button className={'cell back' + (b ? '' : backZone ? ' zone' : ' none')} onClick={() => p.onClick('BACK', price)} title={`Back at ${price}`}>{b ? fmtSize(b) : ''}</button>
              <div className={'cell price' + (isLtp ? ' last' : '')}>{price.toFixed(2)}</div>
              <button className={'cell lay' + (l ? '' : layZone ? ' zone' : ' none')} onClick={() => p.onClick('LAY', price)} title={`Lay at ${price}`}>{l ? fmtSize(l) : ''}</button>
              <div className="cell minecol" onClick={cancel} title={hereL.length ? `${hereL.length} unmatched LAY bet${hereL.length > 1 ? 's' : ''} waiting at ${price.toFixed(2)}, ${fmtSum(hereL)} in all (click to cancel, drag to move)` : trg.length ? 'Your stop / take-profit here (click to cancel)' : ''}>
                {hereL.length > 0 && <span className="chip lay draggable sum" draggable onDragStart={e => { e.dataTransfer.setData('text/order', ids(hereL)); e.dataTransfer.effectAllowed = 'move' }}>{fmtSum(hereL)}{hereL.length > 1 && <sup>×{hereL.length}</sup>}</span>}
                {trg.map(t => <span key={t.id} className={'chip trig ' + (t.label === 'stop loss' ? 'sl' : 'tp')} title={`${t.label}: greens up when the price reaches ${t.price.toFixed(2)} (click to remove)`}>{t.label === 'stop loss' ? 'SL' : 'TP'}</span>)}</div>
              <div className={'cell recent' + (here.length ? ' waiting' : '')} title={`Matched here: £${(view.rs.get(price) ?? 0).toFixed(0)} in the last ${sel.recent?.short_s ?? 0}s, £${(view.rl.get(price) ?? 0).toFixed(0)} in the last ${Math.round((sel.recent?.long_s ?? 0) / 60)} min${sel.recent && sel.recent.long_span < sel.recent.long_s ? ` (only ${Math.round(sel.recent.long_span)}s of history so far)` : ''}`}>
                <i className="long" style={{ width: `${((view.rl.get(price) ?? 0) / view.maxRecent) * 100}%` }} />
                <i className="short" style={{ width: `${((view.rs.get(price) ?? 0) / view.maxRecent) * 100}%` }} />
                {(view.rs.get(price) ?? 0) > 0 ? <span>{fmtSize(view.rs.get(price)!)}</span> : null}
                {here.length > 0 && <span className="waitbox">{hereL.length > 0 && <b className="sidetag lay">LAY {fmtSum(hereL)}</b>}{hereB.length > 0 && <b className="sidetag back">BACK {fmtSum(hereB)}</b>}<em>waiting</em></span>}
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
      {p.showChart && <div className={'chartwrap' + (chartH < 56 ? ' tiny' : '')} ref={chartEl}><PriceChart marketId={p.marketId} selectionId={p.selectionId} /></div>}
    </div>
  )
}
