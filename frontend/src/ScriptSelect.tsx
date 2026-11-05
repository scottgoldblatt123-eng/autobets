import { useEffect, useMemo, useState } from 'react'
import { api, type Script } from './api'

const RECENT = 'autobets.recentScripts'
export const markScriptUsed = (id: string | null) => { if (!id) return; try { const r: string[] = JSON.parse(localStorage.getItem(RECENT) ?? '[]'); localStorage.setItem(RECENT, JSON.stringify([id, ...r.filter(x => x !== id)].slice(0, 8))) } catch { /* storage unavailable */ } }
const recent = (): string[] => { try { return JSON.parse(localStorage.getItem(RECENT) ?? '[]') } catch { return [] } }
const SPORTS: [string, string][] = [['all', 'All'], ['tennis', 'Tennis'], ['football', 'Football'], ['any', 'Any sport']]

/** Choose a script from a list that stays usable as it grows: search, sport filter, "Recently used" on top, then On and Off. The list is fetched each time it opens, so a script just created elsewhere is there. */
export default function ScriptSelect({ value, onChange, allowNone = false, noneLabel = 'None: watch only', sportHint }: { value: string; onChange: (id: string) => void; allowNone?: boolean; noneLabel?: string; sportHint?: string }) {
  const [open, setOpen] = useState(false), [list, setList] = useState<Script[]>([]), [q, setQ] = useState(''), [sport, setSport] = useState(sportHint && sportHint !== 'any' ? sportHint : 'all'), [loaded, setLoaded] = useState(false)
  useEffect(() => { api.scripts().then(l => { setList(l); setLoaded(true) }).catch(() => setLoaded(true)) }, [open])
  const cur = list.find(s => s.id === value)
  const ok = (s: Script) => (sport === 'all' || s.sport === sport || s.sport === 'any') && (!q || (s.name + ' ' + s.description).toLowerCase().includes(q.toLowerCase()))
  const sections = useMemo(() => {
    const shown = list.filter(ok), rec = recent(), used = new Set<string>()
    const out: [string, Script[]][] = []
    if (!q) { const r = rec.map(id => shown.find(s => s.id === id)).filter(Boolean) as Script[]; if (r.length) { out.push(['Recently used', r.slice(0, 5)]); r.slice(0, 5).forEach(s => used.add(s.id)) } }
    const rest = shown.filter(s => !used.has(s.id))
    if (rest.some(s => s.enabled)) out.push(['On', rest.filter(s => s.enabled)])
    if (rest.some(s => !s.enabled)) out.push(['Off', rest.filter(s => !s.enabled)])
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list, q, sport])
  const pick = (id: string) => { onChange(id); setOpen(false); setQ('') }
  return (
    <div className="scriptselect">
      <button type="button" className="ssbtn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <span>{value ? (cur ? `${cur.name} v${cur.version}` : 'Script') : allowNone ? noneLabel : 'Choose a script…'}</span><span className="muted">▾</span></button>
      {open && <div className="sspanel" role="listbox">
        <input type="search" autoFocus placeholder={`Search ${list.length} script${list.length === 1 ? '' : 's'}…`} value={q} onChange={e => setQ(e.target.value)} aria-label="Search scripts" />
        <div className="chips">{SPORTS.map(([k, l]) => <button type="button" key={k} className={'chip' + (sport === k ? ' on' : '')} onClick={() => setSport(k)}>{l}</button>)}</div>
        <div className="sslist">
          {allowNone && !q && <button type="button" className={'pickrow' + (!value ? ' on' : '')} onClick={() => pick('')}>{noneLabel}</button>}
          {sections.map(([h, xs]) => <div key={h}><div className="mxh">{h} ({xs.length})</div>
            {xs.map(s => <button type="button" key={s.id} role="option" aria-selected={s.id === value} className={'pickrow' + (s.id === value ? ' on' : '')} onClick={() => pick(s.id)}>
              <span>{s.name}<small className="muted"> v{s.version}{s.origin === 'ai' ? ' · AI draft' : ''}</small></span>
              <small className="muted">{s.sport === 'any' ? 'Any sport' : s.sport} · {s.description || 'No description'}</small></button>)}</div>)}
          {loaded && !sections.length && <div className="muted small pad">{list.length ? 'No script matches. Clear the search or the sport filter.' : 'No scripts yet. Ask the Copilot to build one, or use Scripts.'}</div>}
        </div>
      </div>}
    </div>
  )
}
