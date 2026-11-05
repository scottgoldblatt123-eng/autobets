import { useCallback, useEffect, useRef, useState } from 'react'
import { groupMarkets } from './markets'
import { api, setToken, type MarketInfo, type MatchCtx, type State } from './api'
import Copilot from './Copilot'
import { SafetyPanel, StatusStrip } from './Safety'
import ScriptsScreen from './ScriptsScreen'
import PlanScreen from './PlanScreen'
import RecsScreen from './RecsScreen'
import AlertsScreen from './AlertsScreen'
import HealthBadge from './Health'
import HomeScreen from './HomeScreen'
import AnalyseScreen from './AnalyseScreen'
import SettingsScreen from './SettingsScreen'
import AttachDialog from './AttachDialog'
import Workbench from './Workbench'
import MarketHeader, { marketFigure } from './MarketPanel'
import OrdersPanel from './OrdersPanel'
import MatchedPanel from './MatchedPanel'
import InfoPanel from './InfoPanel'
import TradePanel from './TradePanel'
import Ladder from './Ladder'
import { hedge, money, orderSize, parseStake, type Side } from './maths'
import { move } from './ticks'

interface LadderRef { marketId: string; selectionId: string }
interface Settings { autoCentre: boolean; rows: number; presets: number[]; stakeIdx: number; layBasis: 'stake' | 'liability'; confirmAbove: number; stakeText: string; womLevels: number; showChart: boolean; showTotal: boolean; theme: 'dark' | 'light'; pnlSide: 'left' | 'right'; pnlBasis: 'runner' | 'market'; reverse: boolean; persistence: 'KEEP' | 'CANCEL' | 'TAKE_SP'; fokS: number; offsetTicks: number; stopTicks: number; stakeMode: 'fixed' | 'pct'; bank: number; sepLay: boolean; layText: string; clickMode: 'single' | 'double'; keys: Record<string, string>; shortS: number; longS: number }
interface Pending { marketId: string; selectionId: string; side: Side; price: number; size: number; runner: string; entry?: boolean }

const KEYS: Record<string, string> = { stakeBox: 's', cancelBack: 'z', cancelLay: 'x', closeRunner: 'c', hardClose: 'g', reverse: 'r', recentre: 'Enter' }
const DEFAULTS: Settings = { autoCentre: false, rows: 25, presets: [2, 5, 10, 20], stakeIdx: 1, layBasis: 'stake', confirmAbove: 50, stakeText: '', womLevels: 3, showChart: true, showTotal: false, theme: 'light', pnlSide: 'left', pnlBasis: 'runner', reverse: false, persistence: 'CANCEL', fokS: 0, offsetTicks: 0, stopTicks: 0, stakeMode: 'fixed', bank: 1000, sepLay: false, layText: '', clickMode: 'single', keys: KEYS, shortS: 60, longS: 300 }
const KEY_LABELS: Record<string, string> = { stakeBox: 'Jump to the stake box', cancelBack: 'Cancel back bets (hovered ladder)', cancelLay: 'Cancel lay bets (hovered ladder)', closeRunner: 'Close the hovered runner', hardClose: 'Hard close the market', reverse: 'Reverse the ladders', recentre: 'Recentre all ladders' }
const keyName = (k: string) => (k.length === 1 ? k.toUpperCase() : k)
export function resolveStakeText(t: string, bank: number, mode: 'fixed' | 'pct'): number | null {
  const s = t.replace(/[£,\s]/g, '')
  const pct = /^\d+(\.\d+)?%$/.test(s) ? Number(s.slice(0, -1)) : mode === 'pct' && /^\d+(\.\d+)?$/.test(s) ? Number(s) : null
  if (pct != null) { const v = Math.round(bank * pct) / 100; return v >= 1 ? v : null }
  return parseStake(t)
}
const keyOf = (l: LadderRef) => `${l.marketId}:${l.selectionId}`
const MAX_LADDERS = 4
const PRESET_OFF = { stakeText: '' }

type Status = Record<string, unknown> | null
const ago = (iso: unknown) => { if (typeof iso !== 'string') return 'never'; const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000)); return s < 90 ? `${s}s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago` }
const num = (v: unknown) => (typeof v === 'number' ? v.toLocaleString() : '–')

