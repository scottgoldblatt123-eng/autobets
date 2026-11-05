import { useCallback, useEffect, useState } from 'react'
import { api, type AiLearning, type BtResult, type ModelsData, type PerfData, type Script } from './api'
import { Bars, EquityChart, Histogram, LineChart } from './Charts'
import { RuleCards } from './ScriptsScreen'

type Say = (text: string, kind?: 'ok' | 'warn' | 'err') => void
type Tab = 'Performance' | 'Strategies' | 'Models' | 'Backtesting' | 'AI learning'
const TABS: Tab[] = ['Performance', 'Strategies', 'Models', 'Backtesting', 'AI learning']
const money = (v: number | null | undefined, plus = true) => (v == null ? '–' : (v < 0 ? '−' : plus && v > 0 ? '+' : '') + '£' + Math.abs(v).toFixed(2))
const cls = (v: number | null | undefined) => (v == null || v === 0 ? '' : v > 0 ? 'gain' : 'loss')
const pct = (v: number | null | undefined) => (v == null ? '–' : v + '%')
const tile = (label: string, value: string, sub: string, c = '') => <div className="card kpi" key={label}><span className="cap">{label}</span><b className={c}>{value}</b><small className="muted">{sub}</small></div>

function Clv() {
  return <div className="card" id="clv"><h2>What is CLV?</h2><p className="small muted" style={{ lineHeight: 1.6, margin: '8px 0 0' }}><b className="ink">Closing line value</b> compares the price you took with the price the market closed at (the last price before the match started or went in-play). If you backed at 2.20 and the market closed at 2.00, you beat the closing price. The closing price is the market's best estimate, so beating it consistently is the best early evidence that your bets have a real edge. It needs far fewer bets to show up than profit does, because profit is mostly luck over small samples. AutoBets uses CLV, not just P&amp;L, as the gate for moving from Advisor to more automation.</p></div>
}

function Performance({ days }: { days: number }) {
  const [p, setP] = useState<PerfData | null>(null), [err, setErr] = useState('')
  useEffect(() => { api.perf(days).then(setP).catch(e => setErr((e as Error).message)) }, [days])
  if (err) return <div className="loss small">{err}</div>
  if (!p) return <div className="muted">Loading…</div>
  const c = p.current, v = p.previous
  return <>
    <div className="kpis">
      {tile('Net P&L', money(c.net), `previous ${money(v.net)}`, cls(c.net))}{tile('Settled markets', String(c.trades), `previous ${v.trades}`)}{tile('Win rate', pct(c.win_rate), `previous ${pct(v.win_rate)}`)}
      {tile('Avg CLV', p.clv == null ? '–' : `${p.clv > 0 ? '+' : ''}${p.clv} pts`, `${p.clv_n} measured ideas`, cls(p.clv))}{tile('AI costs', '£' + p.costs.toFixed(2), 'estimated, this month')}
    </div>
    <div className="card"><div className="row"><h2>Cumulative P&amp;L</h2><span className="muted small">solid: this period · dashed: the period before</span></div>
      <LineChart label="Cumulative profit and loss over the selected period compared to the previous period" series={[{ points: p.prev_curve.map(x => ({ x: x.t, y: x.v })), dashed: true, color: 'var(--text-muted)' }, { points: p.curve.map(x => ({ x: x.t, y: x.v })) }]} /></div>
    <Strategies p={p} /><Clv /></>
}

function Strategies({ p }: { p: PerfData }) {
  return <div className="card tcard"><div className="row"><h2>By strategy</h2><span className="muted small">Each script, AI ideas, and manual trades, from settled markets</span></div>
    <table className="tbl"><thead><tr><th>Strategy</th><th>Markets</th><th>P&amp;L</th><th>Win rate</th></tr></thead>
      <tbody>{p.strategies.map(s => <tr key={s.name}><td>{s.name}</td><td>{s.trades}</td><td className={cls(s.pnl)}>{money(s.pnl)}</td><td>{s.win_rate}%</td></tr>)}
        {!p.strategies.length && <tr><td colSpan={4} className="muted pad">No settled markets in this period yet.</td></tr>}</tbody></table></div>
}

