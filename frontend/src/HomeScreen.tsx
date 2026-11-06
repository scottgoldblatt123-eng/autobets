import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

type Say = (text: string, kind?: 'ok' | 'warn' | 'err') => void
interface HomeData {
  today: number; exposure: number; automation: boolean
  kpis: { month: number; roi: number | null; last7: number; win_rate: number | null; markets: number; clv: number | null; scripts_running: number; recs_pending: number }
  overview: { market_id: string; event: string; market: string; strategy: string; rules: string; by: string; state: string; pnl: number | null; exposure: number | null; matched: number; start: string | null }[]
  open_orders: { order_id: string; side: 'BACK' | 'LAY'; price: number; size: number; matched: number; remaining: number; status: string; event: string; runner: string; source: string }[]
  recs: { id: string; kind?: string; title: string; edge: number; stake: number; confidence: string; model_p: number; market_p: number; side: string; price: number }[]
  alerts: { id: string; t: number; type: string; text: string }[]
}
const money = (v: number | null | undefined, plus = true) => (v == null ? '–' : (v < 0 ? '-' : plus && v > 0 ? '+' : '') + '£' + Math.abs(v).toFixed(2))
const cls = (v: number | null | undefined) => (v == null || v === 0 ? '' : v > 0 ? 'gain' : 'loss')

