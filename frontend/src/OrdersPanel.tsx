import { useState } from 'react'
import type { MarketState, Order } from './api'
import { move } from './ticks'

interface Props {
  orders: Order[]
  markets: Record<string, MarketState>
  onEdit: (id: string, b: { price?: number; size?: number }) => void
  onCancel: (id: string) => void
  onCancelAll: () => void
  onPersistAll: (p: 'KEEP' | 'CANCEL' | 'TAKE_SP') => void
  onPersist: (id: string, p: 'KEEP' | 'CANCEL' | 'TAKE_SP') => void
}

const hhmmss = (t: number) => new Date(t * 1000).toLocaleTimeString('en-GB')

/** Unmatched bets, as in Bet Angel's bottom panel: every open bet in the open markets, with price and stake editable in place. */
export default function OrdersPanel(p: Props) {
  const [open, setOpen] = useState(true)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const unmatched = p.orders.filter(o => o.remaining > 0.004)
  const commitSize = (o: Order) => {
    const t = draft[o.order_id]
    if (t == null) return
    setDraft(d => { const n = { ...d }; delete n[o.order_id]; return n })
    const v = Number(t.replace(/[£,\s]/g, ''))
    if (Number.isFinite(v) && Math.abs(v - o.remaining) > 0.004) p.onEdit(o.order_id, { size: Math.round(v * 100) / 100 })
  }
  return (
    <div className={'opanel' + (open ? '' : ' shut')}>
      <div className="ohead">
        <button className="icon" onClick={() => setOpen(o => !o)} title={open ? 'Hide' : 'Show'}>{open ? '▾' : '▸'}</button>
        <b>Unmatched bets</b><span className="muted"> ({unmatched.length})</span>
        <span className="spacer" />
        <span className="muted small">At the off, all:</span>
        <button className="sm" disabled={!unmatched.length} onClick={() => p.onPersistAll('KEEP')} title="Unmatched bets stay on when the match starts">Keep</button>
        <button className="sm" disabled={!unmatched.length} onClick={() => p.onPersistAll('CANCEL')} title="Unmatched bets are cancelled when the match starts">Cancel</button>
        <button className="sm" disabled={!unmatched.length} onClick={() => p.onPersistAll('TAKE_SP')} title="Unmatched bets turn into Starting Price bets (not simulated in practice mode: they are removed)">Take SP</button>
        <button className="sm" disabled={!unmatched.length} onClick={p.onCancelAll}>Cancel all</button>
      </div>
      {open && (
        <div className="obody">
          {!unmatched.length ? <div className="muted small pad">No unmatched bets.</div> : (
            <table>
              <thead><tr><th>Type</th><th>Runner</th><th>Placed</th><th>Odds</th><th>Stake</th><th>Matched</th><th>At the off</th><th /></tr></thead>
              <tbody>
                {unmatched.map(o => {
                  const m = p.markets[o.market_id]
                  return (
                    <tr key={o.order_id}>
                      <td><span className={'chip ' + o.side.toLowerCase()}>{o.side}</span></td>
                      <td>{m?.runners[o.selection_id] ?? o.selection_id}<span className="muted small"> · {m?.event}</span></td>
                      <td className="muted">{hhmmss(o.placed_at)}</td>
                      <td className="num">
                        <button className="sm tick" onClick={() => p.onEdit(o.order_id, { price: move(o.price, -1) })} title="One tick lower">−</button>
                        <b>{o.price.toFixed(2)}</b>
                        <button className="sm tick" onClick={() => p.onEdit(o.order_id, { price: move(o.price, 1) })} title="One tick higher">+</button>
                      </td>
                      <td className="num"><input className="stakein" inputMode="decimal" value={draft[o.order_id] ?? o.remaining.toFixed(2)}
                        onChange={e => setDraft(d => ({ ...d, [o.order_id]: e.target.value }))} onBlur={() => commitSize(o)}
                        onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setDraft(d => { const n = { ...d }; delete n[o.order_id]; return n }) }} /></td>
                      <td className="num muted">{o.matched > 0 ? '£' + o.matched.toFixed(2) : '–'}</td>
                      <td><select value={o.persistence} onChange={e => p.onPersist(o.order_id, e.target.value as 'KEEP' | 'CANCEL' | 'TAKE_SP')}>
                        <option value="CANCEL">Cancel</option><option value="KEEP">Keep</option><option value="TAKE_SP">Take SP</option></select></td>
                      <td><button className="sm" onClick={() => p.onCancel(o.order_id)}>Cancel</button></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