/** Football and tennis data collection at a glance, so nobody needs the server to see whether it is working. */
function DataStatus({ onClose }: { onClose: () => void }) {
  const [fb, setFb] = useState<Status>(null), [tn, setTn] = useState<Status>(null), [pl, setPl] = useState<Status>(null), [err, setErr] = useState('')
  useEffect(() => {
    let dead = false
    const go = () => Promise.all([api.footballStatus(), api.tennisStatus(), api.pricelogStatus()]).then(([f, t, p]) => { if (!dead) { setFb(f); setTn(t); setPl(p); setErr('') } }).catch(e => { if (!dead) setErr((e as Error).message) })
    go(); const t = window.setInterval(go, 5000)
    return () => { dead = true; window.clearInterval(t) }
  }, [])
  const row = (k: string, v: React.ReactNode) => <tr key={k}><td className="muted">{k}</td><td><b>{v}</b></td></tr>
  const box = (title: string, s: Status, rows: (s: Record<string, unknown>) => React.ReactNode[]) => (
    <div className="dbox"><h4>{title}</h4>
      {!s ? <div className="muted small">Loading…</div> : s.enabled === false ? <div className="muted small">Not running. Its key is not set on the server.</div> :
        <><table><tbody>{rows(s)}</tbody></table>
          <div className={'small ' + (s.last_error ? 'loss' : 'gain')}>{s.last_error ? 'Last error: ' + String(s.last_error) : 'No errors. Last update ' + ago(s.last_tick)}</div></>}
    </div>)
  return (
    <div className="overlay" onClick={onClose}>
      <div className="card scroll" onClick={e => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <h3>Data collection</h3>
        {err && <div className="loss small">{err}</div>}
        {box('Football (API-Football)', fb, s => [row('Fixtures stored', num(s.fixtures)), row('Finished matches', num(s.finished)), row('With full details (stats, events, lineups)', `${num(s.with_details)} of ${num(s.finished)}`),
          row('Live now', num(s.live_now)), row('Live score changes logged', num(s.live_snapshots)), row('Requests used today', `${num(s.requests_used_today)} of 7,500`)])}
        {box('Tennis (api-tennis)', tn, s => [row('Matches stored', num(s.matches)), row('With match statistics', num(s.with_stats)), row('History reached', `${num(s.history_days_done)} of ${num(s.history_target)} days (back to ${String(s.earliest ?? '–')})`),
          row('Live now', num(s.live_now)), row('Live score changes logged', num(s.live_snapshots))])}
        {pl && pl.enabled === false ? null : <div className="dbox"><h4>Betfair price log (prices with the live score)</h4>{!pl ? <div className="muted small">Loading…</div> :
          <><table><tbody>{[row('Price changes recorded', num(pl.ticks)), row('Markets', num(pl.markets)), row('In-play changes', num(pl.in_play_ticks)), row('Last recorded', pl.last ? ago(new Date(Number(pl.last) * 1000).toISOString()) : '–')]}</tbody></table>
            <div className={'small ' + (pl.last_error ? 'loss' : 'gain')}>{pl.last_error ? 'Last error: ' + String(pl.last_error) : 'No errors'}</div></>}</div>}
        <div className="row" style={{ marginTop: 10, justifyContent: 'flex-end' }}><button onClick={onClose}>Close</button></div>
      </div>
    </div>
  )
}

function loadSettings(): Settings {
  try { const s = JSON.parse(localStorage.getItem('autobets.settings') ?? '{}'); if (s.rows === 21 || s.rows === 0) delete s.rows
    return { ...DEFAULTS, ...s, keys: { ...KEYS, ...(s.keys ?? {}) } } } catch { return DEFAULTS }
}

export default function App() {
  const [ready, setReady] = useState<'checking' | 'token' | 'ok' | 'error'>('checking')
  const [bootError, setBootError] = useState('')
  const [tokenInput, setTokenInput] = useState('')
  const [mode, setMode] = useState('')
  const [sport, setSport] = useState<'tennis' | 'football'>('tennis')
  const [markets, setMarkets] = useState<MarketInfo[]>([])
  const [ladders, setLadders] = useState<LadderRef[]>([])
  /** Every market you have open, shown or not. Up to MAX_LADDERS ladders are on screen; the rest wait behind a tab. */
  const [expanded, setExpanded] = useState<Record<string, MarketInfo[] | 'loading'>>({})
  const [picker, setPicker] = useState<{ m: MarketInfo; sel: string[] } | null>(null)
  const [ctxs, setCtxs] = useState<Record<string, MatchCtx>>({})
  const [openList, setOpenList] = useState<MarketInfo[]>([])
  const [q, setQ] = useState(''), [fIn, setFIn] = useState(false), [fSoon, setFSoon] = useState(false), [fMine, setFMine] = useState(false), [byVol, setByVol] = useState(false)
  const [folded, setFolded] = useState<Record<string, boolean>>({})
  const [centres, setCentres] = useState<Record<string, number | null>>({})
  const [state, setState] = useState<State | null>(null)
  const [settings, setSettings] = useState<Settings>(loadSettings)
  const [showSettings, setShowSettings] = useState(false)
  const [synced, setSynced] = useState(false)
  const [attach, setAttach] = useState<{ id: string; title: string } | null>(null)
  const [badge, setBadge] = useState({ recs: 0, needs: 0 }), [discuss, setDiscuss] = useState<{ marketId: string; text: string } | null>(null)
  const refreshBadges = useCallback(() => api.alerts('all', 30).then(r => setBadge({ recs: r.counts.recs, needs: r.counts.needs_action })).catch(() => undefined), [])
  type Screen = 'home' | 'analyse' | 'settings' | 'manual' | 'plan' | 'scripts' | 'recs' | 'alerts'
  const [screen, setScreenState] = useState<Screen>(() => { const h = window.location.hash.replace('#', ''); return (['home', 'analyse', 'settings', 'manual', 'plan', 'scripts', 'recs', 'alerts'] as string[]).includes(h) ? (h as Screen) : 'home' })
  const setScreen = (s: Screen) => { setScreenState(s); try { window.history.replaceState(null, '', '#' + s) } catch { /* ignore */ } }
  const [showData, setShowData] = useState(false), [showAi, setShowAi] = useState(false), [showSafety, setShowSafety] = useState(false)
  const [layouts, setLayouts] = useState<Record<string, Settings>>(() => { try { return JSON.parse(localStorage.getItem('autobets.layouts') ?? '{}') } catch { return {} } })
  const [layoutName, setLayoutName] = useState('')
  useEffect(() => { try { localStorage.setItem('autobets.layouts', JSON.stringify(layouts)) } catch { /* ignore */ } }, [layouts])
  const [active, setActive] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [menu, setMenu] = useState<{ l: LadderRef; price: number; x: number; y: number } | null>(null)
  const seenEvt = useRef(Date.now() / 1000)
  const [toast, setToast] = useState<{ text: string; kind: 'ok' | 'warn' | 'err' } | null>(null)
  const inFlight = useRef(false)

  // Lay basis and the confirm-above stake live on the server (Safety and limits). The server value wins when the app opens or the panel closes;
  // changing them on the ladder toolbar writes them back.
  const pullSafety = useCallback(() => api.settings().then(r => { setSettings(s => ({ ...s, layBasis: r.lay_basis, confirmAbove: r.confirm_manual_above })); setSynced(true) }).catch(() => setSynced(true)), [])
  useEffect(() => { if (ready === 'ok') void pullSafety() }, [ready, pullSafety])
  useEffect(() => { if (ready !== 'ok') return; void refreshBadges(); const t = window.setInterval(() => void refreshBadges(), 10000); return () => window.clearInterval(t) }, [ready, refreshBadges])
  useEffect(() => { if (synced) api.saveSettings({ lay_basis: settings.layBasis, confirm_manual_above: Number(settings.confirmAbove) || 0 }).catch(() => undefined) }, [synced, settings.layBasis, settings.confirmAbove])
  const say = useCallback((text: string, kind: 'ok' | 'warn' | 'err' = 'ok') => {
    setToast({ text, kind })
    window.setTimeout(() => setToast(t => (t && t.text === text ? null : t)), 4000)
  }, [])

  const theme = settings.theme
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

  const shownIds = Array.from(new Set(ladders.map(l => l.marketId)))
  const ids = Array.from(new Set([...openList.map(m => m.market_id), ...shownIds]))
  useEffect(() => {
    if (ready !== 'ok' || !ids.length) return
    let dead = false
    const go = () => api.context(ids).then(c => { if (!dead) setCtxs(c) }).catch(() => { /* context is decoration; ignore errors */ })
    go(); const t = window.setInterval(go, 5000)
    return () => { dead = true; window.clearInterval(t) }
  }, [ready, ids.join(',')])                                                       // eslint-disable-line react-hooks/exhaustive-deps
  const refresh = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try { setState(await api.state(ids, settings.shortS, settings.longS)) } catch (e) { say((e as Error).message, 'err') } finally { inFlight.current = false }
  }, [ids.join(','), say, settings.shortS, settings.longS])                       // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (ready !== 'ok') return
    refresh()
    const t = window.setInterval(refresh, ids.length ? 1000 : 3000)
    return () => window.clearInterval(t)
  }, [ready, refresh, ids.length])

  useEffect(() => {
    for (const e of state?.events ?? []) if (e.t > seenEvt.current) { seenEvt.current = e.t; say(e.text, e.text.includes('FAILED') ? 'err' : 'ok') }
  }, [state, say])

  const typed = resolveStakeText(settings.stakeText, settings.bank, settings.stakeMode)
  const stakeInvalid = settings.stakeText.trim() !== '' && typed == null
  const stake = typed ?? presetStake0(settings.presets[settings.stakeIdx] ?? settings.presets[0])
  function presetStake0(v: number) { return settings.stakeMode === 'pct' ? Math.round(settings.bank * v) / 100 : v }
  const stakeBox = useRef<HTMLInputElement>(null)
  const [ladderRows, setLadderRows] = useState<Record<string, number>>({})      // each ladder is resized on its own; blank = the setting
  const [ladderStake, setLadderStake] = useState<Record<string, string>>({})     // each ladder can have its own stake; empty = use the toolbar stake
  /** One stake entry: £ amount, or a percentage of the bank ("2%"), or in % mode a bare number is a percentage. */
  const resolveStake = (t: string) => resolveStakeText(t, settings.bank, settings.stakeMode)
  const stakeFor = (l: LadderRef, side?: Side): { amount: number; bad: boolean } => {
    const own = ladderStake[keyOf(l)] ?? ''
    if (own.trim() !== '') { const v = resolveStake(own); return { amount: v ?? stake, bad: v == null } }
    if (side === 'LAY' && settings.sepLay && settings.layText.trim() !== '') { const v = resolveStake(settings.layText); return { amount: v ?? stake, bad: v == null } }
    return { amount: stake, bad: stakeInvalid }
  }

  const submit = useCallback(async (p: Pending) => {
    try {
      const r = await api.place({ market_id: p.marketId, selection_id: p.selectionId, side: p.side, price: p.price, size: p.size, persistence: settings.persistence, fok_s: settings.fokS || undefined,
        offset: p.entry && settings.offsetTicks ? settings.offsetTicks : undefined, stop: p.entry && settings.stopTicks ? settings.stopTicks : undefined })
      const o = r.order
      const text = `${p.runner}: ${p.side} £${p.size.toFixed(2)} @ ${p.price.toFixed(2)} — ${o.status === 'MATCHED' ? 'matched' : o.status === 'PARTIAL' ? `part matched £${o.matched.toFixed(2)}` : o.status === 'UNMATCHED' ? 'waiting (unmatched)' : o.status.toLowerCase()}`
      say(text, o.status === 'REJECTED' ? 'err' : r.warnings.length ? 'warn' : 'ok')
      if (r.warnings.length) say(r.warnings[0], 'warn')
      refresh()
    } catch (e) { say((e as Error).message, 'err') }
  }, [refresh, say, settings.persistence, settings.fokS, settings.offsetTicks, settings.stopTicks])

  const lastClick = useRef({ k: '', t: 0 })
  const click = (l: LadderRef, side: Side, price: number) => {
    if (settings.clickMode === 'double') {
      const k = `${keyOf(l)}|${side}|${price}`, now = Date.now()
      if (lastClick.current.k !== k || now - lastClick.current.t > 450) { lastClick.current = { k, t: now }; return }
      lastClick.current = { k: '', t: 0 }
    }
    const m = state?.markets[l.marketId]
    if (m && m.status && m.status !== 'OPEN') return say(`The market is ${m.status.toLowerCase()} — bets cannot be placed`, 'warn')
    const sf = stakeFor(l, side)
    if (sf.bad) return say('The stake box needs an amount of £1 or more (or clear it to use the default)', 'err')
    const size = orderSize(side, price, sf.amount, settings.layBasis)
    if (size < 1) return say('Minimum stake is £1', 'err')
    const p: Pending = { marketId: l.marketId, selectionId: l.selectionId, side, price, size, runner: m?.runners[l.selectionId] ?? l.selectionId, entry: true }
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
  const greenMarket = async (marketId: string, hard: boolean, pct = 1) => {
    const r = await api.green(marketId, hard, pct).catch(e => { say(e.message, 'err'); return null })
    if (r) say(r.greened ? `${pct < 1 ? `${Math.round(pct * 100)}% hedge` : hard ? 'Hard close' : 'Green up'} done — locked ${money(r.locked ?? 0)}${r.level ? '' : ' (not fully level)'}${r.cancelled ? `, cancelled ${r.cancelled}` : ''}` : (r.cancelled ? `Cancelled ${r.cancelled}; ` : '') + (r.reason ?? 'nothing to do'), r.greened ? 'ok' : 'warn')
    refresh()
  }

  const autoGreen = async (marketId: string, level: number) => {
    try { await api.addMarketTrigger({ market_id: marketId, level }); say(`Auto hard-close set for when the market profit reaches ${money(level)}`) } catch (e) { say((e as Error).message, 'err') }
    refresh()
  }
  const delAuto = async (id: string) => { await api.delMarketTrigger(id).catch(e => say(e.message, 'err')); refresh() }

  const cancelAt = async (l: LadderRef, price: number) => {
    const trg = state?.triggers.filter(t => t.market_id === l.marketId && t.selection_id === l.selectionId && t.price === price) ?? []
    await Promise.all(trg.map(t => api.delTrigger(t.id).catch(e => say(e.message, 'err'))))
    const here = state?.orders.filter(o => o.market_id === l.marketId && o.selection_id === l.selectionId && o.price === price) ?? []
    await Promise.all(here.map(o => api.cancel(o.order_id).catch(e => say(e.message, 'err'))))
    refresh()
  }
  const editOrder = async (id: string, b: { price?: number; size?: number }) => {
    try { const r = await api.edit(id, b); say(`Changed to £${r.order.size.toFixed(2)} @ ${r.order.price.toFixed(2)} — ${r.order.status === 'MATCHED' ? 'matched' : r.order.status.toLowerCase()}`) }
    catch (e) { say((e as Error).message, 'err') }
    refresh()
  }
  const cancelOrder = async (id: string) => { await api.cancel(id).catch(e => say(e.message, 'err')); refresh() }
  const cancelEverything = async () => {
    for (const id of ids) await api.cancelAll(id).catch(e => say(e.message, 'err'))
    say('Cancelled all unmatched bets'); refresh()
  }
  const persistAll = async (persistence: 'KEEP' | 'CANCEL' | 'TAKE_SP') => {
    const r = await api.persist({ persistence, market_ids: ids }).catch(e => { say(e.message, 'err'); return null })
    if (r) say(`${r.changed} bet${r.changed === 1 ? '' : 's'} set to ${persistence === 'TAKE_SP' ? 'take SP' : persistence.toLowerCase()} at the off`)
    refresh()
  }
  const persistOne = async (id: string, persistence: 'KEEP' | 'CANCEL' | 'TAKE_SP') => { await api.persist({ persistence, order_id: id }).catch(e => say(e.message, 'err')); refresh() }
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

  /** A market's runners are one unit (a tennis match is A and B, a football match is home, draw and away), so they open and close together. */
  const showMarket = (m: MarketInfo) => {
    const want = (m.shown ?? Object.keys(m.runners)).map(selectionId => ({ marketId: m.market_id, selectionId }))
    if (ladders.some(l => l.marketId === m.market_id)) return
    if (want.length > MAX_LADDERS) return say(`${m.event} needs ${want.length} ladders, more than the ${MAX_LADDERS} that fit`, 'warn')
    setLadders(cur => {
      let out = cur
      while (out.length + want.length > MAX_LADDERS) { const first = out[0].marketId; out = out.filter(l => l.marketId !== first) }   // the market shown longest steps back to its tab
      return [...out, ...want]
    })
  }
  const toggleEvent = (eventId: string) => {
    if (expanded[eventId]) return setExpanded(o => { const n = { ...o }; delete n[eventId]; return n })
    setExpanded(o => ({ ...o, [eventId]: 'loading' }))
    api.eventMarkets(eventId).then(ms => setExpanded(o => ({ ...o, [eventId]: ms }))).catch(e => { say(e.message, 'err'); setExpanded(o => { const n = { ...o }; delete n[eventId]; return n }) })
  }
  const openById = async (id: string) => {
    try {
      const st = await api.state([id]); const m = st.markets[id]
      if (!m) throw new Error('market not available')
      openMarket({ market_id: id, name: m.name, event: m.event, competition: m.competition, start: m.start, runners: m.runners, in_play: m.in_play }); setScreen('manual')
    } catch (e) { say((e as Error).message, 'err') }
  }
  const openMarket = (m: MarketInfo) => {
    if (!m.shown && Object.keys(m.runners).length > MAX_LADDERS) { setPicker({ m, sel: Object.keys(m.runners).slice(0, 2) }); return }       // e.g. correct score: choose which runners get a ladder
    setOpenList(cur => (cur.some(x => x.market_id === m.market_id) ? cur : [...cur, m]))
    if (ladders.some(l => l.marketId === m.market_id)) return say('That market is already open', 'warn')
    showMarket(m)
  }
  const switchRunner = (l: LadderRef, to: string) => {
    setLadders(cur => {
      const i = cur.findIndex(x => keyOf(x) === keyOf(l)), j = cur.findIndex(x => x.marketId === l.marketId && x.selectionId === to)
      const out = [...cur]
      if (j >= 0) { out[i] = cur[j]; out[j] = cur[i] } else out[i] = { marketId: l.marketId, selectionId: to }
      return out
    })
    setCentres(o => ({ ...o, [`${l.marketId}:${to}`]: null, [keyOf(l)]: null }))
  }
  const closeMarket = async (marketId: string) => {
    const m = state?.markets[marketId]
    const risk = (state?.triggers ?? []).filter(t => t.market_id === marketId).length + (state?.orders ?? []).filter(o => o.market_id === marketId).length
    const pos = m?.outcomes && Math.max(...Object.values(m.outcomes)) - Math.min(...Object.values(m.outcomes)) > 0.004
    if ((risk || pos) && !window.confirm(`Close this market's ladders? ${pos ? 'You still have a position. ' : ''}${risk ? 'Unmatched orders and stops stay active. ' : ''}`)) return
    setLadders(cur => cur.filter(l => l.marketId !== marketId)); setOpenList(cur => cur.filter(m => m.market_id !== marketId))
    setLadderStake(o => Object.fromEntries(Object.entries(o).filter(([k]) => !k.startsWith(marketId + ':'))))
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const l = ladders.find(x => keyOf(x) === active)
      if (e.key === 'Escape') { setPending(null); setShowSettings(false); setMenu(null) }
      else if (e.key.toLowerCase() === settings.keys.recentre.toLowerCase()) setCentres({})
      else if (/^[1-8]$/.test(e.key)) {
        const i = Number(e.key) - 1
        if (l) setLadderStake(o => (i < settings.presets.length ? { ...o, [keyOf(l)]: settings.stakeMode === 'pct' ? settings.presets[i] + '%' : String(settings.presets[i]) } : o))
        else setSettings(s => (i < s.presets.length ? { ...s, stakeIdx: i, ...PRESET_OFF } : s))
      }
      else if (e.key.toLowerCase() === settings.keys.stakeBox.toLowerCase()) { e.preventDefault(); stakeBox.current?.focus(); stakeBox.current?.select() }
      else if (l && e.key.toLowerCase() === settings.keys.cancelBack.toLowerCase()) cancelAll(l, 'BACK')
      else if (l && e.key.toLowerCase() === settings.keys.cancelLay.toLowerCase()) cancelAll(l, 'LAY')
      else if (l && e.key.toLowerCase() === settings.keys.closeRunner.toLowerCase()) closePos(l)
      else if (e.key.toLowerCase() === settings.keys.reverse.toLowerCase()) setSettings(s => ({ ...s, reverse: !s.reverse }))
      else if (l && e.key.toLowerCase() === settings.keys.hardClose.toLowerCase()) greenMarket(l.marketId, true)
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
        {(() => {
          const figs = Object.values(state?.markets ?? {}).map(marketFigure).filter((x): x is number => x != null)
          if (!figs.length) return null
          const total = figs.reduce((x, y) => x + y, 0)
          return <span className={'stat totalpl ' + (Math.round(total * 100) >= 0 ? 'gain' : 'loss')} title="All open markets together: what you would lock by hard-closing each one now (or your guaranteed result where there is nothing left to hedge)">P&L <b>{money(total)}</b></span>
        })()}
        <span className="stat">Exposure <b>£{(tot?.exposure ?? 0).toFixed(2)}</b></span>
        <HealthBadge />
        <StatusStrip onOpenSafety={() => setShowSafety(true)} onNotice={(t, k) => say(t, k)} />
        <button className="sm" onClick={() => setShowSafety(true)} title="Loss limits, automation switch, AI limits">Safety</button>
        <button className="sm" onClick={() => { setDiscuss(null); setShowAi(v => !v) }} title="Ask the copilot about your open markets (ideas only, it cannot place bets)">Copilot</button>
        <button className="sm" onClick={() => setShowData(true)} title="What the football and tennis data collectors have stored">Data</button>
        <button className="sm" onClick={() => setShowSettings(true)}>Ladder settings</button>
        <button className="sm" onClick={() => setSettings(s => ({ ...s, theme: s.theme === 'dark' ? 'light' : 'dark' }))}>{theme === 'dark' ? 'Light' : 'Dark'}</button>
      </header>

      <nav className="navbar" aria-label="Screens">
        {([['home', 'Home'], ['recs', 'Recommendations'], ['plan', 'Plan'], ['scripts', 'Scripts'], ['manual', 'Manual Trading'], ['analyse', 'Analyse'], ['alerts', 'Alerts'], ['settings', 'Settings']] as [Screen, string][]).map(([k, l]) => <button key={k} className={screen === k ? 'on' : ''} onClick={() => setScreen(k)}>{l}{k === 'recs' && badge.recs > 0 && <span className="nbadge">{badge.recs}</span>}{k === 'alerts' && badge.needs > 0 && <span className="nbadge bad">{badge.needs}</span>}</button>)}
      </nav>
      {(screen === 'home' || screen === 'plan') && <Workbench say={say} withCopilot={screen === 'home'} openIds={ids} onOpenLadder={openById}>
        {screen === 'home' && <HomeScreen say={say} go={s => setScreen(s)} openMarket={openById} />}
        {screen === 'plan' && <PlanScreen say={say} />}
      </Workbench>}
      {screen === 'recs' && <RecsScreen say={say} onPlan={() => setScreen('plan')} onDiscuss={r => { setDiscuss({ marketId: r.market_id, text: `Why does the model like ${r.side === 'BACK' ? 'backing' : 'laying'} ${r.runner} in ${r.event}? What would make this wrong?` }); setShowAi(true) }} />}
      {screen === 'settings' && <SettingsScreen theme={theme} onTheme={() => setSettings(s => ({ ...s, theme: s.theme === 'dark' ? 'light' : 'dark' }))} onLadderSettings={() => setShowSettings(true)} />}
      {screen === 'analyse' && <AnalyseScreen say={say} />}
      {screen === 'alerts' && <AlertsScreen say={say} onGo={s => setScreen(s)} onChanged={refreshBadges} />}
      {screen === 'scripts' && <ScriptsScreen say={say} onPlan={() => setScreen('plan')} />}
      <div className="body" style={screen === 'manual' ? undefined : { display: 'none' }}>
        <aside>
          <div className="tabs">
            {(['tennis', 'football'] as const).map(s => <button key={s} className={sport === s ? 'on' : ''} onClick={() => setSport(s)}>{s === 'tennis' ? 'Tennis' : 'Football'}</button>)}
          </div>
          <div className="msearch">
            <input type="search" placeholder="Search players, teams, competitions…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search markets" />
            <div className="chips">
              <button className={'chip' + (fIn ? ' on' : '')} onClick={() => setFIn(v => !v)}>In-play</button>
              <button className={'chip' + (fSoon ? ' on' : '')} onClick={() => setFSoon(v => !v)}>Next hour</button>
              <button className={'chip' + (fMine ? ' on' : '')} onClick={() => setFMine(v => !v)}>Mine</button>
              <button className="chip" onClick={() => setByVol(v => !v)} title="Sort order">{byVol ? 'By name' : 'By start'}</button>
            </div>
          </div>
          <div className="finder">
            {markets.length === 0 && <div className="muted pad">No markets found</div>}
            {(() => {
              const needle = q.trim().toLowerCase(), now = Date.now(), mine = new Set(ids)
              const list = markets.filter(m => {
                if (needle && !`${m.event} ${m.competition} ${m.name} ${Object.values(m.runners).join(' ')}`.toLowerCase().includes(needle)) return false
                if (fIn && !m.in_play) return false
                if (fSoon && !(m.start && new Date(m.start).getTime() - now < 3600_000)) return false
                if (fMine && !mine.has(m.market_id)) return false
                return true
              }).sort((a, b) => (byVol ? a.event.localeCompare(b.event) : (a.start ?? '').localeCompare(b.start ?? '')))
              if (markets.length && !list.length) return <div className="muted pad">Nothing matches. Clear the search or a filter.</div>
              const groups = new Map<string, MarketInfo[]>()
              for (const m of list) groups.set(m.competition || 'Other', [...(groups.get(m.competition || 'Other') ?? []), m])
              return Array.from(groups.entries()).map(([comp, ms]) => (
                <div key={comp} className="mgroup">
                  <button className="mgroup-h" onClick={() => setFolded(o => ({ ...o, [comp]: !o[comp] }))}><span>{folded[comp] ? '▸' : '▾'} {comp}</span><i>{ms.length}</i></button>
                  {!folded[comp] && ms.map(m => (
                    <div key={m.market_id} className="mwrap">
                      <div className="mrowx">
                        <button className={'market' + (mine.has(m.market_id) ? ' open' : '')} onClick={() => openMarket(m)}>
                          <span>{m.in_play && <b className="livedot" title="In play" />}{m.event}</span>
                          <small className="muted">{m.name}{m.start ? ' · ' + new Date(m.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</small>
                        </button>
                        <button className="mexp" title="Add this market to your Plan (watch it, or attach a script)" onClick={() => setAttach({ id: m.market_id, title: m.event })}>▤</button>
                        {m.event_id && <button className="mexp" title="All markets on this event: half time, goal lines, correct score…" onClick={() => toggleEvent(m.event_id!)}>{expanded[m.event_id] ? '▾' : '＋'}</button>}
                      </div>
                      {m.event_id && expanded[m.event_id] === 'loading' && <div className="muted small pad">Loading markets…</div>}
                      {m.event_id && Array.isArray(expanded[m.event_id]) && groupMarkets(expanded[m.event_id] as MarketInfo[], m.event).map(([label, list]) => (
                        <div key={label} className="mxgroup">
                          <div className="mxh">{label}</div>
                          {list.map(x => <button key={x.market_id} className={'mx' + (mine.has(x.market_id) ? ' open' : '')} onClick={() => openMarket(x)}>{x.name}<small className="muted">{Object.keys(x.runners).length > MAX_LADDERS ? ` · ${Object.keys(x.runners).length} runners` : ''}</small></button>)}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ))
            })()}
          </div>
        </aside>

        <main>
          <div className="toolbar">
            <span className="muted">Stake £</span>
            {settings.presets.map((v, i) => (
              <button key={i} className={'chipbtn' + (i === settings.stakeIdx && typed == null ? ' on' : '')} onClick={() => setSettings(s => ({ ...s, stakeIdx: i, ...PRESET_OFF }))} title={`Key ${i + 1}${settings.stakeMode === 'pct' ? ` — ${v}% of your £${settings.bank} bank = £${presetStake0(v)}` : ''}`}>{settings.stakeMode === 'pct' ? v + '%' : v}</button>
            ))}
            <span className="stakebox" title="Type any stake, e.g. 65 (press S to jump here, Enter to finish). Clear it to go back to the presets.">
              <span className="muted">£</span>
              <input ref={stakeBox} inputMode="decimal" placeholder="any" className={(typed != null ? 'on' : '') + (stakeInvalid ? ' bad' : '')}
                     value={settings.stakeText} onChange={e => setSettings(s => ({ ...s, stakeText: e.target.value }))}
                     onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') (e.target as HTMLInputElement).blur() }} />
            </span>
            {settings.sepLay && <span className="stakebox" title="Stake used for lay bets (blank = same as above)">
              <span className="muted">Lay £</span>
              <input inputMode="decimal" placeholder="same" value={settings.layText} onChange={e => setSettings(s => ({ ...s, layText: e.target.value }))} />
            </span>}
            {stakeInvalid && <span className="loss small">min £1</span>}
            <span className="sep" />
            <span className="muted">Lay by</span>
            {(['stake', 'liability'] as const).map(b => <button key={b} className={'chipbtn' + (settings.layBasis === b ? ' on' : '')} onClick={() => setSettings(s => ({ ...s, layBasis: b }))}>{b === 'stake' ? 'Stake' : 'Liability'}</button>)}
            <span className="sep" />
            <button className={'chipbtn on'} onClick={() => setSettings(s => ({ ...s, pnlBasis: s.pnlBasis === 'runner' ? 'market' : 'runner' }))}
                    title="What the profit and loss column on the ladders shows: this runner only, or the whole market">P&amp;L: {settings.pnlBasis === 'runner' ? 'runner' : 'market'}</button>
            <span className="muted" title="After a bet matches, place the closing bet this many ticks away (0 = off)">Offset</span>
            <input type="number" min={0} max={50} className="tickin" value={settings.offsetTicks || ''} placeholder="0" onChange={e => setSettings(s => ({ ...s, offsetTicks: Math.max(0, Math.min(50, Number(e.target.value) || 0)) }))} />
            <span className="muted" title="Stop loss: if the price moves this many ticks against a matched bet, close the position (0 = off)">Stop</span>
            <input type="number" min={0} max={50} className="tickin" value={settings.stopTicks || ''} placeholder="0" onChange={e => setSettings(s => ({ ...s, stopTicks: Math.max(0, Math.min(50, Number(e.target.value) || 0)) }))} />
            <span className="sep" />
            <button className={'chipbtn' + (settings.reverse ? ' on' : '')} onClick={() => setSettings(s => ({ ...s, reverse: !s.reverse }))} title="Flip the ladders: highest price at the top (normal) or lowest price at the top (reversed). Key R.">⇅ Reverse</button>
            <span className="spacer" />
            <span className="muted small">{keyName(settings.keys.stakeBox)} stake box · Hover a ladder (1–8 sets its stake) · {keyName(settings.keys.cancelBack)} cancel back · {keyName(settings.keys.cancelLay)} cancel lay · {keyName(settings.keys.closeRunner)} close runner · {keyName(settings.keys.hardClose)} hard close market · {keyName(settings.keys.reverse)} reverse ladders · {keyName(settings.keys.recentre)} recentre · wheel scrolls</span>
          </div>
          {mode === 'demo' && ladders.length > 0 && (() => {
            const mid = ladders.find(x => keyOf(x) === active)?.marketId ?? ladders[0].marketId
            const go = (s: string, ip?: boolean) => api.demoStatus(mid, s, ip).then(() => say(`Demo: market ${s.toLowerCase()}${ip === undefined ? '' : ip ? ', in play' : ', pre-match'}`)).catch(e => say(e.message, 'err'))
            return <div className="toolbar demobar"><span className="muted small">Demo controls for the highlighted market (for testing):</span>
              <button className="sm" onClick={() => go('SUSPENDED')}>Suspend</button><button className="sm" onClick={() => go('OPEN')}>Reopen</button>
              <button className="sm" onClick={() => go('CLOSED')}>Close</button><button className="sm" onClick={() => go('OPEN', false)}>Pre-match</button><button className="sm" onClick={() => go('OPEN', true)}>Go in play</button></div>
          })()}
          {ladders.length === 0 && <div className="empty muted">Pick a market on the left to open its ladders ({MAX_LADDERS} on screen at once; open more and switch between them with the tabs).</div>}
          {openList.length > 1 && (
            <div className="mtabs" role="tablist">
              {openList.map(m => {
                const st = state?.markets[m.market_id], shown = shownIds.includes(m.market_id)
                const vals = st?.outcomes ? Object.values(st.outcomes) : [], worst = vals.length ? Math.min(...vals) : 0
                const hasPos = vals.length > 0 && Math.max(...vals) - Math.min(...vals) > 0.004
                const nOrd = (state?.orders ?? []).filter(o => o.market_id === m.market_id).length
                return (
                  <div key={m.market_id} role="tab" aria-selected={shown} className={'mtab' + (shown ? ' on' : '') + (st?.status && st.status !== 'OPEN' ? ' susp' : '')} onClick={() => showMarket(m)} title={shown ? 'On screen' : 'Click to bring on screen (the longest-shown market steps back to its tab)'}>
                    {(st?.in_play ?? m.in_play) && <b className="livedot" />}
                    <span className="mtab-n">{m.event}{m.name && m.name !== 'Match Odds' ? <small className="muted"> · {m.name}</small> : null}</span>
                    {hasPos && <i className={worst >= 0 ? 'gain' : 'loss'}>{money(worst)}</i>}
                    {nOrd > 0 && <em title="Unmatched bets waiting">{nOrd}</em>}
                    <button className="mtab-x" aria-label={'Close ' + m.event} onClick={e => { e.stopPropagation(); closeMarket(m.market_id) }}>×</button>
                  </div>
                )
              })}
            </div>
          )}
          <div className="mrow">
            {shownIds.map(id => {
              const group = ladders.filter(l => l.marketId === id), m = state?.markets[id]
              const orders = (state?.orders ?? []).filter(o => o.market_id === id)
              return (
                <div key={id} className="mblock" style={{ flex: `${group.length} 1 ${group.length * 290}px` }}>
                  {m ? <MarketHeader marketId={id} market={m} ctx={ctxs[id]} openOrders={orders.length} triggers={(state?.market_triggers ?? []).filter(t => t.market_id === id)} onGreen={(h, pct) => greenMarket(id, h, pct)} onAuto={lv => autoGreen(id, lv)} onDelAuto={delAuto} onClose={() => closeMarket(id)} /> : <div className="mhead muted">Loading…</div>}
                  <div className="ladders" style={{ gridTemplateColumns: `repeat(${group.length}, minmax(0, 1fr))` }}>
                    {group.map(l => {
                      const k = keyOf(l)
                      if (!m) return <div key={k} className="ladder"><div className="ladder-head muted">Loading…</div></div>
                      return (
                        <Ladder key={k} market={m} marketId={l.marketId} selectionId={l.selectionId}
                          orders={orders} presets={settings.presets} stakeText={ladderStake[k] ?? ''} defaultStake={stake} stakeBad={stakeFor(l).bad} onStakeText={t => setLadderStake(o => ({ ...o, [k]: t }))} pnlSide={settings.pnlSide} pnlBasis={settings.pnlBasis} reverse={settings.reverse} rows={ladderRows[k] ?? settings.rows} onRows={n => setLadderRows(o => ({ ...o, [k]: n }))} womLevels={settings.womLevels} showChart={settings.showChart} showTotal={settings.showTotal}
                          centre={centres[k] ?? null} autoCentre={settings.autoCentre} active={active === k}
                          onSetCentre={c => setCentres(o => ({ ...o, [k]: c }))}
                          triggers={(state?.triggers ?? []).filter(t => t.market_id === l.marketId && t.selection_id === l.selectionId)}
                          onHedge={price => hedgeAt(l, price)} onContext={(price, x, y) => setMenu({ l, price, x, y })}
                          onClick={(side, price) => click(l, side, price)} onCancelAt={price => cancelAt(l, price)} onMoveOrder={(oid, price) => editOrder(oid, { price })}
                          onWheel={d => setCentres(o => (o[k] == null ? o : { ...o, [k]: move(o[k]!, d) }))} onHover={() => setActive(k)}
                          onCancelAll={() => cancelAll(l)} onClose={() => closePos(l)}
                          onRecentre={() => setCentres(o => ({ ...o, [k]: null }))}
                          runners={m.runners} openIds={group.map(g => g.selectionId)} onSwitch={to => switchRunner(l, to)} />
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
          {ids.length > 0 && <div className="panels"><OrdersPanel orders={state?.orders ?? []} markets={state?.markets ?? {}} onEdit={editOrder} onCancel={cancelOrder}
            onCancelAll={cancelEverything} onPersistAll={persistAll} onPersist={persistOne} />
            <MatchedPanel bets={state?.matched_bets ?? []} markets={state?.markets ?? {}} />
            <TradePanel marketId={ladders.find(x => keyOf(x) === active)?.marketId ?? ladders[0]?.marketId ?? null} market={state?.markets[ladders.find(x => keyOf(x) === active)?.marketId ?? ladders[0]?.marketId ?? '']} say={say} refresh={refresh} />
            <InfoPanel markets={state?.markets ?? {}} active={(() => { const l = ladders.find(x => keyOf(x) === active) ?? ladders[0]; return l ? { marketId: l.marketId, selectionId: l.selectionId } : null })()} /></div>}
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

      {showData && <DataStatus onClose={() => setShowData(false)} />}
      {attach && <AttachDialog marketId={attach.id} title={attach.title} onClose={() => setAttach(null)} onDone={(m, k) => say(m, k)} />}
      {showSafety && <SafetyPanel onClose={() => { setShowSafety(false); void pullSafety() }} onNotice={(t, k) => say(t, k)} />}
      {showAi && <Copilot marketIds={discuss ? [discuss.marketId] : ids} seed={discuss?.text} onClose={() => { setShowAi(false); setDiscuss(null) }} />}
      {picker && (
        <div className="overlay" onClick={() => setPicker(null)}>
          <div className="card scroll" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <h3>{picker.m.event} · {picker.m.name}</h3>
            <p className="muted small">This market has {Object.keys(picker.m.runners).length} runners. Choose up to {MAX_LADDERS} to open as ladders; you can swap a ladder to any other runner later with the selector at its top.</p>
            <div className="pickgrid">
              {Object.entries(picker.m.runners).map(([id, name]) => {
                const on = picker.sel.includes(id)
                return <label key={id} className={'pick' + (on ? ' on' : '')}><input type="checkbox" checked={on} disabled={!on && picker.sel.length >= MAX_LADDERS}
                  onChange={() => setPicker(p => p && ({ ...p, sel: on ? p.sel.filter(x => x !== id) : [...p.sel, id] }))} />{name}</label>
              })}
            </div>
            <div className="row" style={{ marginTop: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => setPicker(null)}>Cancel</button>
              <button className="primary" disabled={!picker.sel.length} onClick={() => { const m = { ...picker.m, shown: picker.sel }; setPicker(null); openMarket(m) }}>Open {picker.sel.length} ladder{picker.sel.length === 1 ? '' : 's'}</button>
            </div>
          </div>
        </div>
      )}
      {showSettings && (
        <div className="overlay" onClick={() => setShowSettings(false)}>
          <div className="card wide scroll" onClick={e => e.stopPropagation()}>
            <h3>Ladder settings</h3>

            <h4>Stakes</h4>
            <label>Stakes (and the preset buttons) are
              <select value={settings.stakeMode} onChange={e => setSettings(s => ({ ...s, stakeMode: e.target.value as 'fixed' | 'pct' }))}>
                <option value="fixed">£ amounts</option><option value="pct">% of my bank</option></select>
            </label>
            <label>My bank, £ (used for % stakes; you can also type e.g. 2% in any stake box)
              <input type="number" min={1} value={settings.bank} onChange={e => setSettings(s => ({ ...s, bank: Math.max(1, Number(e.target.value) || 1) }))} />
            </label>
            <label className="check"><input type="checkbox" checked={settings.sepLay} onChange={e => setSettings(s => ({ ...s, sepLay: e.target.checked }))} />
              Use a separate stake for lay bets (the box appears in the toolbar)</label>
            <h4>Clicking</h4>
            <label>Placing a bet takes a
              <select value={settings.clickMode} onChange={e => setSettings(s => ({ ...s, clickMode: e.target.value as 'single' | 'double' }))}>
                <option value="single">single click</option><option value="double">double click (safer)</option></select>
            </label>
            <h4>Hotkeys (click a box, press the key you want)</h4>
            {Object.entries(KEY_LABELS).map(([act, label]) => (
              <label key={act}>{label}
                <input readOnly className="keybox" value={keyName(settings.keys[act])} onKeyDown={e => {
                  e.preventDefault(); e.stopPropagation()
                  if (e.key === 'Escape' || e.key === 'Tab' || e.key === 'Shift' || e.key === 'Control' || e.key === 'Alt' || e.key === 'Meta' || /^[1-8]$/.test(e.key)) return
                  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key
                  const clash = Object.entries(settings.keys).find(([a2, v]) => a2 !== act && v.toLowerCase() === k.toLowerCase())
                  if (clash) return say(`${keyName(k)} is already used for “${KEY_LABELS[clash[0]]}”`, 'warn')
                  setSettings(s => ({ ...s, keys: { ...s.keys, [act]: k } }))
                }} />
              </label>))}
            <h4>Saved layouts</h4>
            <div className="row">
              <input placeholder="Name, e.g. Tennis scalping" value={layoutName} onChange={e => setLayoutName(e.target.value)} />
              <button disabled={!layoutName.trim()} onClick={() => { setLayouts(o => ({ ...o, [layoutName.trim()]: settings })); say(`Saved layout “${layoutName.trim()}”`); setLayoutName('') }}>Save current settings</button>
            </div>
            {Object.keys(layouts).map(n => (
              <div key={n} className="row"><span style={{ flex: 1 }}>{n}</span>
                <button onClick={() => { setSettings({ ...DEFAULTS, ...layouts[n], keys: { ...KEYS, ...(layouts[n].keys ?? {}) } }); say(`Loaded “${n}”`) }}>Load</button>
                <button onClick={() => { if (window.confirm(`Delete layout “${n}”?`)) setLayouts(o => Object.fromEntries(Object.entries(o).filter(([k]) => k !== n))) }}>Delete</button></div>))}

            <h4>Layout</h4>
            <label className="check"><input type="checkbox" checked={settings.autoCentre} onChange={e => setSettings(s => ({ ...s, autoCentre: e.target.checked }))} />
              Auto-recentre on the price (off: the ladder stays put until you press Enter or ⌖)</label>
            <label>Ticks in view (default 25; the ladder compresses or relaxes to fit that many. 0 = as many as fit. You can also drag the bar under a ladder)
              <input type="number" min={0} max={61} value={settings.rows} onChange={e => setSettings(s => ({ ...s, rows: Math.max(0, Math.min(61, Number(e.target.value) || 0)) }))} />
            </label>
            <label>The profit and loss column shows
              <select value={settings.pnlBasis} onChange={e => setSettings(s => ({ ...s, pnlBasis: e.target.value as 'runner' | 'market' }))}>
                <option value="runner">this runner only (what hedging it would lock)</option><option value="market">the whole market (worst case across every runner after hedging)</option></select>
            </label>
            <label>Profit and loss column (the hedge figures) sits on the
              <select value={settings.pnlSide} onChange={e => setSettings(s => ({ ...s, pnlSide: e.target.value as 'left' | 'right' }))}>
                <option value="left">left of the ladder (Bet Angel)</option><option value="right">right of the ladder (Geeks Toy)</option>
              </select>
            </label>
            <label>Ladder direction
              <select value={settings.reverse ? 'reverse' : 'normal'} onChange={e => setSettings(s => ({ ...s, reverse: e.target.value === 'reverse' }))}>
                <option value="normal">Normal: highest price at the top</option><option value="reverse">Reversed: lowest price at the top</option>
              </select>
            </label>
            <label className="check"><input type="checkbox" checked={settings.showChart} onChange={e => setSettings(s => ({ ...s, showChart: e.target.checked }))} />
              Show the price chart under each ladder</label>
            <label className="check"><input type="checkbox" checked={settings.showTotal} onChange={e => setSettings(s => ({ ...s, showTotal: e.target.checked }))} />
              Show a column of total matched at each price (as well as Recent)</label>
            <label>Theme
              <select value={settings.theme} onChange={e => setSettings(s => ({ ...s, theme: e.target.value as 'light' | 'dark' }))}><option value="light">Light</option><option value="dark">Dark</option></select>
            </label>

            <h4>Volume and weight of money</h4>
            <label>Recent volume: short window (seconds)
              <input type="number" min={10} max={1800} value={settings.shortS} onChange={e => setSettings(s => ({ ...s, shortS: Math.max(10, Math.min(1800, Number(e.target.value) || 60)), longS: Math.max(s.longS, Math.max(10, Math.min(1800, Number(e.target.value) || 60))) }))} />
            </label>
            <label>Recent volume: long window (seconds)
              <input type="number" min={10} max={1800} value={settings.longS} onChange={e => setSettings(s => ({ ...s, longS: Math.max(s.shortS, Math.min(1800, Number(e.target.value) || 300)) }))} />
            </label>
            <label>Weight of money: prices counted each side of the book
              <input type="number" min={1} max={10} value={settings.womLevels} onChange={e => setSettings(s => ({ ...s, womLevels: Math.max(1, Math.min(10, Number(e.target.value) || 3)) }))} />
            </label>

            <h4>Stakes and orders</h4>
            <label>Stake presets £ (comma separated, up to 8)
              <input defaultValue={settings.presets.join(', ')} onBlur={e => {
                const v = e.target.value.split(',').map(x => Number(x.trim())).filter(x => x >= 1).slice(0, 8)
                if (v.length) setSettings(s => ({ ...s, presets: v, stakeIdx: Math.min(s.stakeIdx, v.length - 1) }))
              }} />
            </label>
            <label>Unmatched bets when the match starts (new bets)
              <select value={settings.persistence} onChange={e => setSettings(s => ({ ...s, persistence: e.target.value as 'KEEP' | 'CANCEL' | 'TAKE_SP' }))}>
                <option value="CANCEL">Cancel them (safest)</option><option value="KEEP">Keep them in play</option><option value="TAKE_SP">Take the Starting Price (not simulated in practice)</option>
              </select>
            </label>
            <label>Offset: place the closing bet this many ticks away once a bet matches (0 = off)
              <input type="number" min={0} max={50} value={settings.offsetTicks} onChange={e => setSettings(s => ({ ...s, offsetTicks: Math.max(0, Math.min(50, Number(e.target.value) || 0)) }))} />
            </label>
            <label>Stop: close the position if the price moves this many ticks against a matched bet (0 = off)
              <input type="number" min={0} max={50} value={settings.stopTicks} onChange={e => setSettings(s => ({ ...s, stopTicks: Math.max(0, Math.min(50, Number(e.target.value) || 0)) }))} />
            </label>
            <label>Fill or kill: cancel any unmatched part after this many seconds (0 = off)
              <input type="number" min={0} max={600} value={settings.fokS} onChange={e => setSettings(s => ({ ...s, fokS: Math.max(0, Math.min(600, Number(e.target.value) || 0)) }))} />
            </label>
            <label>Lay stakes are entered as
              <select value={settings.layBasis} onChange={e => setSettings(s => ({ ...s, layBasis: e.target.value as 'stake' | 'liability' }))}><option value="stake">a stake</option><option value="liability">a liability</option></select>
            </label>
            <label>Ask me to confirm orders of £… or more (0 = never)
              <input type="number" min={0} value={settings.confirmAbove} onChange={e => setSettings(s => ({ ...s, confirmAbove: Math.max(0, Number(e.target.value) || 0) }))} />
            </label>
            <div className="row"><button className="primary" onClick={() => setShowSettings(false)}>Done</button><button onClick={() => { if (window.confirm('Reset all ladder settings to the defaults?')) setSettings(DEFAULTS) }}>Reset to defaults</button></div>
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

      {toast && <div className={'toast ' + toast.kind} role="status">{toast.text.split(/\b(BACK|LAY)\b/).map((t, i) => t === 'BACK' || t === 'LAY' ? <b key={i} className={'sidetag ' + t.toLowerCase()}>{t}</b> : t)}</div>}
    </div>
  )
}
