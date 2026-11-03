import { useCallback, useEffect, useRef, useState } from 'react'
import { api, setToken, type MarketInfo, type State } from './api'
import MarketPanel from './MarketPanel'
import Ladder from './Ladder'
import { hedge, money, orderSize, parseStake, type Side } from './maths'
import { move } from './ticks'

interface LadderRef { marketId: string; selectionId: string }
interface Settings { autoCentre: boolean; ticksShown: number; presets: number[]; stakeIdx: number; layBasis: 'stake' | 'liability'; confirmAbove: number; stakeText: string; womLevels: number; showChart: boolean }
interface Pending { marketId: string; selectionId: string; side: Side; price: number; size: number; runner: string }

const DEFAULTS: Settings = { autoCentre: false, ticksShown: 10, presets: [2, 5, 10, 20], stakeIdx: 1, layBasis: 'stake', confirmAbove: 50, stakeText: '', womLevels: 3, showChart: true }
const keyOf = (l: LadderRef) => `${l.marketId}:${l.selectionId}`
const MAX_LADDERS = 4
const PRESET_OFF = { stakeText: '' }

function loadSettings(): Settings {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem('autobets.settings') ?? '{}') } } catch { return DEFAULTS }
}

export default function App() {
  const [ready, setReady] = useState<'checking' | 'token' | 'ok' | 'error'>('checking')
  const [bootError, setBootError] = useState('')
  const [tokenInput, setTokenInput] = useState('')
  const [mode, setMode] = useState('')
  const [sport, setSport] = useState<'tennis' | 'football'>('tennis')
  const [markets, setMarkets] = useState<MarketInfo[]>([])
  const [ladders, setLadders] = useState<LadderRef[]>([])
  const [centres, setCentres] = useState<Record<string, number | null>>({})
  const [state, setState] = useState<State | null>(null)
  const [settings, setSettings] = useState<Settings>(loadSettings)
  const [showSettings, setShowSettings] = useState(false)
  const [active, setActive] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [menu, setMenu] = useState<{ l: LadderRef; price: number; x: number; y: number } | null>(null)
  const seenEvt = useRef(Date.now() / 1000)
  const [toast, setToast] = useState<{ text: string; kind: 'ok' | 'warn' | 'err' } | null>(null)
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const inFlight = useRef(false)

  const say = useCallback((text: string, kind: 'ok' | 'warn' | 'err' = 'ok') => {
    setToast({ text, kind })
    window.setTimeout(() => setToast(t => (t && t.text === text ? null : t)), 4000)
  }, [])

  useEffect(() => { document.documentElement.dataset.theme = theme }, [theme])
  useEffect(() => { try { localStorage.setItem('autobets.settings', JSON.stringify(settings)) } catch { /* ignore */ } }, [settings])

  const boot = useCallback(async () => {
    try {
      const p = await api.ping()
      setMode(p.mode)
      if (!p.needs_token) return setReady('ok')
      await api.mode()                        // authenticated, no exchange call: 401 means the token is missing or wrong
      setReady('ok')
    } catch (e) {
      if ((e as { status?: number }).status === 401) { setReady('token'); return }
      setBootError((e as Error).message || 'Cannot reach the server')
      setReady('error')
    }
  }, [say])
  useEffect(() => { boot() }, [boot])

  useEffect(() => {
    if (ready !== 'ok') return
    api.markets(sport).then(setMarkets).catch(e => { setMarkets([]); say(e.message, 'err') })
  }, [ready, sport, say])

  const ids = Array.from(new Set(ladders.map(l => l.marketId)))
  const refresh = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try { setState(await api.state(ids)) } catch (e) { say((e as Error).message, 'err') } finally { inFlight.current = false }
  }, [ids.join(','), say])                       // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (ready !== 'ok') return
    refresh()
    const t = window.setInterval(refresh, ids.length ? 1000 : 3000)
    return () => window.clearInterval(t)
  }, [ready, refresh, ids.length])

  useEffect(() => {
    for (const e of state?.events ?? []) if (e.t > seenEvt.current) { seenEvt.current = e.t; say(e.text, e.text.includes('FAILED') ? 'err' : 'ok') }
  }, [state, say])

  const typed = parseStake(settings.stakeText)
  const stakeInvalid = settings.stakeText.trim() !== '' && typed == null
  const stake = typed ?? settings.presets[settings.stakeIdx] ?? settings.presets[0]
  const stakeBox = useRef<HTMLInputElement>(null)

  const submit = useCallback(async (p: Pending) => {
    try {
      const r = await api.place({ market_id: p.marketId, selection_id: p.selectionId, side: p.side, price: p.price, size: p.size })
      const o = r.order
      const text = `${p.runner}: ${p.side} £${p.size.toFixed(2)} @ ${p.price.toFixed(2)} — ${o.status === 'MATCHED' ? 'matched' : o.status === 'PARTIAL' ? `part matched £${o.matched.toFixed(2)}` : o.status === 'UNMATCHED' ? 'waiting (unmatched)' : o.status.toLowerCase()}`
      say(text, o.status === 'REJECTED' ? 'err' : r.warnings.length ? 'warn' : 'ok')
      if (r.warnings.length) say(r.warnings[0], 'warn')
      refresh()
    } catch (e) { say((e as Error).message, 'err') }
  }, [refresh, say])

  const click = (l: LadderRef, side: Side, price: number) => {
    const m = state?.markets[l.marketId]
    if (stakeInvalid) return say('The stake box needs an amount of £1 or more (or clear it to use a preset)', 'err')
    const size = orderSize(side, price, stake, settings.layBasis)
    if (size < 1) return say('Minimum stake is £1', 'err')
    const p: Pending = { marketId: l.marketId, selectionId: l.selectionId, side, price, size, runner: m?.runners[l.selectionId] ?? l.selectionId }
    if (settings.confirmAbove > 0 && size >= settings.confirmAbove) setPending(p)
    else submit(p)
  }

  const hedgeAt = (l: LadderRef, price: number) => {
    const m = state?.markets[l.marketId]
    const pos = m?.positions[l.selectionId]
    const h = pos ? hedge(pos, price) : null
    if (!h) return say('Position is already level', 'warn')
    if (h.stake < 1) return say('Hedge would be under the £1 minimum stake', 'warn')
    const p: Pending = { marketId: l.marketId, selectionId: l.selectionId, side: h.side, price, size: h.stake, runner: m?.runners[l.selectionId] ?? l.selectionId }
    if (settings.confirmAbove > 0 && h.stake >= settings.confirmAbove) setPending(p)
    else submit(p)
  }
  const addTrigger = async (l: LadderRef, price: number) => {
    setMenu(null)
    try {
      const t = await api.addTrigger({ market_id: l.marketId, selection_id: l.selectionId, price })
      say(`${t.label === 'stop loss' ? 'Stop loss' : 'Take profit'} set: greens up when the price reaches ${price.toFixed(2)} (locks ${money(t.locked)})`)
      refresh()
    } catch (e) { say((e as Error).message, 'err') }
  }
  const greenMarket = async (marketId: string, hard: boolean) => {
    const r = await api.green(marketId, hard).catch(e => { say(e.message, 'err'); return null })
    if (r) say(r.greened ? `${hard ? 'Hard close' : 'Green up'} done — locked ${money(r.locked ?? 0)}${r.level ? '' : ' (not fully level)'}${r.cancelled ? `, cancelled ${r.cancelled}` : ''}` : (r.cancelled ? `Cancelled ${r.cancelled}; ` : '') + (r.reason ?? 'nothing to do'), r.greened ? 'ok' : 'warn')
    refresh()
  }

  const cancelAt = async (l: LadderRef, price: number) => {
    const trg = state?.triggers.filter(t => t.market_id === l.marketId && t.selection_id === l.selectionId && t.price === price) ?? []
    await Promise.all(trg.map(t => api.delTrigger(t.id).catch(e => say(e.message, 'err'))))
    const here = state?.orders.filter(o => o.market_id === l.marketId && o.selection_id === l.selectionId && o.price === price) ?? []
    await Promise.all(here.map(o => api.cancel(o.order_id).catch(e => say(e.message, 'err'))))
    refresh()
  }
  const cancelAll = async (l: LadderRef, side?: Side) => {
    const r = await api.cancelAll(l.marketId, l.selectionId, side).catch(e => { say(e.message, 'err'); return null })
    if (r) say(r.cancelled ? `Cancelled ${r.cancelled}` : 'Nothing to cancel', r.cancelled ? 'ok' : 'warn')
    refresh()
  }
  const closePos = async (l: LadderRef) => {
    const r = await api.close(l.marketId, l.selectionId).catch(e => { say(e.message, 'err'); return null })
    if (r) say(r.closed ? `Closed — locked ${money(r.locked_profit ?? 0)}` : r.reason ?? 'Nothing to close', r.closed ? 'ok' : 'warn')
    refresh()
  }

  const openMarket = (m: MarketInfo) => {
    const want = Object.keys(m.runners).map(selectionId => ({ marketId: m.market_id, selectionId }))
    setLadders(cur => {
      const fresh = want.filter(w => !cur.some(c => keyOf(c) === keyOf(w)))
      const room = MAX_LADDERS - cur.length
      if (fresh.length > room) say(`Only ${room} ladder slot${room === 1 ? '' : 's'} free — close one to open more`, 'warn')
      return [...cur, ...fresh.slice(0, Math.max(0, room))]
    })
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const l = ladders.find(x => keyOf(x) === active)
      if (e.key === 'Escape') { setPending(null); setShowSettings(false); setMenu(null) }
      else if (e.key === 'Enter') setCentres({})
      else if (['1', '2', '3', '4'].includes(e.key)) setSettings(s => (Number(e.key) - 1 < s.presets.length ? { ...s, stakeIdx: Number(e.key) - 1, ...PRESET_OFF } : s))
      else if (e.key.toLowerCase() === 's') { e.preventDefault(); stakeBox.current?.focus(); stakeBox.current?.select() }
      else if (l && e.key.toLowerCase() === 'z') cancelAll(l, 'BACK')
      else if (l && e.key.toLowerCase() === 'x') cancelAll(l, 'LAY')
      else if (l && e.key.toLowerCase() === 'c') closePos(l)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (ready === 'checking') return <div className="center muted">Connecting…</div>
  if (ready === 'error') return (
    <div className="center"><div className="card"><h3>Cannot start</h3><p className="loss">{bootError}</p>
      <div className="row"><button className="primary" onClick={() => { setReady('checking'); boot() }}>Try again</button></div></div></div>
  )
  if (ready === 'token') return (
    <div className="center">
      <form className="card" onSubmit={e => { e.preventDefault(); setToken(tokenInput); setReady('checking'); boot() }}>
        <h2>AutoBets</h2>
        <p className="muted">Enter your access token</p>
        <input type="password" autoFocus value={tokenInput} onChange={e => setTokenInput(e.target.value)} />
        <button className="primary" type="submit">Sign in</button>
      </form>
    </div>
  )

  const tot = state?.totals
  return (
    <div className="app">
      <header>
        <b className="logo">AutoBets</b>
        <span className="badge">{mode === 'practice' ? 'PRACTICE MODE' : mode === 'demo' ? 'DEMO — FAKE PRICES' : mode.toUpperCase()}</span>
        <span className="spacer" />
        <span className="stat">Exposure <b>£{(tot?.exposure ?? 0).toFixed(2)}</b></span>
        <button className="sm" onClick={() => setShowSettings(true)}>Ladder settings</button>
        <button className="sm" onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}>{theme === 'dark' ? 'Light' : 'Dark'}</button>
      </header>

      <div className="body">
        <aside>
          <div className="tabs">
            {(['tennis', 'football'] as const).map(s => <button key={s} className={sport === s ? 'on' : ''} onClick={() => setSport(s)}>{s === 'tennis' ? 'Tennis' : 'Football'}</button>)}
          </div>
          <div className="finder">
            {markets.length === 0 && <div className="muted pad">No markets found</div>}
            {markets.map(m => (
              <button key={m.market_id} className="market" onClick={() => openMarket(m)}>
                <span>{m.event}</span>
                <small className="muted">{m.competition} · {m.name}{m.start ? ' · ' + new Date(m.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</small>
              </button>
            ))}
          </div>
        </aside>

        <main>
          <div className="toolbar">
            <span className="muted">Stake £</span>
            {settings.presets.map((v, i) => (
              <button key={i} className={'chipbtn' + (i === settings.stakeIdx && typed == null ? ' on' : '')} onClick={() => setSettings(s => ({ ...s, stakeIdx: i, ...PRESET_OFF }))} title={`Key ${i + 1}`}>{v}</button>
            ))}
            <span className="stakebox" title="Type any stake, e.g. 65 (press S to jump here, Enter to finish). Clear it to go back to the presets.">
              <span className="muted">£</span>
              <input ref={stakeBox} inputMode="decimal" placeholder="any" className={(typed != null ? 'on' : '') + (stakeInvalid ? ' bad' : '')}
                     value={settings.stakeText} onChange={e => setSettings(s => ({ ...s, stakeText: e.target.value }))}
                     onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') (e.target as HTMLInputElement).blur() }} />
            </span>
            {stakeInvalid && <span className="loss small">min £1</span>}
            <span className="sep" />
            <span className="muted">Lay by</span>
            {(['stake', 'liability'] as const).map(b => <button key={b} className={'chipbtn' + (settings.layBasis === b ? ' on' : '')} onClick={() => setSettings(s => ({ ...s, layBasis: b }))}>{b === 'stake' ? 'Stake' : 'Liability'}</button>)}
            <span className="spacer" />
            <span className="muted small">S stake box · Hover a ladder · Z cancel back · X cancel lay · C close · Enter recentre · wheel scrolls</span>
          </div>
          {ids.map(id => state?.markets[id] && <MarketPanel key={id} marketId={id} market={state.markets[id]} onGreen={h => greenMarket(id, h)} />)}
          {ladders.length === 0 && <div className="empty muted">Pick a market on the left to open its ladders (up to {MAX_LADDERS}).</div>}
          <div className="ladders" style={{ gridTemplateColumns: `repeat(${Math.max(1, ladders.length)}, minmax(290px, 1fr))` }}>
            {ladders.map(l => {
              const k = keyOf(l), m = state?.markets[l.marketId]
              if (!m) return <div key={k} className="ladder"><div className="ladder-head muted">Loading…</div></div>
              return (
                <Ladder key={k} market={m} marketId={l.marketId} selectionId={l.selectionId}
                  orders={(state?.orders ?? []).filter(o => o.market_id === l.marketId)} ticksShown={settings.ticksShown} womLevels={settings.womLevels} showChart={settings.showChart}
                  centre={centres[k] ?? null} autoCentre={settings.autoCentre} active={active === k}
                  onSetCentre={c => setCentres(o => ({ ...o, [k]: c }))}
                  triggers={(state?.triggers ?? []).filter(t => t.market_id === l.marketId && t.selection_id === l.selectionId)}
                  onHedge={price => hedgeAt(l, price)} onContext={(price, x, y) => setMenu({ l, price, x, y })}
                  onClick={(side, price) => click(l, side, price)} onCancelAt={price => cancelAt(l, price)}
                  onWheel={d => setCentres(o => (o[k] == null ? o : { ...o, [k]: move(o[k]!, d) }))} onHover={() => setActive(k)}
                  onCancelAll={() => cancelAll(l)} onClose={() => closePos(l)}
                  onRemove={() => setLadders(cur => cur.filter(x => keyOf(x) !== k))}
                  onRecentre={() => setCentres(o => ({ ...o, [k]: null }))} />
              )
            })}
          </div>
        </main>
      </div>

      {pending && (
        <div className="overlay" onClick={() => setPending(null)}>
          <div className="card" onClick={e => e.stopPropagation()}>
            <h3>Confirm order</h3>
            <p><b>{pending.side}</b> {pending.runner}<br />£{pending.size.toFixed(2)} at {pending.price.toFixed(2)}
              {pending.side === 'LAY' && <span className="muted"> (liability £{(pending.size * (pending.price - 1)).toFixed(2)})</span>}</p>
            <div className="row">
              <button className="primary" autoFocus onClick={() => { const p = pending; setPending(null); submit(p) }}>Place</button>
              <button onClick={() => setPending(null)}>Cancel (Esc)</button>
            </div>
          </div>
        </div>
      )}

      {showSettings && (
        <div className="overlay" onClick={() => setShowSettings(false)}>
          <div className="card wide" onClick={e => e.stopPropagation()}>
            <h3>Ladder settings</h3>
            <label className="check"><input type="checkbox" checked={settings.autoCentre} onChange={e => setSettings(s => ({ ...s, autoCentre: e.target.checked }))} />
              Auto-recentre on the price (off: the ladder stays put until you press Enter or ⌖)</label>
            <label>Ticks shown each side of the price
              <input type="number" min={4} max={30} value={settings.ticksShown} onChange={e => setSettings(s => ({ ...s, ticksShown: Math.max(4, Math.min(30, Number(e.target.value) || 10)) }))} />
            </label>
            <label className="check"><input type="checkbox" checked={settings.showChart} onChange={e => setSettings(s => ({ ...s, showChart: e.target.checked }))} />
              Show the price chart under each ladder</label>
            <label>Weight of money: prices counted each side of the book
              <input type="number" min={1} max={10} value={settings.womLevels} onChange={e => setSettings(s => ({ ...s, womLevels: Math.max(1, Math.min(10, Number(e.target.value) || 3)) }))} />
            </label>
            <label>Stake presets £ (comma separated, up to 4)
              <input defaultValue={settings.presets.join(', ')} onBlur={e => {
                const v = e.target.value.split(',').map(x => Number(x.trim())).filter(x => x >= 1).slice(0, 4)
                if (v.length) setSettings(s => ({ ...s, presets: v, stakeIdx: Math.min(s.stakeIdx, v.length - 1) }))
              }} />
            </label>
            <label>Ask me to confirm orders of £… or more (0 = never)
              <input type="number" min={0} value={settings.confirmAbove} onChange={e => setSettings(s => ({ ...s, confirmAbove: Math.max(0, Number(e.target.value) || 0) }))} />
            </label>
            <div className="row"><button className="primary" onClick={() => setShowSettings(false)}>Done</button></div>
          </div>
        </div>
      )}

      {menu && (() => {
        const m = state?.markets[menu.l.marketId], pos = m?.positions[menu.l.selectionId]
        const h = pos ? hedge(pos, menu.price) : null
        const runner = m?.runners[menu.l.selectionId] ?? ''
        const here = (state?.triggers ?? []).filter(t => t.market_id === menu.l.marketId && t.selection_id === menu.l.selectionId && t.price === menu.price)
        return (
          <div className="overlay clear" onClick={() => setMenu(null)} onContextMenu={e => { e.preventDefault(); setMenu(null) }}>
            <div className="menu" style={{ left: Math.min(menu.x, window.innerWidth - 290), top: Math.min(menu.y, window.innerHeight - 140) }} onClick={e => e.stopPropagation()}>
              <div className="muted small">{runner} · {menu.price.toFixed(2)}</div>
              {h
                ? <button onClick={() => addTrigger(menu.l, menu.price)}>{h.locked >= 0 ? 'Take profit' : 'Stop loss'}: green up when price reaches {menu.price.toFixed(2)} <b className={h.locked >= 0 ? 'gain' : 'loss'}>({money(h.locked)})</b></button>
                : <div className="muted small pad">{pos ? 'Position is level — nothing to protect' : 'No position on this selection'}</div>}
              {here.length > 0 && <button onClick={async () => { await Promise.all(here.map(t => api.delTrigger(t.id))); setMenu(null); refresh() }}>Remove stop / take profit here</button>}
            </div>
          </div>
        )
      })()}

      {toast && <div className={'toast ' + toast.kind} role="status">{toast.text}</div>}
    </div>
  )
}
