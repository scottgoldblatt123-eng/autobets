import { useState } from 'react'
import { api, type Script, type ScriptRuleText } from './api'
import { RuleCards } from './ScriptsScreen'

type Obj = Record<string, unknown>
interface Rule { id: string; kind: 'entry' | 'exit' | 'safety'; when: Obj[]; then: Obj[]; repeat?: number }
interface Draft { name: string; sport: string; description: string; rules: Rule[] }

const LABEL: Record<string, string> = {
  price: 'Price', in_play: 'In play', set_number: 'Set number (tennis)', set_games_diff: 'Games ahead (+) or behind (−) in the set (tennis)', sets_diff: 'Sets ahead (+) or behind (−) (tennis)',
  goals_total: 'Total goals (football)', score_is: 'Exact score (football)', minute: 'Match minute (football)', rule_matched: 'An earlier rule has fired', position_loss: 'Possible loss £',
  clock: 'Time of day (UK)', ticks_from_entry: 'Ticks of profit (+) or loss (−) since entry', ticks_from_peak: 'Ticks given back from the best (trailing stop)',
  minutes_to_start: 'Minutes to the scheduled start', spread_ticks: 'Spread in ticks', market_matched: 'Matched on the market £', price_move: 'Price move in ticks over N seconds',
}
const DEFAULT: Record<string, Obj> = {
  price: { type: 'price', op: '>=', value: 2, ref: 'back' }, in_play: { type: 'in_play', value: true }, set_number: { type: 'set_number', op: '==', value: 1 },
  set_games_diff: { type: 'set_games_diff', op: '<=', value: -1 }, sets_diff: { type: 'sets_diff', op: '>=', value: 1 }, goals_total: { type: 'goals_total', op: '<=', value: 1 },
  score_is: { type: 'score_is', home: 0, away: 0 }, minute: { type: 'minute', op: '>=', value: 15 }, position_loss: { type: 'position_loss', op: '>=', value: 10 },
  clock: { type: 'clock', start: '19:00', end: '22:00' }, ticks_from_entry: { type: 'ticks_from_entry', op: '>=', value: 2 }, ticks_from_peak: { type: 'ticks_from_peak', value: 3 },
  minutes_to_start: { type: 'minutes_to_start', op: '<=', value: 30 }, spread_ticks: { type: 'spread_ticks', op: '<=', value: 2 }, market_matched: { type: 'market_matched', op: '>=', value: 50000 },
  price_move: { type: 'price_move', op: '<=', value: -3, seconds: 60 },
}
const KIND: Record<string, string> = { entry: 'Entry: opens the position', exit: 'Exit: takes it off', safety: 'Safety: limits the loss' }

function Field({ k, v, onChange, rules, idx }: { k: string; v: unknown; onChange: (x: unknown) => void; rules: Rule[]; idx: number }) {
  if (k === 'op') return <select value={String(v)} onChange={e => onChange(e.target.value)} aria-label="Comparison">{['>=', '<=', '==', '>', '<'].map(o => <option key={o}>{o}</option>)}</select>
  if (k === 'ref') return <select value={String(v ?? 'last')} onChange={e => onChange(e.target.value)} aria-label="Which price"><option value="last">last traded</option><option value="back">best back</option><option value="lay">best lay</option></select>
  if (k === 'rule') return <select value={String(v)} onChange={e => onChange(e.target.value)}>{rules.slice(0, idx).map(r => <option key={r.id} value={r.id}>{r.id}</option>)}</select>
  if (typeof v === 'boolean') return <select value={String(v)} onChange={e => onChange(e.target.value === 'true')}><option value="true">yes</option><option value="false">no</option></select>
  if (k === 'start' || k === 'end') return <input style={{ width: 70 }} value={String(v)} onChange={e => onChange(e.target.value)} aria-label={k} />
  if (k === 'basis') return <select value={String(v)} onChange={e => onChange(e.target.value)}><option value="stake">stake</option><option value="liability">liability</option></select>
  if (k === 'persistence') return <select value={String(v)} onChange={e => onChange(e.target.value)}><option value="CANCEL">cancel at in-play</option><option value="KEEP">keep in play</option><option value="TAKE_SP">take SP</option></select>
  const num = typeof v === 'number'
  return <input style={{ width: 78 }} inputMode="decimal" value={String(v)} aria-label={k} onChange={e => { const t = e.target.value; onChange(num && t.trim() !== '' && Number.isFinite(Number(t)) ? Number(t) : t) }} />
}

