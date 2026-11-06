import { useEffect, useState } from 'react'
import { api, type HealthItem } from './api'
import { SafetyForm } from './Safety'

const SECTIONS = ['Safety and limits', 'Live trading', 'Connections and feeds', 'Credentials', 'Trading defaults', 'AI and costs', 'Alerts', 'Versions and models', 'Appearance'] as const
type Section = typeof SECTIONS[number]
const ago = (v: unknown) => (typeof v === 'number' ? (() => { const s = Math.max(0, Math.round(Date.now() / 1000 - v)); return s < 90 ? `${s}s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago` })() : '–')

function Connections() {
  const [h, setH] = useState<{ items: HealthItem[]; issues: number } | null>(null), [pl, setPl] = useState<Record<string, unknown> | null>(null), [fb, setFb] = useState<Record<string, unknown> | null>(null), [tn, setTn] = useState<Record<string, unknown> | null>(null)
  useEffect(() => { api.health().then(setH).catch(() => undefined); api.pricelogStatus().then(setPl).catch(() => undefined); api.footballStatus().then(setFb).catch(() => undefined); api.tennisStatus().then(setTn).catch(() => undefined) }, [])
  const n = (v: unknown) => (typeof v === 'number' ? v.toLocaleString() : '–')
  return <>
    <h3>Connections and feeds</h3>
    <div className="card">{h?.items.map(i => <div key={i.key} className="hrow" style={{ padding: '6px 0' }}><span className={'hdot ' + i.level} aria-hidden /><div><b>{i.name}</b><div className="muted small">{i.detail}</div></div></div>) ?? <div className="muted small">Loading…</div>}</div>
    <div className="card tcard"><h3>What has been collected</h3><table className="tbl"><tbody>
      <tr><td>Football matches stored</td><td>{n(fb?.fixtures)} ({n(fb?.finished)} finished, {n(fb?.live_snapshots)} live score changes)</td></tr>
      <tr><td>Tennis matches stored</td><td>{n(tn?.matches)} ({n(tn?.live_snapshots)} live score changes)</td></tr>
      <tr><td>Betfair price log</td><td>{n(pl?.markets)} markets, {n(pl?.ticks)} price changes, last {ago(pl?.last)}</td></tr></tbody></table></div></>
}

function LiveTrading() {
  const [l, setL] = useState<Awaited<ReturnType<typeof api.live>> | null>(null), [phrase, setPhrase] = useState(''), [err, setErr] = useState('')
  const load = () => api.live().then(setL).catch(() => undefined)
  useEffect(() => { void load() }, [])
  const run = (f: () => Promise<unknown>) => { setErr(''); f().then(() => { setPhrase(''); void load() }).catch(e => setErr((e as Error).message)) }
  if (!l) return <div className="muted small">Loading…</div>
  if (!l.live) return <><h3>Live trading</h3><div className="card"><div className="small">Practice mode: real prices, simulated money. No order is ever sent to Betfair. Live trading is switched on in the server's configuration, not here, and then has to be armed on this page each time the service restarts.</div></div></>
  return <><h3>Live trading</h3><div className="card">
    <div className="row"><b className={l.armed ? 'loss' : 'muted'}>{l.armed ? 'ARMED: new orders are real Betfair orders' : 'NOT ARMED: no new orders will be sent'}</b></div>
    <div className="small muted">Betfair funds: {l.funds?.available != null ? `£${l.funds.available.toFixed(2)} available, £${(l.funds.exposure ?? 0).toFixed(2)} exposure` : 'not available'}. Orders {l.sync_error ? `NOT syncing: ${l.sync_error}` : 'are syncing with Betfair'}.</div>
    {l.armed ? <div className="row"><button className="danger" onClick={() => run(() => api.liveDisarm())}>Disarm (cancels still work)</button></div>
      : <><div className="small">Arming lets manual trading, scripts and the AI place real bets, subject to your limits. It resets whenever the service restarts. Type SEND-REAL-ORDERS to confirm.</div>
        <div className="row"><input value={phrase} onChange={e => setPhrase(e.target.value)} placeholder="SEND-REAL-ORDERS" aria-label="Confirmation phrase" /><button className="primary" disabled={phrase !== 'SEND-REAL-ORDERS'} onClick={() => run(() => api.liveArm(phrase))}>Arm live trading</button></div></>}
    {err && <div className="loss small">{err}</div>}</div></>
}

