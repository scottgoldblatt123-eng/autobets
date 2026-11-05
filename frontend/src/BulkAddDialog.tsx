import { useState } from 'react'
import { api, type MarketInfo } from './api'
import ScriptSelect, { markScriptUsed } from './ScriptSelect'

type Rule = 'fav' | 'dog' | 'first' | 'second' | 'draw'
const RULES: [Rule, string][] = [['fav', 'Favourite (shortest price)'], ['dog', 'Outsider (longest price)'], ['first', 'First listed (home / player 1)'], ['second', 'Second listed (away / player 2)'], ['draw', 'The Draw']]

/** Add several markets to the Plan at once: watch them, or attach one script to all of them with a rule for which runner it acts on. */
export default function BulkAddDialog({ markets, onClose, onDone }: { markets: MarketInfo[]; onClose: () => void; onDone: (msg: string, kind?: 'ok' | 'warn' | 'err') => void }) {
  const [sid, setSid] = useState(''), [rule, setRule] = useState<Rule>('fav'), [stake, setStake] = useState(''), [busy, setBusy] = useState(false), [report, setReport] = useState<string[]>([])
  const go = async () => {
    const v = Number(stake)
    if (stake.trim() && !(v >= 1)) { onDone('Stake must be at least £1.', 'err'); return }
    setBusy(true); const skipped: string[] = []; let added = 0
    try {
      const st = sid ? await api.state(markets.map(m => m.market_id)).catch(() => null) : null
      for (const m of markets) {
        let selection: string | null = null
        if (sid) {
          const names = (st?.markets[m.market_id]?.runners ?? m.runners), ids = Object.keys(names)
          const price = (id: string) => { const s = st?.markets[m.market_id]?.selections[id]; return s?.backs[0]?.[0] ?? s?.last ?? null }
          const priced = ids.filter(i => price(i) != null).sort((a, b) => price(a)! - price(b)!)
          selection = rule === 'first' ? ids[0] ?? null : rule === 'second' ? ids[1] ?? null
            : rule === 'draw' ? ids.find(i => /^the draw$/i.test(names[i])) ?? null : rule === 'fav' ? priced[0] ?? null : priced[priced.length - 1] ?? null
          if (!selection) { skipped.push(`${m.event} · ${m.name}: no ${RULES.find(r => r[0] === rule)![1].toLowerCase()} found`); continue }
        }
        try { await api.planAdd({ market_id: m.market_id, selection_id: selection, script_id: sid || null, stake: stake.trim() ? v : null }); added++ } catch (e) { skipped.push(`${m.event} · ${m.name}: ${(e as Error).message}`) }
      }
    } finally { setBusy(false) }
    if (sid) markScriptUsed(sid)
    if (!skipped.length) { onDone(`Added ${added} market${added === 1 ? '' : 's'} to your Plan.`); onClose() } else { onDone(`Added ${added}; ${skipped.length} skipped.`, 'warn'); setReport(skipped) }
  }
  return (
    <div className="overlay" onClick={onClose}><div className="card" role="dialog" aria-label="Add to Plan" onClick={e => e.stopPropagation()} style={{ width: 500, maxWidth: '95vw' }}>
      <h3>Add {markets.length} market{markets.length === 1 ? '' : 's'} to your Plan</h3>
      <div className="pickerlist" style={{ maxHeight: 110 }}>{markets.map(m => <div key={m.market_id} className="small" style={{ padding: '2px 8px' }}>{m.event} <span className="muted">· {m.name}</span></div>)}</div>
      <label>Script (leave as watching to attach one later)
        <ScriptSelect value={sid} onChange={setSid} allowNone /></label>
      {sid && <>
        <label>Which runner it acts on in each market<select value={rule} onChange={e => setRule(e.target.value as Rule)}>{RULES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label>Stake (£), blank = the script's own<input inputMode="decimal" value={stake} onChange={e => setStake(e.target.value)} /></label>
        <div className="muted small">Favourite and outsider use the current best back price. Markets where the rule cannot apply (e.g. no Draw) are skipped and listed.</div></>}
      {report.length > 0 && <div className="warnbox small">{report.map(r => <div key={r}>{r}</div>)}</div>}
      <div className="row" style={{ justifyContent: 'flex-end' }}><button onClick={onClose}>{report.length ? 'Close' : 'Cancel'}</button>{!report.length && <button className="primary" disabled={busy} onClick={() => void go()}>{busy ? 'Adding…' : 'Add to Plan'}</button>}</div>
    </div></div>
  )
}