/** Edit a script without touching JSON: a form for its settings, a prompt for Claude to revise it, and the raw data for experts. Saves as a new version, or as a copy. */
export default function ScriptEditor({ script, initial, onClose, onSaved, say }: { script: Script | null; initial?: Obj; onClose: () => void; onSaved: (id: string) => void; say: (t: string, k?: 'ok' | 'warn' | 'err') => void }) {
  const [d, setD] = useState<Draft>(() => initial ? (JSON.parse(JSON.stringify(initial)) as Draft) : script ? { name: script.name, sport: script.sport, description: script.description, rules: JSON.parse(JSON.stringify(script.rules)) } : { name: 'New script', sport: 'any', description: '', rules: [] })
  const [tab, setTab] = useState<'settings' | 'ask' | 'json'>('settings'), [json, setJson] = useState(''), [err, setErr] = useState(''), [busy, setBusy] = useState(false)
  const [ask, setAsk] = useState(''), [proposal, setProposal] = useState<{ explanation: string; script: Obj | null; text?: ScriptRuleText[]; headline?: string; error: string | null } | null>(null)
  const setRule = (i: number, f: (r: Rule) => Rule) => setD(x => ({ ...x, rules: x.rules.map((r, j) => (j === i ? f(r) : r)) }))
  const setIn = (i: number, key: 'when' | 'then', j: number, field: string, val: unknown) => setRule(i, r => ({ ...r, [key]: r[key].map((c, n) => (n === j ? { ...c, [field]: val } : c)) }))
  const body = () => (tab === 'json' ? JSON.parse(json) : d)
  const switchTo = (t: typeof tab) => { if (tab === 'json') { try { setD(JSON.parse(json)); setErr('') } catch { setErr('The Advanced text is not valid JSON, so it was not applied.'); return } } if (t === 'json') setJson(JSON.stringify(d, null, 2)); setTab(t) }
  const save = async (asCopy: boolean) => {
    setErr(''); setBusy(true)
    try {
      const b = body() as Obj
      if (asCopy) b.name = `${String(b.name)} (copy)`
      const s = script && !asCopy ? await api.updateScript(script.id, b) : await api.createScript(b)
      say(asCopy ? 'Saved as a copy (switched off). The original is unchanged.' : script ? 'Saved as a new version.' : 'Saved (switched off until you enable it).')
      onSaved(s.id)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const revise = async () => {
    setErr(''); setBusy(true); setProposal(null)
    try {
      const cur = tab === 'json' ? JSON.parse(json) : d
      setProposal(await api.buildScript(`Here is an existing script:\n\`\`\`script\n${JSON.stringify(cur)}\n\`\`\`\nChange it as follows and keep everything else exactly as it is, including its name unless I ask to rename it: ${ask}`))
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const addCond = (i: number, t: string) => t && setRule(i, r => ({ ...r, when: [...r.when, { ...DEFAULT[t] }] }))
  return (
    <div className="overlay" onClick={onClose}><div className="card scroll" role="dialog" aria-label="Edit script" onClick={e => e.stopPropagation()} style={{ width: 860, maxWidth: '96vw' }}>
      <div className="row"><h3 style={{ margin: 0 }}>{script ? `Edit ${script.name}` : 'New script'}</h3><span className="spacer" />
        <div className="viewsw" role="tablist">{([['settings', 'Settings'], ['ask', 'Ask Claude to change it'], ['json', 'Advanced']] as const).map(([k, l]) => <button key={k} role="tab" className={tab === k ? 'on' : ''} onClick={() => switchTo(k)}>{l}</button>)}</div></div>
      {script && <div className="muted small" style={{ margin: '6px 0' }}>Saving creates a new version (the old one stays in History). To keep the original exactly as it is, use <b>Save as a copy</b>.</div>}

      {tab === 'settings' && <div>
        <div className="row" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label>Name<input value={d.name} onChange={e => setD({ ...d, name: e.target.value })} style={{ width: 280 }} /></label>
          <label>Sport<select value={d.sport} onChange={e => setD({ ...d, sport: e.target.value })}><option value="any">Any</option><option value="tennis">Tennis</option><option value="football">Football</option></select></label>
        </div>
        <label style={{ display: 'block', margin: '8px 0' }}>Description<input value={d.description} onChange={e => setD({ ...d, description: e.target.value })} style={{ width: '100%' }} /></label>
        {d.rules.map((r, i) => <div key={r.id} className="card" style={{ margin: '8px 0', padding: '8px 10px' }}>
          <div className="row"><b>{r.id}</b><span className="small muted">{KIND[r.kind]}</span><span className="spacer" />
            {r.kind === 'entry' && <label className="row small" style={{ gap: 6 }}>Repeat<input style={{ width: 52 }} inputMode="numeric" value={r.repeat ?? 1} onChange={e => setRule(i, x => ({ ...x, repeat: Math.max(1, Math.min(100, Number(e.target.value) || 1)) }))} title="After this rule's exit has greened and the position is level, run again up to this many times" /></label>}
            <button className="sm" aria-label={`Remove rule ${r.id}`} title="Remove this rule" onClick={() => setD(x => ({ ...x, rules: x.rules.filter((_, j) => j !== i) }))}>Remove rule</button></div>
          <div className="small muted" style={{ marginTop: 4 }}>When all of these are true:</div>
          {r.when.map((c, j) => <div key={j} className="row" style={{ gap: 6, padding: '3px 0' }}>
            <span style={{ minWidth: 250 }}>{LABEL[String(c.type)] ?? String(c.type)}</span>
            {Object.entries(c).filter(([k]) => k !== 'type').map(([k, v]) => <Field key={k} k={k} v={v} rules={d.rules} idx={i} onChange={x => setIn(i, 'when', j, k, x)} />)}
            <button className="sm" aria-label="Remove condition" onClick={() => setRule(i, x => ({ ...x, when: x.when.filter((_, n) => n !== j) }))}>×</button></div>)}
          <select value="" onChange={e => addCond(i, e.target.value)} aria-label="Add a condition"><option value="">+ Add a condition…</option>{Object.keys(DEFAULT).map(t => <option key={t} value={t}>{LABEL[t]}</option>)}</select>
          <div className="small muted" style={{ marginTop: 6 }}>Then:</div>
          {r.then.map((a, j) => <div key={j} className="row" style={{ gap: 6, padding: '3px 0' }}>
            <b style={{ minWidth: 60, textTransform: 'capitalize' }}>{String(a.type)}</b>
            {Object.entries(a).filter(([k]) => k !== 'type').map(([k, v]) => <label key={k} className="row small" style={{ gap: 4 }}>{k === 'price' ? 'price' : k === 'stake' ? 'stake £' : k === 'basis' ? 'by' : k === 'persistence' ? 'if unmatched' : k}<Field k={k} v={v} rules={d.rules} idx={i} onChange={x => setIn(i, 'then', j, k, x)} /></label>)}</div>)}
        </div>)}
        {!d.rules.length && <div className="muted small">No rules yet. Use Ask Claude to change it, or Advanced, to add some.</div>}
        <div className="muted small">To add a whole new rule, use Ask Claude to change it (for example "add a stop that closes at 8 ticks against"), or Advanced.</div>
      </div>}

      {tab === 'ask' && <div>
        <p className="small muted">Describe the change in plain English. Claude revises the whole script and shows you the result to review before anything is kept. Nothing is saved until you press Save.</p>
        <textarea rows={4} style={{ width: '100%' }} value={ask} onChange={e => setAsk(e.target.value)} placeholder="e.g. Halve the stake, take 3 ticks instead of 2, and stop after the 60th minute" aria-label="Change request" />
        <div className="row"><button className="primary" disabled={busy || !ask.trim()} onClick={revise}>{busy ? 'Thinking…' : 'Revise the script'}</button></div>
        {proposal && <div className="card" style={{ marginTop: 8, padding: '8px 10px' }}>
          <div className="small">{proposal.explanation}</div>
          {proposal.error && <div className="loss small">{proposal.error}</div>}
          {proposal.script && <><div style={{ margin: '6px 0' }}><RuleCards text={proposal.text ?? []} headline={proposal.headline} /></div>
            <div className="row"><button className="primary" onClick={() => { setD(proposal.script as unknown as Draft); setProposal(null); setAsk(''); setTab('settings') }}>Use this version</button><span className="small muted">It loads into Settings so you can fine-tune it, then Save.</span></div></>}
        </div>}
      </div>}

      {tab === 'json' && <div><div className="muted small">The script as data, for experts. The server checks it when you save.</div>
        <textarea className="code" rows={20} value={json} onChange={e => setJson(e.target.value)} spellCheck={false} aria-label="Script JSON" /></div>}

      {err && <div className="loss small" style={{ marginTop: 6 }}>{err}</div>}
      <div className="row" style={{ justifyContent: 'flex-end', marginTop: 10 }}>
        <button onClick={onClose}>Cancel</button>
        {script && <button disabled={busy} onClick={() => save(true)} title="Keep the original untouched and save this version as a new script">Save as a copy</button>}
        <button className="primary" disabled={busy} onClick={() => save(false)}>{script ? 'Save as new version' : 'Save'}</button></div>
    </div></div>
  )
}