function Credentials() {
  const [c, setC] = useState<{ items: { name: string; set: boolean; detail: string }[]; where: string } | null>(null)
  useEffect(() => { api.credentials().then(setC).catch(() => undefined) }, [])
  return <><h3>Credentials</h3><div className="muted small">Server side only. Values are never shown or sent to this browser.</div>
    <div className="card tcard"><table className="tbl"><tbody>{c?.items.map(i => <tr key={i.name}><td><b>{i.name}</b><div className="muted small">{i.detail}</div></td><td className={i.set ? 'gain' : 'loss'}>{i.set ? 'Set' : 'Not set'}</td></tr>)}</tbody></table><div className="muted small">{c?.where}</div></div></>
}

function AiCosts() {
  const [s, setS] = useState<{ enabled: boolean; model: string; estimated_gbp: number; cap_gbp: number } | null>(null)
  useEffect(() => { api.aiStatus().then(x => setS(x as never)).catch(() => undefined) }, [])
  return <><h3>AI and costs</h3>
    <div className="card tcard"><table className="tbl"><tbody>
      <tr><td>Claude</td><td>{s ? (s.enabled ? 'Connected' : 'No key on the server') : '…'}</td></tr><tr><td>Model</td><td>{(s as { model?: string } | null)?.model ?? '–'}</td></tr>
      <tr><td>Spend this month (estimate)</td><td>£{s?.estimated_gbp?.toFixed(2) ?? '–'} of £{s?.cap_gbp ?? '–'} cap</td></tr></tbody></table>
      <div className="muted small">The estimate counts tokens at published prices. The caps and the AI mode are in Safety and limits. Set the same cap in the Anthropic Console as a hard backstop.</div></div></>
}

/** Settings: safety, connections, credentials, defaults, AI, alerts, versions, appearance. */
export default function SettingsScreen({ theme, onTheme, onLadderSettings }: { theme: string; onTheme: () => void; onLadderSettings: () => void }) {
  const [sec, setSec] = useState<Section>('Safety and limits')
  return (
    <div className="screen">
      <div className="row"><h1>Settings</h1></div>
      <div className="split">
        <aside className="card library" style={{ width: 220 }}>{SECTIONS.map(x => <button key={x} className={'librow' + (sec === x ? ' on' : '')} onClick={() => setSec(x)}>{x}</button>)}</aside>
        <section className="detail" style={{ maxWidth: 720 }}>
          {sec === 'Safety and limits' && <div className="card"><SafetyForm heading={false} /></div>}
          {sec === 'Live trading' && <LiveTrading />}
          {sec === 'Connections and feeds' && <Connections />}
          {sec === 'Credentials' && <Credentials />}
          {sec === 'Trading defaults' && <><h3>Trading defaults</h3><div className="card"><div className="small muted">Lay bet sizing and the optional confirmation threshold are in Safety and limits. Ladder layout, stake presets, keyboard shortcuts and the rest are in Ladder settings.</div><div className="row" style={{ marginTop: 8 }}><button onClick={onLadderSettings}>Open Ladder settings</button></div></div></>}
          {sec === 'AI and costs' && <AiCosts />}
          {sec === 'Alerts' && <><h3>Alerts</h3><div className="card"><label className="sw"><input type="checkbox" checked readOnly /> In the browser</label><label className="sw"><input type="checkbox" disabled /> Email for warnings and system <span className="muted small">(not set up yet)</span></label><label className="sw"><input type="checkbox" disabled /> Phone push <span className="muted small">(not set up yet)</span></label></div></>}
          {sec === 'Versions and models' && <><h3>Versions and models</h3><div className="card tcard"><table className="tbl"><tbody><tr><td>Tennis win-probability model</td><td>v3 (Elo blended with point-by-point v2), live version for in-play prices</td></tr><tr><td>Football goals model</td><td>Poisson with Dixon-Coles, tuned 2026-11 (half-life 450 days, shrinkage 6)</td></tr><tr><td>Exchange</td><td>Betfair, delayed application key, practice mode (orders are simulated)</td></tr></tbody></table><div className="muted small">Scripts keep their own version history on the Scripts screen.</div></div></>}
          {sec === 'Appearance' && <><h3>Appearance</h3><div className="card"><div className="row"><span className="small">Theme</span><button onClick={onTheme}>{theme === 'dark' ? 'Switch to light' : 'Switch to dark'}</button></div></div></>}
        </section>
      </div>
    </div>
  )
}
