import { useEffect, useState } from 'react'
import { api } from './api'
import ScriptSelect, { markScriptUsed } from './ScriptSelect'

/** Put a market on the Plan: watch it, or attach a script (and pick the runner the script acts on). */
export default function AttachDialog({ marketId, title, onDone, onClose }: { marketId: string; title: string; onDone: (msg: string, kind?: 'ok' | 'err') => void; onClose: () => void }) {
  const [sid, setSid] = useState<string>(''), [runners, setRunners] = useState<Record<string, string>>({})
  useEffect(() => { if (sid) api.state([marketId]).then(s => setRunners(s.markets[marketId]?.runners ?? {})).catch(() => undefined) }, [sid, marketId])
  const add = (script_id: string | null, selection_id: string | null) => api.planAdd({ market_id: marketId, selection_id, script_id }).then(() => { markScriptUsed(script_id); onDone(script_id ? 'Added to your Plan.' : 'Added to your Plan (watching).'); onClose() }).catch(e => onDone((e as Error).message, 'err'))
  return (
    <div className="overlay" onClick={onClose}><div className="card" role="dialog" aria-label="Add to Plan" onClick={e => e.stopPropagation()} style={{ width: 460 }}>
      <h3>{title}</h3><div className="muted small">Attach a script, or just watch the market.</div>
      <div className="row"><button onClick={() => add(null, null)}>Just watch it</button></div>
      <label>Or attach a script<ScriptSelect value={sid} onChange={setSid} /></label>
      {sid && <><div className="muted small">Which runner does it act on?</div><div className="pickerlist">{Object.entries(runners).map(([r, n]) => <button key={r} className="pickrow" onClick={() => add(sid, r)}>{n}</button>)}</div></>}
      <div className="row" style={{ justifyContent: 'flex-end', display: 'flex' }}><button onClick={onClose}>Cancel</button></div></div></div>
  )
}
