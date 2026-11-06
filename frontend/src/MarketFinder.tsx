import { useEffect, useMemo, useState } from 'react'
import { api, type MarketInfo } from './api'
import { groupMarkets } from './markets'
import DayPicker from './DayPicker'

type Say = (text: string, kind?: 'ok' | 'warn' | 'err') => void
interface Props {
  say: Say
  /** 'select': tick boxes and a bulk "Add to Plan" bar. 'pick': one click chooses a market. */
  mode: 'select' | 'pick'
  onPick?: (m: MarketInfo) => void
  onAddToPlan?: (ms: MarketInfo[]) => void
  onOpenLadder?: (m: MarketInfo) => void
  planned?: Set<string>
  /** Change this number to clear the tick boxes (after a bulk add). */
  clearKey?: number
}

/** The market list used outside Manual Trading: same search, filters, grouping and "all markets on this event" as the ladder screen,
 *  plus tick boxes (also per competition) so many markets can be added to the Plan at once. Selection survives tab and search changes. */
export default function MarketFinder({ say, mode, onPick, onAddToPlan, onOpenLadder, planned, clearKey }: Props) {
  const [sport, setSport] = useState<'tennis' | 'football'>('tennis'), [markets, setMarkets] = useState<MarketInfo[]>([]), [loading, setLoading] = useState(true), [day, setDay] = useState('')
  const [q, setQ] = useState(''), [fIn, setFIn] = useState(false), [fSoon, setFSoon] = useState(false), [byName, setByName] = useState(false)
  const [folded, setFolded] = useState<Record<string, boolean>>({}), [expanded, setExpanded] = useState<Record<string, MarketInfo[] | 'loading'>>({})
  const [sel, setSel] = useState<Map<string, MarketInfo>>(new Map())
  useEffect(() => {
    setLoading(true); setMarkets([])
    const go = () => api.markets(sport, day).then(m => { setMarkets(m); setLoading(false) }).catch(e => { setLoading(false); say((e as Error).message, 'err') })
    void go(); const t = window.setInterval(() => void go(), 60000); return () => window.clearInterval(t)
  }, [sport, day, say])
  useEffect(() => { setSel(new Map()) }, [clearKey])
  const toggleEvent = (eventId: string) => {
    if (expanded[eventId]) return setExpanded(o => { const n = { ...o }; delete n[eventId]; return n })
    setExpanded(o => ({ ...o, [eventId]: 'loading' }))
    api.eventMarkets(eventId).then(ms => setExpanded(o => ({ ...o, [eventId]: ms }))).catch(e => { say((e as Error).message, 'err'); setExpanded(o => { const n = { ...o }; delete n[eventId]; return n }) })
  }
  const tick = (ms: MarketInfo[], on: boolean) => setSel(s => { const n = new Map(s); for (const m of ms) on ? n.set(m.market_id, m) : n.delete(m.market_id); return n })
  const list = useMemo(() => {
    const needle = q.trim().toLowerCase(), now = Date.now()
    return markets.filter(m => {
      if (needle && !`${m.event} ${m.competition} ${m.name} ${Object.values(m.runners).join(' ')}`.toLowerCase().includes(needle)) return false
      if (fIn && !m.in_play) return false
      if (fSoon && !(m.start && new Date(m.start).getTime() - now < 3600_000)) return false
      return true
    }).sort((a, b) => (byName ? a.event.localeCompare(b.event) : (a.start ?? '').localeCompare(b.start ?? '')))
  }, [markets, q, fIn, fSoon, byName])
  const groups = useMemo(() => { const g = new Map<string, MarketInfo[]>(); for (const m of list) g.set(m.competition || 'Other', [...(g.get(m.competition || 'Other') ?? []), m]); return Array.from(g.entries()) }, [list])
  const row = (m: MarketInfo, sub: string, cls: string) => {
    const on = sel.has(m.market_id), inPlan = planned?.has(m.market_id)
    return <div className="mrowx" key={m.market_id}>
      {mode === 'select' && <label className="mcheck" title="Select for Plan"><input type="checkbox" checked={on} onChange={e => tick([m], e.target.checked)} aria-label={`Select ${m.event} ${m.name}`} /></label>}
      <button className={cls + (on ? ' open' : '')} onClick={() => (mode === 'pick' ? onPick?.(m) : tick([m], !on))}>
        <span>{m.in_play && <b className="livedot" title="In play" />}{m.event}{inPlan && <em className="inplan">in Plan</em>}</span><small className="muted">{sub}</small></button>
      {mode === 'select' && onOpenLadder && <button className="mexp" title="Open the ladder" onClick={() => onOpenLadder(m)}>▦</button>}
    </div>
  }
  return (
    <aside className="finderpanel">
      <div className="tabs">{(['tennis', 'football'] as const).map(s => <button key={s} className={sport === s ? 'on' : ''} onClick={() => setSport(s)}>{s === 'tennis' ? 'Tennis' : 'Football'}</button>)}</div>
      <DayPicker value={day} onChange={setDay} />
      <div className="msearch">
        <input type="search" placeholder="Search players, teams, competitions…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search markets" />
        <div className="chips">
          <button className={'chip' + (fIn ? ' on' : '')} onClick={() => setFIn(v => !v)}>In-play</button>
          <button className={'chip' + (fSoon ? ' on' : '')} onClick={() => setFSoon(v => !v)}>Next hour</button>
          <button className="chip" onClick={() => setByName(v => !v)} title="Sort order">{byName ? 'By name' : 'By start'}</button>
          {mode === 'select' && <button className="chip" onClick={() => tick(list, true)} title="Tick every market shown (after search and filters)">Select all shown</button>}
        </div>
      </div>
      <div className="finder">
        {loading && <div className="muted pad">Loading markets…</div>}
        {!loading && !markets.length && <div className="muted pad">No markets found</div>}
        {!loading && markets.length > 0 && !list.length && <div className="muted pad">Nothing matches. Clear the search or a filter.</div>}
        {groups.map(([comp, ms]) => {
          const all = ms.every(m => sel.has(m.market_id))
          return <div key={comp} className="mgroup">
            <div className="mgroup-row">
              {mode === 'select' && <label className="mcheck" title="Select this whole competition"><input type="checkbox" checked={all} onChange={e => tick(ms, e.target.checked)} aria-label={`Select all in ${comp}`} /></label>}
              <button className="mgroup-h" onClick={() => setFolded(o => ({ ...o, [comp]: !o[comp] }))}><span>{folded[comp] ? '▸' : '▾'} {comp}</span><i>{ms.length}</i></button>
            </div>
            {!folded[comp] && ms.map(m => <div key={m.market_id} className="mwrap">
              {row(m, `${m.name}${m.start ? ' · ' + new Date(m.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}`, 'market')}
              {m.event_id && <button className="mmore" onClick={() => toggleEvent(m.event_id!)}>{expanded[m.event_id] ? '▾ Hide other markets' : '＋ All markets on this event'}</button>}
              {m.event_id && expanded[m.event_id] === 'loading' && <div className="muted small pad">Loading markets…</div>}
              {m.event_id && Array.isArray(expanded[m.event_id]) && groupMarkets(expanded[m.event_id] as MarketInfo[], m.event).map(([label, xs]) => <div key={label} className="mxgroup">
                <div className="mxh">{label}</div>
                {xs.map(x => row({ ...x, event: x.event || m.event, competition: x.competition || m.competition }, `${x.name} · ${Object.keys(x.runners).length} runners`, 'market mx2'))}
              </div>)}
            </div>)}
          </div>
        })}
      </div>
      {mode === 'select' && <div className="bulkbar">
        <span>{sel.size} selected</span><span className="spacer" />
        {sel.size > 0 && <button className="sm" onClick={() => setSel(new Map())}>Clear</button>}
        <button className="primary sm" disabled={!sel.size} onClick={() => onAddToPlan?.(Array.from(sel.values()))}>Add {sel.size || ''} to Plan</button>
      </div>}
    </aside>
  )
}
