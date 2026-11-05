import { useCallback, useEffect, useState } from 'react'
import { api, type Script, type ScriptRuleText } from './api'
import MarketPicker from './MarketPicker'
import { markScriptUsed } from './ScriptSelect'

type Say = (text: string, kind?: 'ok' | 'warn' | 'err') => void
const when = (t: number) => new Date(t * 1000).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const SCALP = { name: 'Scalp: 2 ticks, repeat 10', sport: 'football', description: 'Back at the best price, green up once the exit is 2 ticks in profit, then go again. One run at a time, 10 runs. Attach it to the Under 2.5 Goals runner.',
  rules: [{ id: 'r1', kind: 'entry', repeat: 10, when: [{ type: 'price', op: '>=', value: 1.01, ref: 'back' }], then: [{ type: 'back', price: 'best', stake: 10, basis: 'stake', persistence: 'CANCEL' }] },
    { id: 'r2', kind: 'exit', when: [{ type: 'rule_matched', rule: 'r1' }, { type: 'ticks_from_entry', op: '>=', value: 2 }], then: [{ type: 'green' }] },
    { id: 'r3', kind: 'safety', when: [{ type: 'ticks_from_entry', op: '<=', value: -6 }], then: [{ type: 'close' }, { type: 'stop' }] }] }
const TEMPLATE = { name: 'New script', sport: 'any', description: '', rules: [
  { id: 'r1', kind: 'entry', when: [{ type: 'price', op: '>=', value: 2.2, ref: 'last' }, { type: 'in_play', value: true }], then: [{ type: 'lay', price: 2.2, stake: 10, basis: 'stake', persistence: 'CANCEL' }] },
  { id: 'r2', kind: 'exit', when: [{ type: 'rule_matched', rule: 'r1' }, { type: 'price', op: '<=', value: 1.8, ref: 'last' }], then: [{ type: 'green' }] },
  { id: 'r3', kind: 'safety', when: [{ type: 'rule_matched', rule: 'r1' }, { type: 'position_loss', op: '>=', value: 15 }], then: [{ type: 'close' }, { type: 'stop' }] }] }

/** The rules of a script, one compact card each. `fold` shows just the headline with a toggle, for lists and chat. */
export function RuleCards({ text, fold, headline }: { text: ScriptRuleText[]; fold?: boolean; headline?: string }) {
  const [open, setOpen] = useState(!fold)
  if (fold && !open) return <button className="foldbtn" onClick={() => setOpen(true)} aria-expanded={false}>▸ {headline || `${text.length} rules`}</button>
  return <>{fold && <button className="foldbtn" onClick={() => setOpen(false)} aria-expanded>▾ {headline || `${text.length} rules`}</button>}{text.map(r => (
    <div key={r.id} className="rulecard"><div className="row" style={{ gap: 8, marginBottom: 4 }}><b>{r.kind === 'entry' ? 'Entry' : r.kind === 'exit' ? 'Exit' : 'Safety'}</b><span className="tag">Rule {r.id.replace(/^r/, '')}</span></div>
      <div className="small muted"><b className="ink">If</b> {r.if.join(' · ')}<br /><b className="ink">Then</b> {r.then.join(', then ')}</div></div>))}</>
}

