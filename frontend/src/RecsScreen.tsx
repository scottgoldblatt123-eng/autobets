import { useCallback, useEffect, useState } from 'react'
import { api, type ScanInfo, type Rec, type RecStats } from './api'
import { RuleCards } from './ScriptsScreen'

type Say = (text: string, kind?: 'ok' | 'warn' | 'err') => void
type Kind = 'all' | 'setup' | 'script' | 'model'

/** Recommendations: trade setups the models surface, each with a ready-made script. Nothing is bet until you add it to the Plan, and then only in play when its conditions are met. */
export default function RecsScreen({ say, onDiscuss, onPlan }: { say: Say; onDiscuss: (r: Rec) => void; onPlan: () => void }) {
  const [items, setItems] = useState<Rec[]>([]), [stats, setStats] = useState<RecStats | null>(null), [scan, setScan] = useState<ScanInfo | null>(null), [scanning, setScanning] = useState(false), [kind, setKind] = useState<Kind>('all'), [sport, setSport] = useState<'all' | 'football' | 'tennis'>('all'), [err, setErr] = useState(''), [proposing, setProposing] = useState(false)
  const [apply, setApply] = useState<Rec | null>(null), [price, setPrice] = useState(''), [stake, setStake] = useState(''), [dismiss, setDismiss] = useState<Rec | null>(null), [reason, setReason] = useState(''), [busy, setBusy] = useState(false)
  const load = useCallback(() => api.recs('all').then(r => { setItems(r.items); setStats(r.stats); setScan(r.scan); setErr('') }).catch(e => setErr((e as Error).message)), [])
  useEffect(() => { void load(); const t = window.setInterval(() => void load(), 15000); return () => window.clearInterval(t) }, [load])
  const inSport = (r: Rec) => sport === 'all' || r.sport === sport || (r.kind === 'script' && r.sport === 'any')
  const shown = items.filter(r => (kind === 'all' || r.kind === kind) && inSport(r))
  const nSport = (sp: string) => items.filter(r => r.status === 'pending' && (sp === 'all' || r.sport === sp || (r.kind === 'script' && r.sport === 'any'))).length
  const propose = async () => { setProposing(true); try { const r = await api.proposeScripts(); say(r.created ? `${r.created} new script proposal${r.created === 1 ? '' : 's'} (cost about £${r.cost_gbp.toFixed(2)}).` : 'Claude had no new script ideas that differ from what you already have.'); void load() } catch (e) { say((e as Error).message, 'err') } finally { setProposing(false) } }
  const open = (r: Rec, edit: boolean) => { setApply(r); setStake(String(r.stake)); setPrice(edit ? String(r.price) : '') }
  const confirm = async () => {
    if (!apply) return
    const st = Number(stake)
    if (!(st >= 1)) { say('Stake must be at least £1.', 'err'); return }
    setBusy(true)
    try { const r = await api.recApply(apply.id, { stake: st, ...(price.trim() ? { price: Number(price) } : {}) }); if (!r.order) { say(`Added to the Plan with script '${r.script?.name ?? ''}'. It bets in play when its conditions are met.`); setApply(null); void load(); return } say(`Placed (practice mode): ${r.order.side} £${r.order.size.toFixed(2)} at ${r.order.price.toFixed(2)}. See it on the Plan.`, r.warnings.length ? 'warn' : 'ok'); setApply(null); await load() }
    catch (e) { say((e as Error).message, 'err') } finally { setBusy(false) }
  }
  const c = stats?.counts
  return (
    <div className="screen">
      <div className="row"><h1>Recommendations</h1><span className="spacer" /><button onClick={() => api.recScan().then(r => { say(r.created ? `${r.created} new idea${r.created === 1 ? '' : 's'}.` : 'Scanned: nothing new right now.'); void load() }).catch(e => say((e as Error).message, 'err'))} title="Look for ideas now (it also runs every couple of minutes)">Scan now</button></div>
      {err && <div className="loss small">{err}</div>}
      <div className="kpis">
        <div className="card kpi"><span className="cap">Pending</span><b>{stats?.pending ?? 0}</b><small className="muted">ideas waiting for you</small></div>
        <div className="card kpi"><span className="cap">Applied (30 days)</span><b>{stats?.applied ?? 0}</b><small className="muted">{stats?.acceptance == null ? 'none decided yet' : `${stats.acceptance}% acceptance`}</small></div>
        <div className="card kpi"><span className="cap">Avg edge of applied</span><b>{stats?.avg_edge_applied == null ? '–' : `+${stats.avg_edge_applied}%`}</b><small className="muted">vs model p</small></div>
        <div className="card kpi"><span className="cap">Evidence so far</span><b>{stats?.avg_clv_pts == null ? '–' : `${stats.avg_clv_pts > 0 ? '+' : ''}${stats.avg_clv_pts} pts`}</b><small className="muted">avg CLV over {stats?.evidence ?? 0} measured ideas</small></div>
        <div className="card kpi"><span className="cap">Auto-apply</span><b>{stats?.auto_apply_unlocked ? 'Available' : 'Locked'}</b><small className="muted">{stats?.evidence ?? 0} / {stats?.evidence_needed ?? 300} evidence needed</small></div>
      </div>
      <ScanReport scan={scan} busy={scanning} run={async () => { setScanning(true); try { await api.recScan(); await load() } catch (e) { setErr((e as Error).message) } finally { setScanning(false) } }} />
      {!!stats?.setup_results?.n && <div className="small muted">Accepted setups that have settled: {stats.setup_results.n}, net <b className={stats.setup_results.net >= 0 ? 'gain' : 'loss'}>{stats.setup_results.net >= 0 ? '+' : ''}£{stats.setup_results.net.toFixed(2)}</b> (whole-market result, practice mode)</div>}
      <div className="row" role="group" aria-label="Sport">
        {([['all', 'All sports'], ['football', 'Football'], ['tennis', 'Tennis']] as ['all' | 'football' | 'tennis', string][]).map(([k, l]) => <button key={k} className={'chip' + (sport === k ? ' on' : '')} onClick={() => setSport(k)}>{l} ({nSport(k)})</button>)}
        <span className="spacer" /><button onClick={propose} disabled={proposing} title="Ask Claude for new scripts that differ from your library (about 3p to 10p each time)">{proposing ? 'Thinking…' : 'Propose new scripts'}</button>
      </div>
      <div className="row">
        {([['all', `All (${c?.all ?? 0})`], ['setup', `Trade setups (${c?.setups ?? 0})`], ['script', `New scripts (${items.filter(r => r.kind === 'script' && r.status === 'pending').length})`], ['model', `Model improvements (${c?.models ?? 0})`]] as [Kind, string][]).map(([k, l]) => <button key={k} className={'chip' + (kind === k ? ' on' : '')} onClick={() => setKind(k)}>{l}</button>)}
        <span className="spacer" /><label className="sw"><input type="checkbox" disabled /> Auto-apply recommendations</label><span className="muted small">Unlocks after {stats?.evidence_needed ?? 300} recommendations with positive CLV</span>
      </div>
      {shown.map(r => r.kind === 'script' && r.proposal ? (
        <div key={r.id} className="card reccard">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="row" style={{ gap: 8 }}><span className="src ai">New script proposal</span><h3>{r.title}</h3><span className="muted small">{r.sport === 'any' ? 'Any sport' : r.sport}</span></div>
            <p className="small muted" style={{ margin: '6px 0 8px', lineHeight: 1.5 }}>{r.reason}</p>
            {!!r.text?.length && <RuleCards text={r.text} fold headline={r.headline} />}
          </div>
          <div className="reccta"><button className="primary" onClick={async () => { try { const x = await api.recApply(r.id); say(`Saved '${x.script?.name ?? ''}' to Scripts (switched off). Put it to work from there when you are ready.`); void load() } catch (e) { say((e as Error).message, 'err') } }}>Save to Scripts</button>
            <button onClick={() => onDiscuss(r)}>Discuss with Claude</button><button onClick={() => { setDismiss(r); setReason('') }}>Dismiss</button></div>
        </div>) : r.kind === 'setup' ? (
        <div key={r.id} className="card reccard">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="row" style={{ gap: 8 }}><span className="src ai">Trade setup</span><h3>{r.title}{r.start ? ` · ${new Date(r.start).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })}` : ''}</h3></div>
            <p className="small muted" style={{ margin: '6px 0 8px', lineHeight: 1.5 }}>{r.reason}</p>
            {!!r.watch?.length && <div className="small" style={{ marginBottom: 8 }}><b>What has to happen</b><ul style={{ margin: '4px 0 0 18px', padding: 0 }}>{r.watch.map(w => <li key={w}>{w}</li>)}</ul></div>}
            {!!r.text?.length && <div style={{ marginBottom: 8 }}><RuleCards text={r.text} fold headline={r.headline} /></div>}
            <div className="row small" style={{ gap: 20 }}><span>Model <b>{(r.model_p * 100).toFixed(0)}%</b> · market <b>{(r.market_p * 100).toFixed(0)}%</b></span><span>{r.side === 'BACK' ? 'Back' : 'Lay'} {r.runner} (now {r.price.toFixed(2)})</span><span>Stake £{r.stake}</span><span>{r.side === 'LAY' ? 'Liability' : 'Worst case'} £{r.max_loss}</span></div>
          </div>
          <div className="reccta"><button className="primary" onClick={() => open(r, false)}>Add to Plan</button><button onClick={() => onDiscuss(r)}>Discuss with Claude</button><button onClick={() => { setDismiss(r); setReason('') }}>Dismiss</button></div>
        </div>) : (
        <div key={r.id} className="card reccard">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="row" style={{ gap: 8 }}><span className="src ai">{r.kind === 'trade' ? 'Trade' : r.kind === 'script' ? 'Script' : 'Model improvement'}</span><h3>{r.title}{r.start ? ` · ${new Date(r.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}</h3></div>
            <p className="small muted" style={{ margin: '6px 0 8px', lineHeight: 1.5 }}>{r.reason}</p>
            <div className="row small" style={{ gap: 20 }}><span>Edge <b className="gain">+{(r.edge * 100).toFixed(1)}%</b></span><span>{r.side === 'BACK' ? 'Back' : 'Lay'} at <b>{r.price.toFixed(2)}</b></span><span>Stake £{r.stake}</span><span>{r.side === 'LAY' ? 'Liability' : 'Max loss'} £{r.max_loss.toFixed(2)}</span><span>Confidence {r.confidence}</span></div>
          </div>
          <div className="reccta"><button className="primary" onClick={() => open(r, false)}>Apply</button><button onClick={() => open(r, true)}>Edit</button><button onClick={() => onDiscuss(r)}>Discuss with Claude</button><button onClick={() => { setDismiss(r); setReason('') }}>Dismiss</button></div>
        </div>))}
      {!shown.length && <div className="card muted small">{kind === 'script' || kind === 'model' ? kind === 'script' ? 'None yet. Press Propose new scripts and Claude will suggest scripts that differ from your library; it also does this about once a day.' : 'None yet. Model recommendations need backtest results, which arrive with the Analyse screens.' : 'No setups right now. Every couple of minutes AutoBets checks pre-match tennis and football markets starting in the next 8 hours and suggests a trade setup (a plan for how to trade the game, with a ready-made script) only when the model and the market see the game differently. Quiet spells are normal.'}</div>}
      {apply && <div className="overlay" onClick={() => setApply(null)}><div className="card" role="dialog" aria-label="Apply recommendation" onClick={e => e.stopPropagation()} style={{ width: 440 }}>
        <h3>{apply.kind === 'setup' ? 'Add to Plan' : price ? 'Edit before applying' : 'Apply recommendation'}</h3><div className="small">{apply.title}</div>
        <label>Stake (£)<input inputMode="decimal" value={stake} onChange={e => setStake(e.target.value)} /></label>
        {apply.kind !== 'setup' && <label>Price (blank = the best price right now, checked again when you confirm)<input inputMode="decimal" value={price} placeholder={apply.price.toFixed(2)} onChange={e => setPrice(e.target.value)} /></label>}
        <div className="muted small">{apply.kind === 'setup' ? 'Saves the script to your library (switched on) and adds this market to the Plan. Nothing is bet now: the script bets in play, only when its conditions are met, and your safety limits apply. Practice mode: no real money.' : 'Placed as an AI order, so your safety limits apply. Practice mode: no real money. The bet appears on the Plan.'}</div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={() => setApply(null)}>Cancel</button><button className="primary" disabled={busy} onClick={confirm}>{busy ? 'Placing…' : 'Confirm and place'}</button></div></div></div>}
      {dismiss && <div className="overlay" onClick={() => setDismiss(null)}><div className="card" role="dialog" aria-label="Dismiss recommendation" onClick={e => e.stopPropagation()} style={{ width: 420 }}>
        <h3>Dismiss recommendation</h3><div className="small">{dismiss.title}</div>
        <label>Reason (optional)<input value={reason} onChange={e => setReason(e.target.value)} placeholder="Edge too small" /></label>
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={() => setDismiss(null)}>Cancel</button><button className="primary" onClick={() => api.recDismiss(dismiss.id, reason).then(() => { say('Dismissed.'); setDismiss(null); void load() }).catch(e => say((e as Error).message, 'err'))}>Dismiss</button></div></div></div>}
      <button hidden onClick={onPlan} />
    </div>
  )
}

/** Where the last scan for trade setups lost each market, so "nothing found" is explained: how many matches were listed, starting soon, priced, had data, and produced a setup. */
function ScanReport({ scan, run, busy }: { scan: ScanInfo | null; run: () => void; busy: boolean }) {
  const [open, setOpen] = useState(false)
  const when = scan ? new Date(scan.t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : null
  const total = scan ? Object.values(scan.sports).reduce((n, s) => n + s.setups, 0) : 0
  return <div className="small muted" style={{ margin: '6px 0' }}>
    {scan ? <>Last scan {when}: {total} setup{total === 1 ? '' : 's'} found. <button className="linkbtn" onClick={() => setOpen(o => !o)}>{open ? 'Hide detail' : 'Why so few?'}</button></> : 'No scan has run since the server started (it scans every 2 minutes).'}
    {' '}<button className="linkbtn" disabled={busy} onClick={run}>{busy ? 'Scanning…' : 'Scan now'}</button>
    {open && scan && <div className="card" style={{ padding: 10, marginTop: 6 }}>
      {Object.entries(scan.sports).map(([k, s]) => <div key={k} style={{ marginBottom: 6 }}>
        <b className="ink">{k === 'tennis' ? 'Tennis' : 'Football'}</b>: {s.markets} matches listed · {s.soon} start within 8 hours · {s.priced} priced · {s.with_context} with live data · {s.with_model} with a model view · <b className="ink">{s.setups} setups</b>
        {s.soon === 0 && <div>Nothing in scope starts in the next 8 hours (the scan only looks that far ahead, in scope leagues and tours only).</div>}
        {s.soon > 0 && s.priced < s.soon && <div>{s.soon - s.priced} of them have no open price yet.</div>}
        {s.priced > 0 && s.setups === 0 && <div>Priced matches did not meet a setup's price range or conditions (for example a favourite too short, or an Under 2.5 price outside 1.65 to 2.40).</div>}
        {s.errors.map((e, i) => <div key={i} className="loss">{e}</div>)}
      </div>)}
    </div>}
  </div>
}