/** Home: how things stand at a glance. Ladders and the order ticket live in Manual. */
export default function HomeScreen({ say, go, openMarket }: { say: Say; go: (s: 'recs' | 'alerts' | 'plan' | 'scripts' | 'manual') => void; openMarket: (marketId: string, view?: 'ladder' | 'grid') => void }) {
  const [d, setD] = useState<HomeData | null>(null), [err, setErr] = useState(''), [busy, setBusy] = useState(''), [sure, setSure] = useState(false)
  const load = useCallback(() => api.home().then(x => { setD(x as unknown as HomeData); setErr('') }).catch(e => setErr((e as Error).message)), [])
  useEffect(() => { void load(); const t = window.setInterval(() => void load(), 5000); return () => window.clearInterval(t) }, [load])
  const k = d?.kpis
  const apply = async (ids: string[]) => {
    setBusy(ids.length === 1 ? ids[0] : 'all'); setSure(false)
    let ok = 0; const bad: string[] = []
    for (const id of ids) { try { await api.recApply(id); ok++ } catch (e) { bad.push((e as Error).message) } }
    setBusy(''); void load()
    if (ok) say(ok === 1 ? 'Applied: added to your Plan.' : `Applied ${ok} ideas: added to your Plan.`)
    if (bad.length) say(`${bad.length} could not be applied: ${bad[0]}`, 'warn')
  }
  const tile = (label: string, value: string, sub: string, c = '') => <div className="card kpi" key={label}><span className="cap">{label}</span><b className={c}>{value}</b><small className="muted">{sub}</small></div>
  return (
    <div className="screen">
      <div className="row"><h1>Home</h1><span className="muted">How things stand right now</span></div>
      {err && <div className="loss small">{err}</div>}
      <div className="kpis kpis7">
        {tile('Month P&L', money(k?.month), `${k?.markets ?? 0} settled markets`, cls(k?.month))}
        {tile('ROI', k?.roi == null ? '–' : `${k.roi > 0 ? '+' : ''}${k.roi}%`, 'on money at risk', cls(k?.roi))}
        {tile('7-day P&L', money(k?.last7), 'settled', cls(k?.last7))}
        {tile('Win rate', k?.win_rate == null ? '–' : `${k.win_rate}%`, 'of settled markets')}
        {tile('Avg CLV', k?.clv == null ? '–' : `${k.clv > 0 ? '+' : ''}${k.clv} pts`, 'on AI ideas')}
        {tile('Scripts running', String(k?.scripts_running ?? 0), 'on the Plan, switched on')}
        {tile('Recs pending', String(k?.recs_pending ?? 0), 'waiting for you')}
      </div>
      <div className="card tcard"><div className="row"><h3>Market overview</h3><span className="muted small">Markets in your Plan and any you hold a position in</span><span className="spacer" /><button className="sm" onClick={() => go('plan')}>Open Plan</button></div>
        <table className="tbl"><thead><tr><th>Market</th><th>Script / rules</th><th>Nominated by</th><th>State</th><th>P&amp;L now</th><th>At risk</th><th>Matched</th><th /></tr></thead>
          <tbody>{d?.overview.map((o, i) => <tr key={o.market_id + i}><td><b>{o.event}</b><div className="muted small">{o.market}</div></td><td>{o.strategy}<div className="muted small">{o.rules || ''}</div></td>
            <td><span className={'src' + (o.by === 'ai' ? ' ai' : '')}>{o.by === 'ai' ? 'AI' : 'You'}</span></td><td>{o.state}</td><td className={cls(o.pnl)}>{money(o.pnl)}</td><td>{o.exposure == null ? '–' : '£' + o.exposure.toFixed(2)}</td><td>£{o.matched.toFixed(2)}</td>
            <td style={{ whiteSpace: 'nowrap' }}><button className="sm" onClick={() => openMarket(o.market_id, 'grid')}>Grid</button> <button className="sm" onClick={() => openMarket(o.market_id)}>Ladder</button></td></tr>)}
            {!d?.overview.length && <tr><td colSpan={8} className="muted pad">Nothing planned and no open positions. Add a market to the Plan, or open one in Manual.</td></tr>}</tbody></table></div>
      <div className="homecols">
        <div className="card tcard"><div className="row"><h3>Open orders</h3><span className="spacer" /></div>
          <table className="tbl"><thead><tr><th>Market</th><th>Side</th><th>Price</th><th>Waiting</th><th>By</th><th /></tr></thead>
            <tbody>{d?.open_orders.map(o => <tr key={o.order_id}><td><b>{o.event}</b><div className="muted small">{o.runner}</div></td><td><span className={'chip ' + o.side.toLowerCase()}>{o.side}</span></td><td>{o.price.toFixed(2)}</td><td>£{o.remaining.toFixed(2)}</td><td>{o.source === 'manual' ? 'You' : o.source === 'ai' ? 'AI' : 'Script'}</td>
              <td><button className="sm" onClick={() => api.cancel(o.order_id).then(() => { say('Cancelled.'); void load() }).catch(e => say((e as Error).message, 'err'))}>Cancel</button></td></tr>)}
              {!d?.open_orders.length && <tr><td colSpan={6} className="muted pad">No unmatched orders.</td></tr>}</tbody></table></div>
        <div className="card tcard"><div className="row"><h3>AI recommended trades</h3><span className="spacer" />
          {!!d?.recs.length && (sure
            ? <><span className="small muted">Add {d.recs.length} to the Plan?</span><button className="sm primary" disabled={!!busy} onClick={() => void apply(d.recs.map(r => r.id))}>Yes, apply all</button><button className="sm" onClick={() => setSure(false)}>No</button></>
            : <button className="sm primary" disabled={!!busy} onClick={() => setSure(true)}>Apply all ({d.recs.length})</button>)}
          <button className="sm" onClick={() => go('recs')}>See all</button></div>
          <table className="tbl"><thead><tr><th>Idea</th><th>Model</th><th>Market</th><th>Edge</th><th /></tr></thead>
            <tbody>{d?.recs.map(r => <tr key={r.id}><td>{r.title}</td><td>{(r.model_p * 100).toFixed(1)}%</td><td>{(r.market_p * 100).toFixed(1)}%</td><td className="gain">+{(r.edge * 100).toFixed(1)}%</td><td><button className="sm" onClick={() => go('recs')}>Review</button> <button className="sm primary" disabled={!!busy} onClick={() => void apply([r.id])}>{busy === r.id ? '…' : 'Apply'}</button></td></tr>)}
              {!d?.recs.length && <tr><td colSpan={5} className="muted pad">No ideas right now.</td></tr>}</tbody></table></div>
      </div>
      <div className="card tcard"><div className="row"><h3>Recent alerts</h3><span className="spacer" /><button className="sm" onClick={() => go('alerts')}>Open Alerts</button></div>
        {d?.alerts.map(a => <div key={a.id} className="small" style={{ padding: '4px 0', borderTop: '1px solid var(--border)' }}><span className="muted">{new Date(a.t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span> · {a.text}</div>)}
        {!d?.alerts.length && <div className="muted small">Nothing yet.</div>}</div>
    </div>
  )
}