/** Scripts: build with Claude or by hand, review in plain English, clone, version, enable, and put on the Plan. */
export default function ScriptsScreen({ say, onPlan }: { say: Say; onPlan: () => void }) {
  const [list, setList] = useState<Script[]>([]), [sel, setSel] = useState<string>(''), [q, setQ] = useState('')
  const [editing, setEditing] = useState<string | null>(null), [err, setErr] = useState(''), [hist, setHist] = useState(false), [pick, setPick] = useState(false), [importing, setImporting] = useState<string | null>(null)
  const load = useCallback(() => api.scripts().then(l => { setList(l); setSel(s => (l.some(x => x.id === s) ? s : l[0]?.id ?? '')) }).catch(e => setErr((e as Error).message)), [])
  useEffect(() => { void load() }, [load])
  useEffect(() => { const f = (e: Event) => { void load().then(() => { const id = (e as CustomEvent<string>).detail; if (id) setSel(id) }) }; window.addEventListener('autobets:scripts-changed', f); return () => window.removeEventListener('autobets:scripts-changed', f) }, [load])
  const cur = list.find(s => s.id === sel)
  const [lf, setLf] = useState('all')
  const shown = list.filter(s => (!q || (s.name + ' ' + s.description).toLowerCase().includes(q.toLowerCase())) && (lf === 'all' || (lf === 'on' ? s.enabled : lf === 'off' ? !s.enabled : lf === 'ai' ? s.origin === 'ai' : s.sport === lf || s.sport === 'any')))
  const guard = async (f: () => Promise<unknown>, ok?: string) => { setErr(''); try { await f(); if (ok) say(ok); await load() } catch (e) { setErr((e as Error).message) } }
  const full = (s: Script) => JSON.stringify({ name: s.name, sport: s.sport, description: s.description, rules: s.rules }, null, 2)
  return (
    <div className="screen">
      <div className="row"><h1>Scripts</h1><span className="muted">Create, edit, clone and apply automation scripts</span><span className="spacer" />
        <input type="search" placeholder="Search scripts…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search scripts" />
        <button onClick={() => setImporting('')}>Import</button>
        <button onClick={() => setEditing(JSON.stringify(SCALP, null, 2))}>Scalp example</button>
        <button className="primary" onClick={() => setEditing(JSON.stringify(TEMPLATE, null, 2))}>New script</button></div>
      {err && <div className="loss small">{err}</div>}
      <div className="split">
        <aside className="card library"><div className="cap">Library ({shown.length}{shown.length !== list.length ? ` of ${list.length}` : ''})</div>
          <div className="chips">{[['all', 'All'], ['on', 'On'], ['off', 'Off'], ['ai', 'AI drafts'], ['tennis', 'Tennis'], ['football', 'Football']].map(([k, l]) => <button key={k} className={'chip' + (lf === k ? ' on' : '')} onClick={() => setLf(k)}>{l}</button>)}</div>
          {shown.map(s => <button key={s.id} className={'librow' + (s.id === sel ? ' on' : '')} onClick={() => setSel(s.id)}>{s.name}{s.headline && <span className="muted small trunc">{s.headline}</span>}<span className="muted small">{s.sport === 'any' ? 'Any' : s.sport[0].toUpperCase() + s.sport.slice(1)} · v{s.version} · {s.origin === 'ai' ? 'AI built' : 'yours'}{s.enabled ? ' · ON' : ''}</span></button>)}
          {!shown.length && <div className="muted small pad">{list.length ? 'No script matches.' : 'No scripts yet. Describe one above, or start from New script.'}</div>}
        </aside>
        <section className="detail">
          {!cur ? <div className="empty muted">Select a script.</div> : <>
            <div className="card"><div className="row"><h2>{cur.name}</h2><span className={'src' + (cur.origin === 'ai' ? ' ai' : '')}>{cur.origin === 'ai' ? 'AI built' : 'Yours'}</span><span className="muted small">v{cur.version} · {cur.enabled ? 'on' : 'off, not applied'}</span><span className="spacer" />
              <label className="sw"><input type="checkbox" checked={cur.enabled} onChange={e => guard(() => api.enableScript(cur.id, e.target.checked), e.target.checked ? 'Script on. It acts only on markets in your Plan.' : 'Script off.')} /> On</label>
              <button onClick={() => setEditing(full(cur))}>Edit</button>
              <button onClick={() => guard(() => api.cloneScript(cur.id, `Copy of ${cur.name}`), 'Cloned (off).')}>Clone</button>
              <button onClick={() => setHist(true)}>Version history</button>
              <button className="danger" onClick={() => { if (window.confirm(`Delete "${cur.name}"? This cannot be undone.`)) void guard(() => api.deleteScript(cur.id), 'Deleted.') }}>Delete</button></div>
              <div className="muted small" style={{ marginTop: 6 }}>The script name is what appears in the Strategy column on the Plan and everywhere else. Rename it and every plan row follows.</div>
              {cur.description && <div className="small" style={{ marginTop: 6 }}>{cur.description}</div>}</div>
            <RuleCards text={cur.text} />
            <div className="card"><div className="row"><h3>Put it to work</h3><span className="spacer" />
              <button disabled title="Backtests need logged price history. The Betfair price log is still collecting; this unlocks in the Analyse step." >Backtest (collecting data)</button>
              <button className="primary" onClick={() => setPick(true)}>Add to Plan…</button></div>
              <p className="muted small" style={{ margin: '8px 0 0' }}>Pick a market and the runner it acts on. Nothing is placed until the script's conditions are met and it is switched on. Practice mode is on, so no real money is used.</p></div>
          </>}
        </section>
      </div>
      {editing !== null && <div className="overlay" onClick={() => setEditing(null)}><div className="card scroll" role="dialog" aria-label="Edit script" onClick={e => e.stopPropagation()} style={{ width: 720, maxWidth: '96vw' }}>
        <h3>{cur && editing === full(cur) ? 'Edit script' : 'New script'}</h3>
        <div className="muted small">Scripts are plain data. Conditions: price, in_play, set_number, goals_total, score_is, minute, rule_matched, position_loss, clock. Actions: back, lay, green, close, stop. The server checks it and explains anything wrong.</div>
        <textarea className="code" rows={22} value={editing} onChange={e => setEditing(e.target.value)} spellCheck={false} aria-label="Script JSON" />
        {err && <div className="loss small">{err}</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={() => setEditing(null)}>Cancel</button>
          <button className="primary" onClick={() => guard(async () => { const body = JSON.parse(editing); const isEdit = cur && editing === full(cur) ? true : cur && JSON.parse(editing).name === cur.name && JSON.stringify(JSON.parse(editing).rules) !== JSON.stringify(cur.rules)
            const s = isEdit && cur ? await api.updateScript(cur.id, body) : await api.createScript(body); setSel(s.id); setEditing(null) }, 'Saved as a new version.')}>Save</button></div></div></div>}
      {importing !== null && <div className="overlay" onClick={() => setImporting(null)}><div className="card" role="dialog" aria-label="Import script" onClick={e => e.stopPropagation()} style={{ width: 560, maxWidth: '95vw' }}>
        <h3>Import script</h3><div className="muted small">Paste a script's JSON. It is checked against the script rules before it is saved, and it starts off.</div>
        <textarea className="code" rows={12} value={importing} onChange={e => setImporting(e.target.value)} spellCheck={false} aria-label="Script JSON to import" />
        {err && <div className="loss small">{err}</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={() => setImporting(null)}>Cancel</button>
          <button className="primary" onClick={() => guard(async () => { const s = await api.createScript(JSON.parse(importing)); setSel(s.id); setImporting(null) }, 'Imported. Script is off until you enable it.')}>Validate and import</button></div></div></div>}
      {hist && cur && <div className="overlay" onClick={() => setHist(false)}><div className="card" role="dialog" aria-label="Version history" onClick={e => e.stopPropagation()}><h3>Version history</h3>
        {[...cur.history].reverse().map(h => <div key={h.version} className="small">v{h.version} · {when(h.t)} · {h.note}</div>)}
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={() => setHist(false)}>Close</button></div></div></div>}
      {pick && cur && <MarketPicker say={say} needRunner title={`Add "${cur.name}" to Plan`} onClose={() => setPick(false)}
        onPick={(m, sid) => { setPick(false); markScriptUsed(cur.id); void guard(() => api.planAdd({ market_id: m.market_id, selection_id: sid, script_id: cur.id }), `Added to your Plan: ${m.event}.`).then(onPlan) }} />}
    </div>
  )
}
