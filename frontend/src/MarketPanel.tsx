import { useEffect, useState } from 'react'
import type { MarketState, MarketTrigger } from './api'
import { money } from './maths'

interface Props {
  marketId: string
  market: MarketState
  openOrders: number
  triggers: MarketTrigger[]
  onGreen: (hard: boolean, pct: number) => void
  onAuto: (level: number) => void
  onDelAuto: (id: string) => void
  onClose: () => void
}

function countdown(start: string | null, inPlay: boolean, now: number): string {
  if (inPlay) return 'In play'
  if (!start) return ''
  const s = Math.round((new Date(start).getTime() - now) / 1000)
  if (s <= 0) return 'Due off'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`
}

/** The single figure for a market: what the hard-close button would lock at today's prices, or if there is nothing left to hedge,
 *  the guaranteed (worst) result of the position. null when there is no position. */
export function marketFigure(market: MarketState): number | null {
  const g = market.green, o = market.outcomes
  if (g && g.bets.length > 0) return g.locked
  if (o) { const v = Object.values(o); return v.length ? Math.min(...v) : null }
  return null
}

/** Everything about one market in one block header, laid out like Geeks Toy's market panel:
 *  clock above, then back book % | ONE hedge button (green if the market is in profit, red if in loss) | lay book %.
 *  The button is a hard close: it cancels every unmatched order in the market, then places the bets that level all results. */
export default function MarketHeader({ market, openOrders, triggers, onGreen, onAuto, onDelAuto, onClose }: Props) {
  const [now, setNow] = useState(Date.now())
  const [menu, setMenu] = useState(false)
  const [level, setLevel] = useState('')
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t) }, [])
  const sels = Object.values(market.selections)
  const matched = Math.round(sels.reduce((a, s) => a + s.traded.reduce((x, y) => x + y[1], 0), 0))
  const noVolume = sels.length > 0 && sels.every(s => s.traded.length === 0)
  const book = (pick: (s: (typeof sels)[number]) => number | undefined) => {
    const v = sels.map(pick)
    return v.length && v.every(x => !!x) ? (v as number[]).reduce((a, x) => a + 100 / x, 0).toFixed(1) + '%' : '–'
  }
  const o = market.outcomes
  const g = market.green
  const hasPos = !!o
  const canGreen = !!g && g.bets.length > 0
  const figure = marketFigure(market)
  // Green for a profit (exactly £0.00 too), red for a loss. The figure stays on show even when the position is level.
  const state = figure == null ? 'idle' : Math.round(figure * 100) >= 0 ? 'gain' : 'loss'
  const label = figure == null ? '£0.00' : money(figure).replace('+', '')
  const sub = canGreen ? (g!.level ? 'Hard close' : 'Hard close ~') : openOrders ? `Cancel ${openOrders}` : hasPos ? 'Level' : 'no position'
  const enabled = canGreen || openOrders > 0
  const tip = canGreen
    ? `Hard close: cancels every unmatched order in this market, then places the bets that level all results at today's prices. Locks ${money(g!.locked)} (G).`
    : openOrders ? 'Cancels the unmatched orders in this market. Your position is level, or too small to hedge (£1 minimum stake), so this figure is what you are guaranteed.'
    : hasPos ? `Level (or too small to hedge: £1 minimum stake). This is your guaranteed result: ${money(figure ?? 0)}.` : 'No position in this market.'
  return (
    <div className="mhead">
      <div className="mctl">
        <span className={'clock' + (market.in_play ? ' live' : '')}>{countdown(market.start, market.in_play, now) || '—'}</span>
        {market.status && market.status !== 'OPEN' && <span className="statustag">{market.status === 'SUSPENDED' ? 'SUSPENDED' : market.status === 'CLOSED' ? 'CLOSED' : market.status}</span>}
        <div className="mbtnrow">
          <span className="book" title="Back book: add up 1/price of the best back prices. Over 100% is normal."><i>Back</i>{book(s => s.backs[0]?.[0])}</span>
          <button className={'bigbtn ' + state} disabled={!enabled} onClick={() => onGreen(true, 1)} onContextMenu={e => { e.preventDefault(); setMenu(true) }} title={tip + ' Right-click or use ▾ for more options.'}>
            <b>{label}</b><small>{sub}</small>
          </button>
          <button className="caret" onClick={() => setMenu(v => !v)} title="More ways to green up">▾</button>
          <span className="book" title="Lay book: add up 1/price of the best lay prices. Under 100% is normal."><i>Lay</i>{book(s => s.lays[0]?.[0])}</span>
        </div>
      </div>
      {menu && (
        <div className="overlay clear" onClick={() => setMenu(false)} onContextMenu={e => { e.preventDefault(); setMenu(false) }}>
          <div className="menu gmenu" onClick={e => e.stopPropagation()}>
            <button disabled={!canGreen && !openOrders} onClick={() => { setMenu(false); onGreen(true, 1) }}>Hard close: cancel unmatched bets, then green up <small className="muted">(G)</small></button>
            <button disabled={!canGreen} onClick={() => { setMenu(false); onGreen(false, 1) }}>Green up, keep my unmatched bets</button>
            <div className="muted small">Partial hedge (keeps unmatched bets)</div>
            <div className="row">{[0.75, 0.5, 0.25].map(p => <button key={p} disabled={!canGreen} onClick={() => { setMenu(false); onGreen(false, p) }}>{p * 100}%</button>)}</div>
            <div className="muted small">Auto hard-close when the market profit reaches £{figure != null ? ` (now ${money(figure)})` : ''}</div>
            <div className="row"><input inputMode="decimal" placeholder="e.g. 5 or -10" value={level} onChange={e => setLevel(e.target.value)} />
              <button disabled={!hasPos || !Number.isFinite(Number(level)) || level.trim() === ''} onClick={() => { onAuto(Number(level)); setLevel(''); setMenu(false) }}>Set</button></div>
          </div>
        </div>
      )}
      <div className="minfo">
        <div className="mtitle"><b>{market.event}</b><span className="muted"> · {market.name}</span></div>
        <div className="muted small" title={noVolume ? 'Betfair is not sending matched volumes for this market (a delayed key may withhold them)' : ''}>Matched <b>{noVolume ? 'n/a' : '£' + matched.toLocaleString('en-GB')}</b></div>
        {triggers.length > 0 && <div className="small">{triggers.map(t => (
          <span key={t.id} className={'chip trig ' + (t.label === 'stop loss' ? 'sl' : 'tp')} style={{ marginRight: 6 }} title="Hard-closes the market when the profit you could lock reaches this (click to remove)" onClick={() => onDelAuto(t.id)}>
            Auto-green at {money(t.level)} ✕</span>))}</div>}
        {o && (
          <div className="outcomes">
            {Object.entries(o).map(([sid, v]) => (
              <div key={sid} className={'outcome ' + (v >= 0 ? 'gain-box' : 'loss-box')} title={`If ${market.runners[sid] ?? sid} wins`}>
                <small>{market.runners[sid] ?? sid} wins</small><b>{money(v)}</b>
              </div>
            ))}
          </div>
        )}
      </div>
      <button className="icon" title="Close this market (all of its ladders)" onClick={onClose}>✕</button>
    </div>
  )
}
