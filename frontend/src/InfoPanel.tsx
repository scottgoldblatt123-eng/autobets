import { useEffect, useState } from 'react'
import { api, type LogEntry, type MarketState } from './api'
import { matchedShare, money, weightOfMoney } from './maths'
import { marketFigure } from './MarketPanel'
import { tickIndex } from './ticks'

type Tab = 'pnl' | 'market' | 'runner' | 'depth' | 'log'
const TABS: [Tab, string][] = [['pnl', 'P&L all runners'], ['market', 'Market info'], ['runner', 'Runner info'], ['depth', 'Traded & available'], ['log', 'Log']]
const hhmmss = (t: number) => new Date(t * 1000).toLocaleTimeString('en-GB')
const pc = (x: number) => (x > 0.004 ? 'gain' : x < -0.004 ? 'loss' : 'muted')

interface Props { markets: Record<string, MarketState>; active: { marketId: string; selectionId: string } | null }

/** The reference panels from Bet Angel's bottom area: the whole book's P&L, market and runner details, depth, and the activity log. */
export default function InfoPanel({ markets, active }: Props) {
  const [open, setOpen] = useState(true)
  const [tab, setTab] = useState<Tab>('pnl')
  const [log, setLog] = useState<LogEntry[]>([])
  useEffect(() => {
    if (tab !== 'log' || !open) return
    let live = true
    const load = () => api.log(150).then(r => live && setLog([...r].reverse())).catch(() => undefined)
    load(); const t = window.setInterval(load, 3000)
    return () => { live = false; window.clearInterval(t) }
  }, [tab, open])

  const m = active ? markets[active.marketId] : undefined
  const sel = m && active ? m.selections[active.selectionId] : undefined
  const name = m && active ? m.runners[active.selectionId] ?? active.selectionId : ''

  let body: JSX.Element
  if (tab === 'pnl') {
    const ids = Object.keys(markets)
    body = !ids.length ? <div className="muted small pad">Open a market to see its P&L.</div> : (
      <table><thead><tr><th>Market</th><th>If this runner wins</th><th>Profit</th><th>Position</th></tr></thead>
        <tbody>{ids.flatMap(id => {
          const mk = markets[id], o = mk.outcomes
          const fig = marketFigure(mk)
          return [...Object.keys(mk.runners).map(sid => {
            const p = mk.positions[sid]
            return (<tr key={id + sid}><td className="muted small">{mk.event}</td><td>{mk.runners[sid]}</td>
              <td className={'num ' + pc(o?.[sid] ?? 0)}>{o ? money(o[sid] ?? 0) : '–'}</td>
              <td className="num small muted">{p && (Math.abs(p.win) > 0.004 || Math.abs(p.lose) > 0.004) ? `win ${money(p.win)} · lose ${money(p.lose)}` : 'none'}</td></tr>)
          }), <tr key={id + 'tot'} className="totrow"><td>{mk.event}</td><td><b>Market (worst case / green-up)</b></td><td className={'num ' + pc(fig ?? 0)}><b>{fig == null ? '–' : money(fig)}</b></td><td /></tr>]
        })}</tbody></table>)
  } else if (tab === 'market') {
    body = !m ? <div className="muted small pad">Hover a ladder to see its market.</div> : (() => {
      const sels = Object.values(m.selections)
      const matched = sels.reduce((a, s) => a + s.traded.reduce((b, x) => b + x[1], 0), 0)
      const bb = sels.reduce((a, s) => a + (s.backs[0] ? 1 / s.backs[0][0] : 0), 0), bl = sels.reduce((a, s) => a + (s.lays[0] ? 1 / s.lays[0][0] : 0), 0)
      const rows: [string, string][] = [['Event', m.event], ['Market', m.name], ['Competition', m.competition || '–'],
        ['Scheduled start', m.start ? new Date(m.start).toLocaleString('en-GB') : '–'], ['Status', `${m.status ?? 'OPEN'}${m.in_play ? ' · in play' : ' · pre-match'}`],
        ['Runners', Object.values(m.runners).join(' · ')], ['Matched in market', matched > 0 ? `£${matched.toLocaleString('en-GB', { maximumFractionDigits: 0 })}` : 'not available'],
        ['Back book', `${(bb * 100).toFixed(1)}%`], ['Lay book', `${(bl * 100).toFixed(1)}%`]]
      return <table><tbody>{rows.map(([k, v]) => <tr key={k}><td className="muted">{k}</td><td>{v}</td></tr>)}</tbody></table>
    })()
  } else if (tab === 'runner') {
    body = !m || !sel ? <div className="muted small pad">Hover a ladder to see its runner.</div> : (() => {
      const bb = sel.backs[0]?.[0], bl = sel.lays[0]?.[0]
      const spread = bb && bl ? tickIndex(bl) - tickIndex(bb) : null
      const share = matchedShare(sel.traded, Object.values(m.selections).map(s => s.traded))
      const wom = weightOfMoney(sel.backs, sel.lays, 3), p = m.positions[active!.selectionId]
      const rows: [string, string][] = [['Runner', name], ['Status', sel.status ?? 'ACTIVE'], ['Last traded', sel.last?.toFixed(2) ?? '–'],
        ['Best back / lay', `${bb?.toFixed(2) ?? '–'} / ${bl?.toFixed(2) ?? '–'}`], ['Spread', spread == null ? '–' : `${spread} tick${spread === 1 ? '' : 's'}`],
        ['Matched', sel.traded.length ? `£${share.volume.toLocaleString('en-GB')} (${share.pct.toFixed(1)}% of the market)` : 'not available'],
        ['Weight of money (best 3)', wom ? `${wom.back}% back · ${wom.lay}% lay` : '–'],
        ['Your position', p && (Math.abs(p.win) > 0.004 || Math.abs(p.lose) > 0.004) ? `if it wins ${money(p.win)} · if it loses ${money(p.lose)}` : 'none']]
      return <table><tbody>{rows.map(([k, v]) => <tr key={k}><td className="muted">{k}</td><td>{v}</td></tr>)}</tbody></table>
    })()
  } else if (tab === 'depth') {
    body = !m || !sel ? <div className="muted small pad">Hover a ladder to see its depth.</div> : (() => {
      const back = new Map(sel.backs), lay = new Map(sel.lays), tr = new Map(sel.traded)
      const prices = Array.from(new Set([...back.keys(), ...lay.keys(), ...tr.keys()])).sort((a, b) => b - a)
      return <table><thead><tr><th>Price</th><th>Available to back</th><th>Available to lay</th><th>Traded</th></tr></thead>
        <tbody>{prices.map(pr => <tr key={pr}><td className="num"><b>{pr.toFixed(2)}</b></td>
          <td className="num">{back.has(pr) ? '£' + back.get(pr)!.toFixed(0) : ''}</td><td className="num">{lay.has(pr) ? '£' + lay.get(pr)!.toFixed(0) : ''}</td>
          <td className="num">{tr.has(pr) ? '£' + tr.get(pr)!.toFixed(0) : ''}</td></tr>)}</tbody></table>
    })()
  } else {
    body = !log.length ? <div className="muted small pad">Nothing logged yet.</div> : (
      <table><thead><tr><th>Time</th><th>Type</th><th>What happened</th></tr></thead>
        <tbody>{log.map((e, i) => <tr key={i}><td className="num">{hhmmss(e.t)}</td><td className="muted">{e.kind}</td><td>{e.text}</td></tr>)}</tbody></table>)
  }

  return (
    <div className={'opanel infopanel' + (open ? '' : ' shut')}>
      <div className="ohead">
        <button className="icon" onClick={() => setOpen(o => !o)} title={open ? 'Hide' : 'Show'}>{open ? '▾' : '▸'}</button>
        {TABS.map(([k, l]) => <button key={k} className={'chipbtn tiny' + (tab === k ? ' on' : '')} onClick={() => { setTab(k); setOpen(true) }}>{l}</button>)}
        {(tab === 'runner' || tab === 'depth') && name && <span className="muted small">{name}</span>}
      </div>
      {open && <div className="obody">{body}</div>}
    </div>
  )
}
