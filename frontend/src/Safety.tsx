import { useEffect, useState } from 'react'
import { api, type Pnl, type SafetySettings } from './api'

const money = (v: number) => (v < 0 ? '-' : v > 0 ? '+' : '') + '£' + Math.abs(v).toFixed(2)

/** Live strip in the top bar: today's result, exposure, whether automation is on, and the Stop all automation button. */
export function StatusStrip({ onOpenSafety, onNotice }: { onOpenSafety: () => void; onNotice: (text: string, kind?: 'ok' | 'warn' | 'err') => void }) {
  const [p, setP] = useState<Pnl | null>(null), [confirm, setConfirm] = useState(false), [busy, setBusy] = useState(false)
  useEffect(() => {
    let dead = false
    const go = () => api.pnl().then(x => { if (!dead) setP(x) }).catch(() => undefined)
    go(); const t = window.setInterval(go, 5000)
    return () => { dead = true; window.clearInterval(t) }
  }, [])
  const stop = async () => {
    setBusy(true)
    try { const r = await api.stopAutomation(); onNotice(`Automation stopped. ${r.cancelled} unmatched automated order${r.cancelled === 1 ? '' : 's'} cancelled.`, 'warn'); setP(await api.pnl()) }
    catch (e) { onNotice((e as Error).message, 'err') } finally { setBusy(false); setConfirm(false) }
  }
  if (!p) return null
  const limitHit = (p.limits.daily > 0 && -p.today >= p.limits.daily) || (p.limits.weekly > 0 && -p.week >= p.limits.weekly)
  return (
    <>
      <span className={'stat ' + (p.today >= 0 ? 'gain' : 'loss')} title={`Today (UK time): settled ${money(p.settled_today)} plus open positions marked to market ${money(p.open_pnl)}. Manual and automated together.`}>Today <b>{money(p.today)}</b></span>
      {limitHit && <span className="badge warn" title="Automation is blocked until the limit period ends. Manual trading is not blocked.">LOSS LIMIT HIT</span>}
      <button className={'sm autobtn ' + (p.automation ? 'on' : 'off')} onClick={onOpenSafety} title="Safety and limits">{p.automation ? 'Automation on' : 'Automation OFF'}</button>
      <button className="sm stopbtn" disabled={!p.automation} onClick={() => setConfirm(true)} title="Cancel every unmatched order placed by scripts and the AI, and switch automation off">Stop all automation</button>
      {confirm && (
        <div className="overlay" onClick={() => setConfirm(false)}>
          <div className="card" role="dialog" aria-label="Stop all automation" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <h3>Stop all automation?</h3>
            <div className="small">This cancels every unmatched order placed by scripts and the AI, and pauses all scripts. Open positions stay open. Manual trading is unaffected. You can switch automation back on in Safety and limits.</div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirm(false)}>Keep running</button>
              <button className="stopbtn" disabled={busy} onClick={stop}>{busy ? 'Stopping…' : 'Stop all automation'}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

const FIELD = (v: number) => (v === 0 ? '' : String(v))

/** Safety and limits: the rules that sit between scripts / the AI and the exchange. Saved on the server, so they hold with the browser closed. */
export function SafetyForm({ heading = true }: { heading?: boolean }) {
  const [s, setS] = useState<SafetySettings | null>(null), [err, setErr] = useState('')
  useEffect(() => { api.settings().then(setS).catch(e => setErr((e as Error).message)) }, [])
  const save = async (patch: Partial<SafetySettings>) => {
    setErr('')
    try { setS(await api.saveSettings(patch)) } catch (e) { setErr((e as Error).message) }
  }
  const money_ = (key: keyof SafetySettings, label: string, hint: string) => s && (
    <label key={key}>{label}
      <input inputMode="decimal" placeholder="Not set" defaultValue={FIELD(s[key] as number)}
             onBlur={e => { const v = e.target.value.trim() === '' ? 0 : Number(e.target.value); if (Number.isNaN(v)) { setErr(`${label}: enter a number`); return } if (v !== s[key]) void save({ [key]: v }) }} />
      <small className="muted">{hint}</small>
    </label>)
  const check = (key: keyof SafetySettings, label: string, hint?: string) => s && (
    <label className="check" title={hint}><input type="checkbox" checked={s[key] as boolean} onChange={e => save({ [key]: e.target.checked })} />{label}</label>)
  return (
    <>
        {heading && <h3>Safety and limits</h3>}
        {err && <div className="loss small">{err}</div>}
        {!s ? <div className="muted small">Loading…</div> : <>
          <div className="small muted">These rules are plain code on the server. The AI cannot change or bypass them. Leave a limit empty for no limit. Manual trading is never blocked; if you set a loss limit, your manual results count toward it.</div>
          <h4>Automation</h4>
          {check('automation_enabled', 'Automation and AI actions on', 'Off = scripts and AI cannot place orders. Use Stop all automation in the top bar to also cancel their unmatched orders.')}
          <div className="row">
            <button className={'chip' + (s.ai_mode === 'advisor' ? ' on' : '')} onClick={() => save({ ai_mode: 'advisor' })}>Advisor</button>
            <button className={'chip' + (s.ai_mode === 'supervised' ? ' on' : '')} onClick={() => save({ ai_mode: 'supervised' })}>Supervised</button>
            <button className="chip" disabled title="Full AI needs the loss limits and Stop all automation proven first. Not available yet.">Full AI (not yet)</button>
          </div>
          <small className="muted">{s.ai_mode === 'advisor' ? 'The AI gives ideas and analysis only.' : 'The AI may propose a trade; nothing is placed until you approve it.'}</small>
          <h4>Loss limits (manual and automated together)</h4>
          {money_('daily_loss_limit', 'Daily loss limit (£)', 'When today\'s result reaches this loss, scripts and the AI stop placing orders until tomorrow (UK time).')}
          {money_('weekly_loss_limit', 'Weekly loss limit (£)', 'Same, for the week starting Monday (UK time).')}
          <h4>Open liability</h4>
          {money_('max_open_liability', 'Maximum open liability for automated orders (£)', 'Worst case across positions and unmatched orders. Blocks new automated orders that would go over.')}
          {check('include_manual_in_liability', 'Include my manual positions in this total')}
          <h4>Trading defaults</h4>
          <div className="row" style={{ alignItems: 'center' }}>
            <span className="muted small">Lay bets are sized by</span>
            {(['stake', 'liability'] as const).map(b => <button key={b} className={'chip' + (s.lay_basis === b ? ' on' : '')} onClick={() => save({ lay_basis: b })}>{b === 'stake' ? 'Stake' : 'Liability'}</button>)}
          </div>
          {money_('confirm_manual_above', 'Ask me to confirm manual stakes above (£)', 'Off by default. Applies to manual orders only.')}
          <h4>AI and costs</h4>
          {money_('ai_max_stake', 'Largest stake the AI may propose (£)', 'Proposals above this are refused.')}
          {money_('ai_monthly_cap', 'Monthly AI spend cap (£, estimated)', 'AI calls stop when the estimate reaches this. Set the same cap in the Anthropic Console as a hard backstop.')}
        </>}
    </>
  )
}

/** Safety and limits as a popup from the top bar. */
export function SafetyPanel({ onClose, onNotice }: { onClose: () => void; onNotice: (text: string, kind?: 'ok' | 'warn' | 'err') => void }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="card scroll" role="dialog" aria-label="Safety and limits" onClick={e => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <SafetyForm />
        <div className="row" style={{ marginTop: 6, justifyContent: 'flex-end' }}><button onClick={() => { onNotice('Safety settings are saved as you change them.', 'ok'); onClose() }}>Done</button></div>
      </div>
    </div>
  )
}