function Models() {
  const [m, setM] = useState<ModelsData | null>(null)
  useEffect(() => { api.anModels().then(setM).catch(() => setM({ available: false, reason: 'Could not load.' })) }, [])
  if (!m) return <div className="muted">Loading…</div>
  return <>
    <div className="card tcard"><div className="row"><h2>Live: model against the market</h2><span className="muted small">Recorded matches with a result: the model's pre-match probabilities against the last pre-match market price. Lower Brier is better.</span></div>
      {!m.available ? <div className="muted small">{m.reason}</div> : <table className="tbl"><thead><tr><th>Sport</th><th>Matches</th><th>Model Brier</th><th>Market Brier</th><th>Model right</th><th>Market right</th></tr></thead>
        <tbody>{Object.entries(m.live ?? {}).map(([sp, x]) => <tr key={sp}><td>{sp}</td><td>{x.matches}</td><td>{x.model_brier}</td><td>{x.market_brier}</td><td>{x.model_accuracy}%</td><td>{x.market_accuracy}%</td></tr>)}
          {!Object.keys(m.live ?? {}).length && <tr><td colSpan={6} className="muted pad">Not enough yet. This fills in as matches recorded by the price log finish and their results are captured. Until the model's Brier score is below the market's, treat model ideas as ideas, not edges.</td></tr>}</tbody></table>}</div>
    <div className="card tcard"><div className="row"><h2>Offline tests on match history</h2><span className="muted small">Models tested on results only (not against market prices)</span></div>
      <table className="tbl"><thead><tr><th>Sport</th><th>Model</th><th>Matches</th><th>Picked the winner</th><th>Brier</th><th>Note</th></tr></thead>
        <tbody>{m.offline?.map(o => <tr key={o.sport + o.name}><td>{o.sport}</td><td>{o.name}</td><td>{o.matches.toLocaleString()}</td><td>{o.accuracy}%</td><td>{o.brier}</td><td className="muted small">{o.note}</td></tr>)}</tbody></table></div></>
}

function BacktestView({ r, onBack, onAgain }: { r: BtResult; onBack: () => void; onAgain: () => void }) {
  const months = Object.entries(r.by_month)
  return <>
    <div className="row"><button onClick={onBack}>‹ Backtesting</button><h2>Backtest: {r.script}</h2><span className="tag">{r.target} · last {r.days} days · {r.trades} of {r.markets} recorded matches fit</span><span className="spacer" /><button className="primary" onClick={onAgain}>Run again</button></div>
    <div className="card warnbox"><b className="small"><span className="warn">!</span> Read this first</b><div className="muted small" style={{ marginTop: 4, lineHeight: 1.6 }}>{r.warnings.join(' ')}</div></div>
    <div className="kpis">{tile('Net P&L', money(r.net), `after ${r.commission * 100}% commission`, cls(r.net))}{tile('ROI', r.roi == null ? '–' : `${r.roi > 0 ? '+' : ''}${r.roi}%`, `on £${r.staked.toFixed(0)} at risk`, cls(r.roi))}{tile('Trades', String(r.trades), `${r.wins} wins · ${r.losses} losses`)}
      {tile('Max drawdown', '£' + r.max_drawdown.toFixed(2), 'peak to trough', r.max_drawdown ? 'loss' : '')}{tile('Out-of-sample', r.oos ? money(r.oos.net) : '–', r.oos ? `${r.oos.trades} trades, unseen` : 'too few trades to split', r.oos ? cls(r.oos.net) : '')}</div>
    <div className="card"><div className="row"><h2>Equity curve</h2><span className="muted small">cumulative profit, drawdowns in red, shaded = out-of-sample</span></div><EquityChart curve={r.curve} drawdown={r.drawdown} oosFrom={r.oos_from} /></div>
    <div className="homecols"><div className="card"><h3>Profit per trade</h3><Histogram {...r.histogram} /></div><div className="card"><h3>Profit by month</h3><Bars values={months.map(m => m[1])} labels={months.map(m => m[0].slice(0, 3))} label="Profit and loss by month" /></div></div>
    <RuleCards text={r.rules} />
    <div className="homecols"><div className="card tcard"><h3>Trades</h3><table className="tbl"><thead><tr><th>Date</th><th>Match</th><th>Side</th><th>Entry</th><th>P&amp;L</th></tr></thead><tbody>{[...r.trade_list].reverse().slice(0, 50).map(t => <tr key={t.market_id}><td>{t.date}</td><td>{t.event}<div className="muted small">{t.runner}</div></td><td>{t.side}</td><td>{t.entry.toFixed(2)}</td><td className={cls(t.pnl)}>{money(t.pnl)}</td></tr>)}</tbody></table></div>
      <div className="card"><h2>Assumptions</h2><ul className="small muted" style={{ lineHeight: 1.8, paddingLeft: 18 }}><li>Data: the Betfair price log (best back and lay, with the live score) and each market's recorded result: {r.data.markets} markets, {r.data.ticks.toLocaleString()} price changes so far</li><li>Fills: at the best recorded price, size treated as unlimited, so fast trading is flattered</li><li>Commission {r.commission * 100}% of net winnings per market</li><li>Script v{r.version}. Which runner it acts on: {r.target}</li><li>Only matches with a recorded result are used</li></ul></div></div></>
}

