import { useEffect, useState } from 'react'
import { api, type MarketInfo } from './api'

/** Pick a market (search the list) and, optionally, the runner a script acts on. */
export default function MarketPicker({ needRunner, onPick, onClose, title = 'Add market to Plan' }: { needRunner: boolean; onPick: (m: MarketInfo, selectionId: string | null) => void; onClose: () => void; title?: string }) {
  const [sport, setSport] = useState<'tennis' | 'football'>('tennis'), [list, setList] = useState<MarketInfo[]>([]), [q, setQ] = useState(''), [m, setM] = useState<MarketInfo | null>(null), [err, setErr] = useState('')
  useEffect(() => { setList([]); api.markets(sport).then(setList).catch(e => setErr((e as Error).message)) }, [sport])
  const shown = list.filter(x => !q || (x.event + ' ' + x.competition + ' ' + x.name).toLowerCase().includes(q.toLowerCase())).slice(0, 80)
  return (
    <div className="overlay" onClick={onClose}>
      <div className="card scroll" role="dialog" aria-label={title} onClick={e => e.stopPropagation()} style={{ width: 560, maxWidth: '95vw' }}>
        <h3>{title}</h3>
        {err && <div className="loss small">{err}</div>}
        {!m ? <>
          <div className="row">
            {(['tennis', 'football'] as const).map(s => <button key={s} className={'chip' + (sport === s ? ' on' : '')} onClick={() => setSport(s)}>{s === 'tennis' ? 'Tennis' : 'Football'}</button>)}
            <input type="search" autoFocus placeholder="Search players, teams, competitions…" value={q} onChange={e => setQ(e.target.value)} style={{ flex: 1 }} aria-label="Search markets" />
          </div>
          <div className="pickerlist">
            {shown.map(x => <button key={x.market_id} className="pickrow" onClick={() => (needRunner ? setM(x) : onPick(x, null))}><span>{x.in_play && <b className="livedot" />}{x.event}</span><small className="muted">{x.competition} · {x.name}</small></button>)}
            {!shown.length && <div className="muted small pad">{list.length ? 'No match.' : 'Loading…'}</div>}
          </div>
        </> : <>
          <div className="small"><b>{m.event}</b> · {m.name}</div>
          <div className="muted small">Which runner does the script act on?</div>
          <div className="pickerlist">{Object.entries(m.runners).map(([sid, n]) => <button key={sid} className="pickrow" onClick={() => onPick(m, sid)}>{n}</button>)}</div>
          <div className="row"><button onClick={() => setM(null)}>Back</button></div>
        </>}
        <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={onClose}>Cancel</button></div>
      </div>
    </div>
  )
}
