import { useState } from 'react'
import type { MarketInfo } from './api'
import MarketFinder from './MarketFinder'

/** Pick one market from the full market list (search, filters, every market on an event) and, optionally, the runner a script acts on. */
export default function MarketPicker({ needRunner, onPick, onClose, title = 'Add market to Plan', say }: { needRunner: boolean; onPick: (m: MarketInfo, selectionId: string | null) => void; onClose: () => void; title?: string; say?: (t: string, k?: 'ok' | 'warn' | 'err') => void }) {
  const [m, setM] = useState<MarketInfo | null>(null)
  return (
    <div className="overlay" onClick={onClose}>
      <div className="card scroll" role="dialog" aria-label={title} onClick={e => e.stopPropagation()} style={{ width: 520, maxWidth: '95vw', height: 'min(640px, 90vh)' }}>
        <h3>{title}</h3>
        {!m ? <div style={{ flex: 1, minHeight: 0, display: 'flex' }}><MarketFinder mode="pick" say={say ?? (() => undefined)} onPick={x => (needRunner ? setM(x) : onPick(x, null))} /></div> : <>
          <div className="small"><b>{m.event}</b> · {m.name}</div>
          <div className="muted small">Which runner does the script act on?</div>
          <div className="pickerlist">{Object.entries(m.runners).map(([sid, n]) => <button key={sid} className="pickrow" onClick={() => onPick(m, sid)}>{n}</button>)}</div>
          <div className="row"><button onClick={() => setM(null)}>Back</button></div></>}
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={onClose}>Cancel</button></div>
      </div>
    </div>
  )
}
