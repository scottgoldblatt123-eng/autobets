import { useCallback, useEffect, useState } from 'react'
import { api, type PlanBet, type PlanRow, type PlanView, type Script } from './api'
import AttachDialog from './AttachDialog'

type Say = (text: string, kind?: 'ok' | 'warn' | 'err') => void
const gbp = (v: number | null | undefined) => (v == null ? '–' : '£' + v.toFixed(2))
const STATE: Record<PlanRow['state'], string> = { armed: 'Armed', running: 'Running', done: 'Done', stopped: 'Stopped', watching: 'Watching' }
type Filter = 'all' | 'you' | 'ai' | 'attention'
type BetTab = 'Unmatched' | 'Partially matched' | 'Matched' | 'Settled'
const TABS: Record<BetTab, string[]> = { Unmatched: ['UNMATCHED'], 'Partially matched': ['PARTIAL'], Matched: ['MATCHED'], Settled: ['CANCELLED', 'LAPSED'] }

/** The Plan: everything planned or running, chosen by you or recommended by the AI, and every bet on it. */
export default function PlanScreen({ say }: { say: Say }) {
  const [view, setView] = useState<PlanView | null>(null), [bets, setBets] = useState<PlanBet[]>([]), [scripts, setScripts] = useState<Script[]>([])
  const [filter, setFilter] = useState<Filter>('all'), [tab, setTab] = useState<BetTab>('Unmatched'), [err, setErr] = useState('')
  const [edit, setEdit] = useState<PlanRow | null>(null), [stake, setStake] = useState(''), [rm, setRm] = useState<PlanRow | null>(null), [pickScript, setPickScript] = useState<{ m: string; sid: string | null; name: string } | null>(null)
  const load = useCallback(() => Promise.all([api.plan(), api.planBets(), api.scripts()]).then(([p, b, s]) => { setView(p); setBets(b); setScripts(s); setErr('') }).catch(e => setErr((e as Error).message)), [])
  useEffect(() => { void load(); const t = window.setInterval(() => void load(), 4000); return () => window.clearInterval(t) }, [load])
  const act = async (f: () => Promise<unknown>, ok: string) => { try { await f(); say(ok); await load() } catch (e) { say((e as Error).message, 'err') } }
  const clash = new Set((view?.clashes ?? []).flatMap(c => c.rows))
  const rows = (view?.rows ?? []).filter(r => filter === 'all' || (filter === 'you' && r.added_by === 'you') || (filter === 'ai' && r.added_by === 'ai') || (filter === 'attention' && (r.state === 'stopped' || clash.has(r.id) || r.note)))
  const sm = view?.summary
  const tabBets = bets.filter(b => TABS[tab].includes(b.status))
  return (
    <div className="screen">
      <div className="row"><h1>Plan</h1><span className="muted">Everything planned or running, chosen by you or recommended by the AI</span></div>
      <div className="muted small">Tick markets in the list on the left (or a whole competition), then Add to Plan. Use ＋ on a match for half time, goal lines, correct score and the rest.</div>
      {err && <div className="loss small">{err}</div>}
      <div className="kpis">
        <div className="card kpi"><span className="cap">Markets in plan</span><b>{sm?.markets ?? 0}</b><small className="muted">{sm?.you ?? 0} yours · {sm?.ai ?? 0} AI</small></div>
        <div className="card kpi"><span className="cap">Total planned investment</span><b>{gbp(sm?.stake)}</b><small className="muted">stakes across live rows</small></div>
        <div className="card kpi"><span className="cap">Max total liability</span><b>{gbp(sm?.max_liability)}</b><small className="muted">if every position loses</small></div>
        <div className={'card kpi' + (sm?.clashes ? ' warnbox' : '')}><span className="cap">Clashes</span><b>{sm?.clashes ?? 0}</b><small className="muted">live scripts sharing a market</small></div>
      </div>
      <div className="row">{([['all', 'All'], ['you', 'You'], ['ai', 'AI'], ['attention', 'Needs attention']] as [Filter, string][]).map(([k, l]) => <button key={k} className={'chip' + (filter === k ? ' on' : '')} onClick={() => setFilter(k)}>{l}</button>)}</div>
      <div className="card tcard"><h3>Planned and running</h3><div className="muted small">Source tags show who chose each row</div>
        <table className="tbl"><thead><tr><th>Market</th><th>Strategy (script name)</th><th>Source</th><th>Stake</th><th>Max liability</th><th>Trigger / window</th><th>State</th><th /></tr></thead>
          <tbody>{rows.map(r => <tr key={r.id} className={clash.has(r.id) ? 'clash' : ''}>
            <td><b>{r.event}</b><div className="muted small">{r.market_name}{r.runner ? ` · ${r.runner}` : ''}</div></td>
            <td>{r.strategy}{r.script_id && !r.script_enabled && <div className="muted small">script is off</div>}</td>
            <td><span className={'src' + (r.added_by === 'ai' ? ' ai' : '')}>{r.added_by === 'ai' ? 'AI' : 'You'}</span></td>
            <td>{gbp(r.stake)}</td><td>{gbp(r.max_liability)}</td><td className="small">{r.trigger || '–'}</td>
            <td><span className={'state ' + r.state}>{STATE[r.state]}</span>{r.note && <div className="loss small">{r.note}</div>}{clash.has(r.id) && <div className="warn small">Clash: another live script on this market</div>}</td>
            <td className="nowrap"><button className="sm" onClick={() => { setEdit(r); setStake(r.stake == null ? '' : String(r.stake)) }}>Edit</button> <button className="sm" onClick={() => setRm(r)}>Remove</button></td></tr>)}
            {!rows.length && <tr><td colSpan={8} className="muted pad">{view?.rows.length ? 'Nothing matches this filter.' : 'The Plan is empty. Add a market and attach a script, or add one from Scripts.'}</td></tr>}</tbody></table>
        <div className="muted small">Pay-off is not shown: it depends on where each trade exits, which a script decides as the match unfolds.</div></div>
      <div className="card tcard"><h3>Bets</h3><div className="muted small">All bets from you, scripts and the AI</div>
        <div className="row">{(Object.keys(TABS) as BetTab[]).map(t => <button key={t} className={'tab' + (tab === t ? ' on' : '')} onClick={() => setTab(t)}>{t} ({bets.filter(b => TABS[t].includes(b.status)).length})</button>)}</div>
        <table className="tbl"><thead><tr><th>Market / selection</th><th>Strategy</th><th>Side</th><th>Price</th><th>Status</th><th>Matched</th><th>Placed by</th><th /></tr></thead>
          <tbody>{tabBets.map(b => <tr key={b.order_id}><td><b>{b.event}</b><div className="muted small">{b.market} · {b.runner}</div></td><td>{b.strategy}</td><td><span className={'chip ' + b.side.toLowerCase()}>{b.side}</span></td><td>{b.price.toFixed(2)}</td><td>{b.status.toLowerCase()}</td>
            <td className="small">£{b.matched.toFixed(2)} of £{b.size.toFixed(2)}{b.remaining > 0 && b.status !== 'CANCELLED' ? ` · £${b.remaining.toFixed(2)} waiting` : ''}</td><td>{b.placed_by}</td>
            <td>{(b.status === 'UNMATCHED' || b.status === 'PARTIAL') && <button className="sm" onClick={() => act(() => api.cancel(b.order_id), 'Cancelled.')}>Cancel</button>}</td></tr>)}
            {!tabBets.length && <tr><td colSpan={8} className="muted pad">No {tab.toLowerCase()} bets.</td></tr>}</tbody></table></div>
      {pickScript && <AttachDialog marketId={pickScript.m} title={pickScript.name} onClose={() => setPickScript(null)} onDone={(m, k) => { say(m, k); void load() }} />}
      {edit && <div className="overlay" onClick={() => setEdit(null)}><div className="card" role="dialog" aria-label="Edit plan row" onClick={e => e.stopPropagation()} style={{ width: 420 }}>
        <h3>Edit before applying</h3><div className="muted small">{edit.event} · {edit.market_name} · {edit.strategy}</div>
        <label>Stake (£), blank = the script's own<input inputMode="decimal" value={stake} onChange={e => setStake(e.target.value)} /></label>
        <label>Strategy<select defaultValue={edit.script_id ?? ''} onChange={e => e.target.value && act(() => api.planEdit(edit.id, { script_id: e.target.value }), 'Script changed.')}><option value="">{edit.script_id ? '(keep)' : 'None'}</option>{scripts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={() => setEdit(null)}>Cancel</button><button className="primary" onClick={() => { const v = Number(stake); if (stake.trim() && !(v >= 1)) { say('Stake must be at least £1.', 'err'); return } void act(() => api.planEdit(edit.id, stake.trim() ? { stake: v } : {}), 'Changes saved.').then(() => setEdit(null)) }}>Save changes</button></div></div></div>}
      {rm && <div className="overlay" onClick={() => setRm(null)}><div className="card" role="dialog" aria-label="Remove from plan" onClick={e => e.stopPropagation()} style={{ width: 420 }}>
        <h3>Remove?</h3><div className="small">{rm.event} · {rm.market_name} · {rm.strategy}</div><div className="muted small">Cancels this script's unmatched orders on the market. Matched bets and open positions stay as they are.</div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={() => setRm(null)}>Keep</button><button className="stopbtn" onClick={() => act(() => api.planRemove(rm.id), 'Removed.').then(() => setRm(null))}>Remove</button></div></div></div>}
    </div>
  )
}
