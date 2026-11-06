import { useEffect, useState } from 'react'
import { api, type ScriptRuleText } from './api'
import { RuleCards } from './ScriptsScreen'

interface Starter { id: string; sport: string; title: string; summary: string; attach: string; caveats: string[]; source: string; headline: string; text: ScriptRuleText[]; added: boolean }
interface Unsupported { title: string; sport: string; reason: string }

/** Ready-made scripts based on well-known community ideas, written fresh for AutoBets. Adding one puts a switched-off copy in your library. */
export default function StarterLibrary({ onClose, onAdded, say }: { onClose: () => void; onAdded: () => void; say: (t: string, k?: 'ok' | 'warn' | 'err') => void }) {
  const [items, setItems] = useState<Starter[]>([]), [un, setUn] = useState<Unsupported[]>([]), [f, setF] = useState('all'), [err, setErr] = useState(''), [busy, setBusy] = useState(false)
  const load = () => api.starters().then(r => { setItems(r.items); setUn(r.unsupported) }).catch(e => setErr((e as Error).message))
  useEffect(() => { void load() }, [])
  const add = async (ids: string[]) => {
    setBusy(true); setErr('')
    try { for (const id of ids) await api.addStarter(id); say(ids.length === 1 ? 'Added to your library, switched off.' : `Added ${ids.length} scripts to your library, all switched off.`); onAdded(); await load() } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const shown = items.filter(s => f === 'all' || s.sport === f)
  const todo = shown.filter(s => !s.added).map(s => s.id)
  return (
    <div className="overlay" onClick={onClose}>
      <div className="card" role="dialog" aria-label="Starter library" onClick={e => e.stopPropagation()} style={{ width: 820, maxWidth: '95vw', maxHeight: '88vh', overflow: 'auto' }}>
        <div className="row"><h2 style={{ margin: 0 }}>Starter library</h2><span className="spacer" /><button onClick={onClose}>Close</button></div>
        <p className="small muted">Well-known automation ideas from the Betfair trading community, rebuilt as AutoBets scripts in our own words. They are starting points, not proven edges: add one (it arrives switched off), read it, change the numbers, and test it in practice mode before you trust it.</p>
        <div className="row" style={{ gap: 8 }}>
          <div className="chips">{[['all', 'All'], ['tennis', 'Tennis'], ['football', 'Football']].map(([k, l]) => <button key={k} className={'chip' + (f === k ? ' on' : '')} onClick={() => setF(k)}>{l}</button>)}</div>
          <span className="spacer" />
          <button className="primary" disabled={busy || !todo.length} onClick={() => add(todo)}>Add all {todo.length} not yet added</button>
        </div>
        {err && <div className="loss small">{err}</div>}
        {shown.map(s => <div key={s.id} className="rulecard" style={{ marginTop: 8 }}>
          <div className="row" style={{ gap: 8 }}><b>{s.title}</b><span className="tag">{s.sport}</span><span className="spacer" />
            {s.added ? <span className="muted small">In your library</span> : <button className="sm primary" disabled={busy} onClick={() => add([s.id])}>Add to my library</button>}</div>
          <div className="small">{s.summary}</div>
          <div className="small muted"><b className="ink">Attach to:</b> {s.attach}</div>
          {s.caveats.map((c, i) => <div key={i} className="small muted">• {c}</div>)}
          <RuleCards text={s.text} fold headline={s.headline} />
        </div>)}
        <h3>Not available yet</h3>
        <p className="small muted">Some popular Bet Angel bots need things a script cannot do here yet.</p>
        {un.filter(u => f === 'all' || u.sport === f).map(u => <div key={u.title} className="small" style={{ marginTop: 6 }}><b>{u.title}</b> <span className="tag">{u.sport}</span><div className="muted">{u.reason}</div></div>)}
      </div>
    </div>
  )
}
