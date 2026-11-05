import { useCallback, useEffect, useState } from 'react'
import { api, type AlertRow } from './api'

type Say = (text: string, kind?: 'ok' | 'warn' | 'err') => void
const LABEL: Record<string, [string, string]> = { warning: ['bad', '✕ Warning'], system: ['bad', '✕ System'], suspension: ['', '! Suspension'], info: ['ok', '✓ Info'], trade: ['ok', '✓ Trade'], recommendation: ['', '★ Recommendation'] }
const CHIPS: [string, string][] = [['all', 'All'], ['needs_action', 'Needs action'], ['warnings', 'Warnings'], ['suspensions', 'Suspensions'], ['trades', 'Trades'], ['system', 'System']]

/** Alerts centre: what happened and what needs you. */
export default function AlertsScreen({ say, onGo, onChanged }: { say: Say; onGo: (s: 'recs' | 'plan') => void; onChanged: () => void }) {
  const [rows, setRows] = useState<AlertRow[]>([]), [chip, setChip] = useState('all'), [days, setDays] = useState(30), [counts, setCounts] = useState({ needs_action: 0, unread: 0, recs: 0 }), [err, setErr] = useState('')
  const load = useCallback(() => api.alerts(chip, days).then(r => { setRows(r.items); setCounts(r.counts); setErr('') }).catch(e => setErr((e as Error).message)), [chip, days])
  useEffect(() => { void load(); const t = window.setInterval(() => void load(), 8000); return () => window.clearInterval(t) }, [load])
  const t = (x: number) => { const d = new Date(x * 1000); return d.toDateString() === new Date().toDateString() ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  return (
    <div className="screen">
      <div className="row"><h1>Alerts Centre</h1><span className="spacer" /><span className="muted small">Date range</span>
        <select value={days} onChange={e => setDays(Number(e.target.value))} aria-label="Date range"><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select></div>
      {err && <div className="loss small">{err}</div>}
      <div className="row">{CHIPS.map(([k, l]) => <button key={k} className={'chip' + (chip === k ? ' on' : '')} onClick={() => setChip(k)}>{l}{k === 'needs_action' ? ` (${counts.needs_action})` : ''}</button>)}<span className="spacer" />
        <button onClick={() => api.alertsRead().then(() => { say('All alerts marked as read.'); void load(); onChanged() })}>Mark all read</button></div>
      <div className="card tcard"><div className="row"><h2>Alerts</h2><span className="muted small">Actionable alerts carry buttons</span></div>
        <table className="tbl"><thead><tr><th>Time</th><th>Type</th><th>Alert</th><th>Action taken</th><th /></tr></thead>
          <tbody>{rows.map(a => { const [cls, lab] = LABEL[a.type] ?? ['', a.type]; return (
            <tr key={a.id} style={a.read ? { opacity: .7 } : undefined}><td className="nowrap">{t(a.t)}</td><td><span className={'abadge ' + cls}>{lab}</span></td><td>{a.text}</td><td className="muted small">{a.action || '–'}</td>
              <td className="nowrap">
                {a.type === 'recommendation' && a.needs_action && <button className="primary sm" onClick={() => onGo('recs')}>Review</button>}
                {(a.type === 'warning' || a.type === 'system') && a.needs_action && <button className="sm" onClick={() => api.alertDismiss(a.id).then(() => { void load(); onChanged() })}>Dismiss</button>}
                {a.ref.kind === 'plan' && <button className="sm" onClick={() => onGo('plan')}>View</button>}
              </td></tr>) })}
            {!rows.length && <tr><td colSpan={5} className="muted pad">Nothing here yet. Alerts appear when scripts act, markets suspend, limits are hit, data feeds go stale, or the AI has an idea for you.</td></tr>}</tbody></table></div>
      <div className="card"><div className="row"><h2>Where alerts go</h2></div>
        <div className="row" style={{ gap: 24, marginTop: 8 }}><label className="sw"><input type="checkbox" checked readOnly /> In the browser (this screen and the badges)</label>
          <label className="sw"><input type="checkbox" disabled /> Email for warnings and system <span className="muted small">(not set up yet)</span></label>
          <label className="sw"><input type="checkbox" disabled /> Phone push <span className="muted small">(not set up yet)</span></label></div></div>
    </div>
  )
}
