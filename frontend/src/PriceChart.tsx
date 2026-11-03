import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { tickIndex } from './ticks'

type Pt = [number, number | null, number | null, number | null, number]
const RANGES: [string, number][] = [['5m', 300], ['15m', 900], ['1h', 3600], ['3h', 10800]]
const PAD_T = 6, PAD_B = 16

/** Price history for one runner: last traded price (line), best back / lay (band) and matched volume (bars).
 *  Prices are spaced by tick, as on Betfair's own chart. History starts when the market is first opened here. */
export default function PriceChart({ marketId, selectionId }: { marketId: string; selectionId: string }) {
  const [range, setRange] = useState(900)
  const [pts, setPts] = useState<Pt[]>([])
  const [err, setErr] = useState('')
  const box = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 300, h: 120 })
  useEffect(() => {
    const el = box.current; if (!el) return
    const ro = new ResizeObserver(() => setSize({ w: Math.max(120, el.clientWidth), h: Math.max(40, el.clientHeight) }))
    ro.observe(el); setSize({ w: Math.max(120, el.clientWidth), h: Math.max(40, el.clientHeight) })
    return () => ro.disconnect()
  }, [])
  const W = size.w, H = size.h, VOL_H = Math.round(H * 0.2)

  useEffect(() => {
    let live = true
    const load = () => api.history(marketId, selectionId, range).then(r => { if (live) { setPts(r.points); setErr('') } }).catch(e => { if (live) setErr(e.message) })
    load()
    const t = window.setInterval(load, 3000)
    return () => { live = false; window.clearInterval(t) }
  }, [marketId, selectionId, range])

  const line = pts.filter(p => p[1] != null)
  const idxs = pts.flatMap(p => [p[1], p[2], p[3]]).filter((x): x is number => x != null).map(tickIndex)
  let body: JSX.Element
  if (line.length < 2 || !idxs.length) {
    body = <text x={W / 2} y={H / 2} textAnchor="middle" className="chart-note">{err || 'Collecting prices… the chart fills in as you watch'}</text>
  } else {
    const lo = Math.min(...idxs) - 1, hi = Math.max(...idxs) + 1
    const t0 = pts[0][0], t1 = pts[pts.length - 1][0] || t0 + 1
    const x = (t: number) => ((t - t0) / Math.max(1, t1 - t0)) * (W - 38)
    const plotH = H - PAD_T - PAD_B - VOL_H
    const y = (price: number) => PAD_T + (1 - (tickIndex(price) - lo) / Math.max(1, hi - lo)) * plotH
    const maxVol = Math.max(1, ...pts.map(p => p[4]))
    const poly = (k: 1 | 2 | 3) => pts.filter(p => p[k] != null).map(p => `${x(p[0]).toFixed(1)},${y(p[k]!).toFixed(1)}`)
    const bk = poly(2), ly = poly(3)
    const band = bk.length && ly.length ? bk.join(' ') + ' ' + [...ly].reverse().join(' ') : ''
    const last = line[line.length - 1][1]!
    const top = pts.flatMap(p => [p[1], p[2], p[3]]).filter((v): v is number => v != null).reduce((a, v) => Math.max(a, v), 0)
    const bot = pts.flatMap(p => [p[1], p[2], p[3]]).filter((v): v is number => v != null).reduce((a, v) => Math.min(a, v), Infinity)
    const mins = Math.max(1, Math.round((t1 - t0) / 60))
    body = (<>
      {pts.map((p, i) => p[4] > 0 && <rect key={i} x={x(p[0]) - 1} width={2} y={H - PAD_B - (p[4] / maxVol) * VOL_H} height={(p[4] / maxVol) * VOL_H} className="chart-vol" />)}
      {band && <polygon points={band} className="chart-band" />}
      <polyline points={poly(1).join(' ')} className="chart-line" />
      <line x1={0} x2={W - 38} y1={y(last)} y2={y(last)} className="chart-last" />
      <text x={W - 36} y={y(last) + 3} className="chart-tag">{last.toFixed(2)}</text>
      <text x={W - 36} y={PAD_T + 8} className="chart-axis">{top.toFixed(2)}</text>
      <text x={W - 36} y={PAD_T + plotH} className="chart-axis">{bot.toFixed(2)}</text>
      <text x={0} y={H - 3} className="chart-axis">{mins < 60 ? `${mins} min` : `${(mins / 60).toFixed(1)} h`} shown</text>
    </>)
  }

  return (
    <div className="chart">
      <div className="chart-bar">
        <span className="muted small">Price · matched volume</span>
        <span className="spacer" />
        {RANGES.map(([l, s]) => <button key={l} className={'chipbtn tiny' + (range === s ? ' on' : '')} onClick={() => setRange(s)}>{l}</button>)}
      </div>
      <div className="chart-box" ref={box}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Price and matched volume chart">{body}</svg>
      </div>
    </div>
  )
}