function Backtesting({ say }: { say: Say }) {
  const [scripts, setScripts] = useState<Script[]>([]), [sid, setSid] = useState(''), [target, setTarget] = useState('favourite'), [days, setDays] = useState(90), [busy, setBusy] = useState(false)
  const [past, setPast] = useState<Omit<BtResult, 'trade_list'>[]>([]), [data, setData] = useState<BtResult['data'] | null>(null), [view, setView] = useState<BtResult | null>(null), [err, setErr] = useState('')
  const load = useCallback(() => Promise.all([api.scripts(), api.backtests()]).then(([s, b]) => { setScripts(s); setSid(c => c || s[0]?.id || ''); setPast(b.items); setData(b.data) }).catch(e => setErr((e as Error).message)), [])
  useEffect(() => { void load() }, [load])
  const run = async () => { setBusy(true); setErr(''); try { const r = await api.runBacktest({ script_id: sid, target, days }); setView(r); say(`Backtest done: ${r.trades} trades.`); await load() } catch (e) { setErr((e as Error).message) } finally { setBusy(false) } }
  if (view) return <BacktestView r={view} onBack={() => setView(null)} onAgain={run} />
  return <>
    <div className="card"><div className="row"><h2>Backtesting</h2><span className="muted small">Run a script on recorded prices</span></div>
      <div className="row" style={{ marginTop: 8 }}>
        <select value={sid} onChange={e => setSid(e.target.value)} aria-label="Script">{scripts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}{!scripts.length && <option value="">No scripts yet</option>}</select>
        <select value={target} onChange={e => setTarget(e.target.value)} aria-label="Runner the script acts on"><option value="favourite">Acts on the favourite</option><option value="underdog">Acts on the underdog</option><option value="draw">Acts on the draw</option><option value="first">Acts on the first runner</option><option value="second">Acts on the second runner</option></select>
        <select value={days} onChange={e => setDays(Number(e.target.value))} aria-label="Period"><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option><option value={365}>Last year</option></select>
        <button className="primary" disabled={busy || !sid} onClick={run}>{busy ? 'Running…' : 'Run backtest'}</button></div>
      {err && <div className="loss small" style={{ marginTop: 6 }}>{err}</div>}
      <div className="muted small" style={{ marginTop: 8 }}>{data ? `Recorded so far: ${data.markets} markets, ${data.ticks.toLocaleString()} price changes${data.first ? ' since ' + new Date(data.first * 1000).toLocaleDateString([], { day: 'numeric', month: 'short' }) : ''}. Only matches with a recorded result can be tested, and the history grows every day the app runs.` : 'No price log is running.'}</div></div>
    <div className="card tcard"><h3>Previous runs</h3><table className="tbl"><thead><tr><th>When</th><th>Script</th><th>Acts on</th><th>Trades</th><th>Net</th><th>Out-of-sample</th><th /></tr></thead>
      <tbody>{past.map(b => <tr key={b.id}><td>{new Date(b.t * 1000).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</td><td>{b.script}</td><td>{b.target}</td><td>{b.trades}</td><td className={cls(b.net)}>{money(b.net)}</td><td>{b.oos ? money(b.oos.net) : '–'}</td><td><button className="sm" onClick={() => api.backtest(b.id).then(setView).catch(e => setErr((e as Error).message))}>View</button></td></tr>)}
        {!past.length && <tr><td colSpan={7} className="muted pad">No backtests yet.</td></tr>}</tbody></table></div></>
}

function AiLearn() {
  const [a, setA] = useState<AiLearning | null>(null)
  useEffect(() => { api.anAi().then(setA).catch(() => undefined) }, [])
  if (!a) return <div className="muted">Loading…</div>
  return <>
    <div className="kpis">{tile('Ideas generated', String(a.ideas), 'trade ideas so far')}{tile('Applied', String(a.stats.applied), a.stats.acceptance == null ? 'none decided yet' : `${a.stats.acceptance}% acceptance`)}{tile('Measured', String(a.stats.evidence), `of ${a.stats.evidence_needed} needed`)}{tile('Avg CLV', a.stats.avg_clv_pts == null ? '–' : `${a.stats.avg_clv_pts} pts`, 'all measured ideas')}</div>
    <div className="homecols"><div className="card tcard"><h3>CLV by confidence</h3><table className="tbl"><thead><tr><th>Confidence</th><th>Ideas measured</th><th>Avg CLV</th></tr></thead><tbody>{Object.entries(a.clv_by_confidence).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.n}</td><td className={cls(v.avg_clv_pts)}>{v.avg_clv_pts} pts</td></tr>)}{!Object.keys(a.clv_by_confidence).length && <tr><td colSpan={3} className="muted pad">Nothing measured yet. An idea is measured once its match goes in play.</td></tr>}</tbody></table></div>
      <div className="card tcard"><h3>Why you dismissed ideas</h3><table className="tbl"><tbody>{a.dismiss_reasons.map(r => <tr key={r.reason}><td>{r.reason}</td><td>{r.n}</td></tr>)}{!a.dismiss_reasons.length && <tr><td className="muted pad">No reasons recorded yet.</td></tr>}</tbody></table></div></div>
    <Clv /></>
}

/** Analyse: how things are going, which strategies and models earn their keep, and a place to test scripts on recorded prices. */
export default function AnalyseScreen({ say }: { say: Say }) {
  const [tab, setTab] = useState<Tab>('Performance'), [days, setDays] = useState(30), [p, setP] = useState<PerfData | null>(null)
  useEffect(() => { if (tab === 'Strategies') api.perf(days).then(setP).catch(() => undefined) }, [tab, days])
  return (
    <div className="screen">
      <div className="row"><h1>Analyse</h1><span className="spacer" /><span className="muted small">Date range</span>
        <select value={days} onChange={e => setDays(Number(e.target.value))} aria-label="Date range"><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option><option value={365}>Last year</option></select></div>
      <div className="row" style={{ borderBottom: '1px solid var(--border)', gap: 0 }}>{TABS.map(t => <button key={t} className={'tab' + (tab === t ? ' on' : '')} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === 'Performance' && <Performance days={days} />}
      {tab === 'Strategies' && (p ? <><Strategies p={p} /><Clv /></> : <div className="muted">Loading…</div>)}
      {tab === 'Models' && <Models />}
      {tab === 'Backtesting' && <Backtesting say={say} />}
      {tab === 'AI learning' && <AiLearn />}
    </div>
  )
}
