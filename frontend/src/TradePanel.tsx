import { useEffect, useState } from 'react'
import { api, type MarketState, type Plan, type PlanResult } from './api'
import { money } from './maths'
import { marketFigure } from './MarketPanel'
import type { Side } from './maths'

const pc = (x: number) => (x > 0.004 ? 'gain' : x < -0.004 ? 'loss' : 'muted')
type Tab = 'dutch' | 'book'
interface Props { marketId: string | null; market: MarketState | undefined; say: (t: string, k?: 'ok' | 'warn' | 'err') => void; refresh: () => void }

/** Dutching (spread one stake over several runners so each returns the same) and Bookmaking (choose the profit you want on every outcome). */
export default function TradePanel({ marketId, market, say, refresh }: Props) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<Tab>('dutch')
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [side, setSide] = useState<Side>('BACK')
  const [total, setTotal] = useState('')
  const [prices, setPrices] = useState<Record<string, string>>({})
  const [targets, setTargets] = useState<Record<string, string>>({})
  const [plan, setPlan] = useState<Plan | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const ids = market ? Object.keys(market.runners) : []

  useEffect(() => { setPicked({}); setPrices({}); setTargets({}); setPlan(null); setErr('') }, [marketId])

  const chosen = ids.filter(i => picked[i])
  const priceBody = Object.fromEntries(chosen.filter(i => Number(prices[i]) > 0).map(i => [i, Number(prices[i])]))
  const totalN = Number(total.replace(/[£,\s]/g, ''))
  const targetsFull = ids.length > 0 && ids.every(i => targets[i] !== undefined && targets[i].trim() !== '' && Number.isFinite(Number(targets[i])))

  // live preview, a moment after the last change
  useEffect(() => {
    if (!open || !marketId) return
    let live = true
    const t = window.setTimeout(() => {
      let p: Promise<Plan> | null = null
      if (tab === 'dutch' && chosen.length >= 2 && totalN >= 1) p = api.dutchPreview({ market_id: marketId, selection_ids: chosen, side, total: totalN, prices: priceBody })
      if (tab === 'book' && targetsFull) p = api.bookPreview({ market_id: marketId, targets: Object.fromEntries(ids.map(i => [i, Number(targets[i])])) })
      if (!p) { setPlan(null); setErr(''); return }
      p.then(r => { if (live) { setPlan(r); setErr(r.error ?? '') } }).catch(e => { if (live) { setPlan(null); setErr(e.message) } })
    }, 400)
    return () => { live = false; window.clearTimeout(t) }
  }, [open, tab, marketId, side, total, JSON.stringify(picked), JSON.stringify(prices), JSON.stringify(targets)]) // eslint-disable-line react-hooks/exhaustive-deps

  const place = async () => {
    if (!marketId || !plan || !plan.bets.length) return
    const lines = plan.bets.map(b => `${b.side} £${b.stake.toFixed(2)} on ${b.runner} @ ${b.price.toFixed(2)}`).join('\n')
    if (!window.confirm(`Place these ${plan.bets.length} bets?\n\n${lines}\n\nTotal stake £${plan.total_stake.toFixed(2)}`)) return
    setBusy(true)
    try {
      const r: PlanResult = tab === 'dutch'
        ? await api.dutch({ market_id: marketId, selection_ids: chosen, side, total: totalN, prices: priceBody })
        : await api.book({ market_id: marketId, targets: Object.fromEntries(ids.map(i => [i, Number(targets[i])])) })
      const waiting = r.placed.filter(p => p.status === 'UNMATCHED' || p.status === 'PARTIAL').length
      say(`${r.placed.length - r.failed} of ${r.placed.length} bets placed${waiting ? `, ${waiting} still waiting to match` : ''}${r.failed ? `, ${r.failed} FAILED: ${r.placed.find(p => p.error)?.error ?? ''}` : ''}`, r.failed ? 'err' : waiting ? 'warn' : 'ok')
    } catch (e) { say((e as Error).message, 'err') }
    setBusy(false); refresh()
  }

  const fig = market ? marketFigure(market) : null
  return (
    <div className={'opanel tradepanel' + (open ? '' : ' shut')}>
      <div className="ohead">
        <button className="icon" onClick={() => setOpen(o => !o)} title={open ? 'Hide' : 'Show'}>{open ? '▾' : '▸'}</button>
        <button className={'chipbtn tiny' + (tab === 'dutch' ? ' on' : '')} onClick={() => { setTab('dutch'); setOpen(true) }}>Dutching</button>
        <button className={'chipbtn tiny' + (tab === 'book' ? ' on' : '')} onClick={() => { setTab('book'); setOpen(true) }}>Bookmaking</button>
        {market && <span className="muted small">{market.event}</span>}
      </div>
      {open && (!market ? <div className="obody"><div className="muted small pad">Open a market first.</div></div> : (
        <div className="obody tradebody">
          {tab === 'dutch' ? (<>
            <div className="trow">
              <span className="muted small">Back or lay all of them:</span>
              {(['BACK', 'LAY'] as const).map(s => <button key={s} className={'chipbtn tiny' + (side === s ? ' on' : '')} onClick={() => setSide(s)}>{s === 'BACK' ? 'Back' : 'Lay'}</button>)}
              <span className="muted small">Total stake £</span><input className="stakein" inputMode="decimal" placeholder="100" value={total} onChange={e => setTotal(e.target.value)} />
            </div>
            <table><thead><tr><th /><th>Runner</th><th>Price (blank = best {side === 'BACK' ? 'back' : 'lay'})</th><th>Stake</th><th>If it wins</th></tr></thead><tbody>
              {ids.map(i => { const b = plan?.bets.find(x => x.selection_id === i); return (
                <tr key={i}><td><input type="checkbox" checked={!!picked[i]} onChange={e => setPicked(o => ({ ...o, [i]: e.target.checked }))} /></td>
                  <td>{market.runners[i]}</td>
                  <td><input className="stakein" inputMode="decimal" value={prices[i] ?? ''} placeholder={b ? b.price.toFixed(2) : ''} disabled={!picked[i]} onChange={e => setPrices(o => ({ ...o, [i]: e.target.value }))} /></td>
                  <td className="num">{b ? `£${b.stake.toFixed(2)}` : ''}</td>
                  <td className={'num ' + pc(plan?.after[i] ?? 0)}>{plan ? money(plan.after[i] ?? 0) : ''}</td></tr>) })}
            </tbody></table>
          </>) : (<>
            <div className="trow">
              <span className="muted small">Profit you want on each outcome. Quick fill:</span>
              <button className="sm" disabled={fig == null} onClick={() => fig != null && setTargets(Object.fromEntries(ids.map(i => [i, fig.toFixed(2)])))} title="Every outcome the same, at the level a green up would lock now">Even (green-up level)</button>
              <button className="sm" onClick={() => setTargets(Object.fromEntries(ids.map(i => [i, (market.outcomes?.[i] ?? 0).toFixed(2)])))}>Current</button>
              <button className="sm" onClick={() => setTargets({})}>Clear</button>
            </div>
            <table><thead><tr><th>Runner</th><th>Now, if it wins</th><th>Target</th><th>Bet to place</th><th>After</th></tr></thead><tbody>
              {ids.map(i => { const b = plan?.bets.find(x => x.selection_id === i); return (
                <tr key={i}><td>{market.runners[i]}</td>
                  <td className={'num ' + pc(market.outcomes?.[i] ?? 0)}>{money(market.outcomes?.[i] ?? 0)}</td>
                  <td><input className="stakein" inputMode="decimal" placeholder="£" value={targets[i] ?? ''} onChange={e => setTargets(o => ({ ...o, [i]: e.target.value }))} /></td>
                  <td className="num small">{b ? <><b className={'sidetag ' + b.side.toLowerCase()}>{b.side}</b> £{b.stake.toFixed(2)} @ {b.price.toFixed(2)}</> : plan ? <span className="muted">none</span> : ''}</td>
                  <td className={'num ' + pc(plan?.after[i] ?? 0)}>{plan ? money(plan.after[i] ?? 0) : ''}</td></tr>) })}
            </tbody></table>
          </>)}
          <div className="trow">
            {err ? <span className="loss small">{err}</span>
              : plan ? <span className="small">{plan.bets.length} bet{plan.bets.length === 1 ? '' : 's'}, £{plan.total_stake.toFixed(2)} in all{plan.dropped.length ? <span className="loss"> · {plan.dropped.length} under £1 left out</span> : null}
                {tab === 'dutch' && plan.book != null ? <span className="muted"> · book {plan.book.toFixed(1)}%</span> : null}</span>
              : <span className="muted small">{tab === 'dutch' ? 'Tick two or more runners and enter a total stake.' : 'Enter a target for every runner.'}</span>}
            <span className="spacer" />
            <button className="primary" disabled={!plan || !plan.bets.length || busy || !!err} onClick={place}>{busy ? 'Placing…' : `Place ${plan?.bets.length ?? ''} bets`}</button>
          </div>
        </div>))}
    </div>
  )
}
