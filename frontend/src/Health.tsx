import { useEffect, useState } from 'react'
import { api, type HealthItem } from './api'

/** "System health" badge in the top bar with the list behind it. */
export default function HealthBadge() {
  const [h, setH] = useState<{ items: HealthItem[]; issues: number } | null>(null), [open, setOpen] = useState(false)
  useEffect(() => { let dead = false; const go = () => api.health().then(x => { if (!dead) setH(x) }).catch(() => undefined); go(); const t = window.setInterval(go, 15000); return () => { dead = true; window.clearInterval(t) } }, [])
  if (!h) return null
  return (
    <span style={{ position: 'relative' }}>
      <button className={'sm healthbtn ' + (h.issues ? 'bad' : 'ok')} onClick={() => setOpen(o => !o)} aria-expanded={open}>{h.issues ? `! System health · ${h.issues} issue${h.issues === 1 ? '' : 's'}` : '✓ System health'}</button>
      {open && <div className="healthpop card" role="dialog" aria-label="System health">
        {h.items.map(i => <div key={i.key} className="hrow"><span className={'hdot ' + i.level} aria-hidden /><div><b>{i.name}</b><div className="muted small">{i.detail}</div></div></div>)}
        <button className="sm" onClick={() => setOpen(false)}>Close</button></div>}
    </span>
  )
}
