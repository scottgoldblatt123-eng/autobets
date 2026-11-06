import { useCallback, useEffect, useState } from 'react'
import { api, type Rec, type Script, type ScriptRuleText } from './api'
import MarketPicker from './MarketPicker'
import ScriptEditor from './ScriptEditor'
import StarterLibrary from './StarterLibrary'
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
export function RuleCards({ text, fold, headline, startOpen }: { text: ScriptRuleText[]; fold?: boolean; headline?: string; startOpen?: boolean }) {
  const [open, setOpen] = useState(!fold || !!startOpen)
  if (fold && !open) return <button className="foldbtn" onClick={() => setOpen(true)} aria-expanded={false}>▸ {headline || `${text.length} rules`}</button>
  return <>{fold && <button className="foldbtn" onClick={() => setOpen(false)} aria-expanded>▾ {headline || `${text.length} rules`}</button>}{text.map(r => (
    <div key={r.id} className="rulecard"><div className="row" style={{ gap: 8, marginBottom: 4 }}><b>{r.kind === 'entry' ? 'Entry' : r.kind === 'exit' ? 'Exit' : 'Safety'}</b><span className="tag">Rule {r.id.replace(/^r/, '')}</span></div>
      <div className="small muted"><b className="ink">If</b> {r.if.join(' · ')}<br /><b className="ink">Then</b> {r.then.join(', then ')}</div></div>))}</>
}

/** Scripts: build with Claude or by hand, review in plain English, clone, version, enable, and put on the Plan. */
export default function ScriptsScreen({ say, onPlan }: { say: Say; onPlan: () => void }) {
  const [list, setList] = useState<Script[]>([]), [sel, setSel] = useState<string>(''), [q, setQ] = useState('')
  const [editor, setEditor] = useState<{ script: Script | null; initial?: Record<string, unknown> } | null>(null), [err, setErr] = useState(''), [hist, setHist] = useState(false), [pick, setPick] = useState(false), [starters, setStarters] = useState(false), [importing, setImporting] = useState<string | null>(null)
  const load = useCallback(() => api.scripts().then(l => { setList(l); setSel(s => (l.some(x => x.id === s) ? s : l[0]?.id ?? '')) }).catch(e => setErr((e as Error).message)), [])
  useEffect(() => { void load() }, [load])
  useEffect(() => { const f = (e: Event) => { void load().then(() => { const id = (e as CustomEvent<string>).detail; if (id) setSel(id) }) }; window.addEventListener('autobets:scripts-changed', f); return () => window.removeEventListener('autobets:scripts-changed', f) }, [load])
  const [props, setProps] = useState<Rec[]>([])
  const loadProps = useCallback(() => api.recs('script').then(r => setProps(r.items.filter(x => x.proposal && x.status === 'pending'))).catch(() => undefined), [])
  useEffect(() => { void loadProps() }, [loadProps])
  const cur = list.find(s => s.id === sel)
  const [lf, setLf] = useState('all')
  const shown = list.filter(s => (!q || (s.name + ' ' + s.description).toLowerCase().includes(q.toLowerCase())) && (lf === 'all' || (lf === 'on' ? s.enabled : lf === 'off' ? !s.enabled : lf === 'ai' ? s.origin === 'ai' : s.sport === lf || s.sport === 'any')))
  const guard = async (f: () => Promise<unknown>, ok?: string) => { setErr(''); try { await f(); if (ok) say(ok); await load() } catch (e) { setErr((e as Error).message) } }
  return (
    <div className="screen">
      <div className="row"><h1>Scripts</h1><span className="muted">Create, edit, clone and apply automation scripts</span><span className="spacer" />
        <input type="search" placeholder="Search scripts…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search scripts" />
        <button onClick={() => setStarters(true)}>Starter library</button>
        <button onClick={() => setImporting('')}>Import</button>
        <button onClick={() => setEditor({ script: null, initial: SCALP as unknown as Record<string, unknown> })}>Scalp example</button>
        <button className="primary" onClick={() => setEditor({ script: null, initial: TEMPLATE as unknown as Record<string, unknown> })}>New script</button></div>
      {props.length > 0 && <div className="card" style={{ padding: '8px 12px' }}>
        <div className="row"><b>Recommended scripts</b><span className="muted small">New ideas from Claude. Discuss them in the panel on the right, then approve to add one to your library (switched off).</span></div>
        {props.map(r => <div key={r.id} className="row" style={{ gap: 10, padding: '6px 0', borderTop: '1px solid var(--border)', alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}><span className="src ai">New</span> <b>{r.title}</b><div className="small muted">{r.reason}</div>{r.text?.length ? <RuleCards text={r.text} fold headline={r.headline} /> : null}</div>
          <button className="sm" onClick={() => window.dispatchEvent(new CustomEvent('autobets:seed', { detail: `Review this proposed script: "${r.title}". ${r.reason} Its rules in short: ${r.headline ?? ''}. Is the hypothesis sound, how would it lose, and what would you change?` }))}>Discuss</button>
          <button className="sm primary" onClick={async () => { try { const x = await api.recApply(r.id); say(`Added '${x.script?.name ?? ''}' to your library, switched off.`); await load(); void loadProps(); window.dispatchEvent(new CustomEvent('autobets:scripts-changed')) } catch (e) { say((e as Error).message, 'err') } }}>Approve</button>
          <button className="sm" onClick={() => api.recDismiss(r.id, 'not interested').then(loadProps)}>Dismiss</button>
        </div>)}
      </div>}
      {starters && <StarterLibrary onClose={() => setStarters(false)} onAdded={() => void load()} say={say} />}
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
              <button className="primary" onClick={() => setPick(true)} title="Pick a market and the runner it acts on. Nothing is placed until its conditions are met and the script is on. Practice mode: no real money.">Add to Plan…</button>
              <label className="sw"><input type="checkbox" checked={cur.enabled} onChange={e => guard(() => api.enableScript(cur.id, e.target.checked), e.target.checked ? 'Script on. It acts only on markets in your Plan.' : 'Script off.')} /> On</label>
              <button onClick={() => setEditor({ script: cur })}>Edit</button>
              <button onClick={() => guard(() => api.cloneScript(cur.id, `Copy of ${cur.name}`), 'Cloned (off).')}>Clone</button>
              <button onClick={() => setHist(true)}>Version history</button>
              <button className="danger" onClick={() => { if (window.confirm(`Delete "${cur.name}"? This cannot be undone.`)) void guard(() => api.deleteScript(cur.id), 'Deleted.') }}>Delete</button></div>
              {cur.description && <div className="small" style={{ marginTop: 6 }}>{cur.description}</div>}</div>
            <RuleCards key={cur.id} fold startOpen text={cur.text} headline={cur.headline} />
          </>}
        </section>
      </div>
      {editor && <ScriptEditor key={editor.script?.id ?? 'new'} script={editor.script} initial={editor.initial} say={say} onClose={() => setEditor(null)} onSaved={id => { setEditor(null); setSel(id); void load() }} />}
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
