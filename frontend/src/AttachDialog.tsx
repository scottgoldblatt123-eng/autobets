import { useEffect, useState } from 'react'
import { api, type Script } from './api'

/** Put a market on the Plan: watch it, or attach a script (and pick the runner the script acts on). */
export default function AttachDialog({ marketId, title, onDone, onClose }: { marketId: string; title: string; onDone: (msg: string, kind?: 'ok' | 'err') => void; onClose: () => void }) {
  const [scripts, setScripts] = useState<Script[]>([]), [sid, setSid] = useState<string | null>(null), [runners, setRunners] = useState<Record<string, string>>({})
  useEffect(() => { api.scripts().then(setScripts).catch(() => undefined) }, [])
  useEffect(() => { if (sid) api.state([marketId]).then(s => setRunners(s.markets[marketId]?.runners ?? {})).catch(() => undefined) }, [sid, marketId])
  const add = (script_id: string | null, selection_id: string | null) => api.planAdd({ market_id: marketId, selection_id, script_id }).then(() => { onDone(script_id ? 'Added to your Plan.' : 'Added to your Plan (watching).'); onClose() }).catch(e => onDone((e as Error).message, 'err'))
  return (
    <div className="overlay" onClick={onClose}><div className="card" role="dialog" aria-label="Add to Plan" onClick={e => e.stopPropagation()} style={{ width: 460 }}>
      <h3>{title}</h3><div className="muted small">Attach a script, or just watch the market.</div>
      <div className="pickerlist"><button className="pickrow" onClick={() => add(null, null)}>None (watching only)</button>
        {scripts.map(s => <button key={s.id} className={'pickrow' + (sid === s.id ? ' on' : '')} onClick={() => setSid(s.id)}>{s.name}<small className="muted"> v{s.version}{s.enabled ? ' · on' : ' · off'}</small></button>)}
        {!scripts.length && <div className="muted small pad">No scripts yet. Create one on the Scripts screen.</div>}</div>
      {sid && <><div className="muted small">Which runner does it act on?</div><div className="pickerlist">{Object.entries(runners).map(([r, n]) => <button key={r} className="pickrow" onClick={() => add(sid, r)}>{n}</button>)}</div></>}
      <div className="row" style={{ justifyContent: 'flex-end', display: 'flex' }}><button onClick={onClose}>Cancel</button></div></div></div>
  )
}
