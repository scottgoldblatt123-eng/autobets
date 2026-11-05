import { useEffect, useRef, useState } from 'react'
import { api, type AiProposal, type ScriptDraft } from './api'
import { RuleCards } from './ScriptsScreen'

interface Msg { role: 'user' | 'assistant'; content: string; cost?: number; proposals?: AiProposal[]; notes?: string[]; draft?: ScriptDraft; saved?: string }
const KEY = 'autobets.copilot', MODE_KEY = 'autobets.copilot.mode'
const load = (): Msg[] => { try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') } catch { return [] } }
const SUGGEST = ['What stands out in these markets right now?', 'Is the market over- or under-reacting to the score?', 'Where would I green up, and what does holding cost me?', 'What would make this idea wrong?']

/** Advisor-mode copilot: asks Claude about the open markets. It sees prices, score, model fair prices, gaps and the position; it cannot place anything. */
export default function Copilot({ marketIds, onClose, seed, docked = false, startBuild = false }: { marketIds: string[]; onClose?: () => void; seed?: string; docked?: boolean; startBuild?: boolean }) {
  const [msgs, setMsgs] = useState<Msg[]>(load), [text, setText] = useState(seed ?? ''), [busy, setBusy] = useState(false), [err, setErr] = useState('')
  const [status, setStatus] = useState<{ enabled: boolean; estimated_gbp: number; cap_gbp: number } | null>(null)
  const [mode, setModeState] = useState<'advisor' | 'supervised'>(() => { try { return localStorage.getItem(MODE_KEY) === 'supervised' ? 'supervised' : 'advisor' } catch { return 'advisor' } })
  useEffect(() => { api.settings().then(s => setModeState(s.ai_mode === 'supervised' ? 'supervised' : 'advisor')).catch(() => undefined) }, [])     // the saved setting (Safety and limits) is the source of truth
  const setMode = (m: 'advisor' | 'supervised') => { setModeState(m); try { localStorage.setItem(MODE_KEY, m) } catch { /* storage unavailable */ }; api.saveSettings({ ai_mode: m }).catch(() => undefined) }
  const [build, setBuild] = useState(startBuild), [acting, setActing] = useState<string | null>(null)
  const act = async (mi: number, p: AiProposal, approve: boolean) => {
    setActing(p.id); setErr('')
    try {
      const r = approve ? (await api.aiApprove(p.id)).proposal : await api.aiReject(p.id)
      setMsgs(ms => ms.map((m, i) => i === mi ? { ...m, proposals: m.proposals?.map(x => x.id === p.id ? { ...x, status: r.status } : x) } : m))
    } catch (e) { setErr((e as Error).message) } finally { setActing(null) }
  }
  const saveDraft = async (mi: number, d: ScriptDraft) => {
    if (!d.script) return
    setActing('draft' + mi); setErr('')
    try {
      const sc = await api.createScript({ ...d.script, _origin: 'ai' })
      setMsgs(ms => ms.map((m, i) => i === mi ? { ...m, saved: sc.name } : m)); window.dispatchEvent(new CustomEvent('autobets:scripts-changed', { detail: sc.id }))
    } catch (e) { setErr((e as Error).message) } finally { setActing(null) }
  }
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { api.aiStatus().then(s => setStatus(s as never)).catch(() => undefined) }, [msgs.length])
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(msgs.slice(-40))) } catch { /* storage unavailable */ } end.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy])
  const send = async (q: string) => {
    const t = q.trim(); if (!t || busy) return
    const next: Msg[] = [...msgs, { role: 'user', content: t }]
    setMsgs(next); setText(''); setBusy(true); setErr('')
    try {
      if (build) {
        const last = [...msgs].reverse().find(m => m.draft?.script && !m.saved)?.draft?.script       // an unsaved draft is refined, not replaced
        const r = await api.buildScript(last ? `Here is my current draft script:\n${JSON.stringify(last)}\n\nChange it like this and return the full updated script: ${t}` : t)
        setMsgs([...next, { role: 'assistant', content: r.explanation || (r.error ?? ''), cost: r.cost_gbp, draft: r }])
        return
      }
      const r = await api.aiChat(next.map(m => ({ role: m.role, content: m.content })), marketIds.slice(0, 5), mode)
      setMsgs([...next, { role: 'assistant', content: r.reply, cost: r.cost_gbp, proposals: r.proposals, notes: r.proposal_notes }])
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className={'copilot' + (docked ? ' docked' : '')} role={docked ? 'complementary' : 'dialog'} aria-label="Copilot">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <b>Copilot</b>
        <span>{msgs.length > 0 && <button className="sm" onClick={() => { setMsgs([]); setErr('') }} title="Clear this conversation">Clear</button>} {onClose && <button className="sm" onClick={onClose}>✕</button>}</span>
      </div>
      <div className="row small">
        <button className={'chip' + (mode === 'advisor' ? ' on' : '')} onClick={() => setMode('advisor')} title="Ideas and analysis only">Advisor</button>
        <button className={'chip' + (mode === 'supervised' ? ' on' : '')} onClick={() => setMode('supervised')} title="The copilot may propose a trade; nothing is placed until you approve it">Supervised</button>
        <button className={'chip' + (build ? ' on' : '')} onClick={() => setBuild(b => !b)} title="Describe a strategy in plain English; Claude drafts a script you can save, then pick from the script list">Build a script</button>
        <span className="muted">{build ? 'Describe the strategy. Drafts are saved off until you enable them.' : mode === 'advisor' ? 'Ideas only. It cannot place bets.' : 'It may propose a trade. Nothing is placed until you approve.'}</span>
      </div>
      <div className="muted small">Looking at {marketIds.length ? `${Math.min(marketIds.length, 5)} open market${marketIds.length > 1 ? 's' : ''}` : 'no markets yet — add some to your Plan or open one to ask about it'}.
        {status && ` Est. spend this month £${status.estimated_gbp.toFixed(2)} of £${status.cap_gbp}.`}</div>
      <div className="cpmsgs">
        {msgs.length === 0 && <div className="muted small pad">Ask about the markets you have open. Try:{SUGGEST.map(s => <div key={s}><button className="chip" onClick={() => send(s)}>{s}</button></div>)}</div>}
        {msgs.map((m, i) => <div key={i} className={'cpmsg ' + m.role}>{m.content}
          {m.proposals?.map(p => (
            <div key={p.id} className={'cpprop ' + p.side.toLowerCase()}>
              <div><b>{p.side} {p.runner}</b> @ {p.price} · £{p.stake}<span className="muted small"> · {p.event}</span></div>
              <div className="small">{p.take_profit_ticks ? `take profit ${p.take_profit_ticks} ticks` : 'no take-profit'} · {p.stop_loss_ticks ? `stop ${p.stop_loss_ticks} ticks` : 'no stop'}</div>
              {p.reason && <div className="muted small">{p.reason}</div>}
              {p.status === 'pending'
                ? <div className="row"><button disabled={acting === p.id} onClick={() => act(i, p, true)}>Approve and place</button><button className="sm" disabled={acting === p.id} onClick={() => act(i, p, false)}>Reject</button><span className="muted small">expires in 3 min</span></div>
                : <div className={'small ' + (p.status === 'approved' ? 'gain' : 'muted')}>{p.status === 'approved' ? 'Placed (practice mode)' : p.status}</div>}
            </div>))}
          {m.draft && <div className="draft">
            {m.draft.error && <div className="loss small">{m.draft.error}</div>}
            {m.draft.script && <><div className="small"><b>{String(m.draft.script.name)}</b></div><RuleCards fold text={m.draft.text ?? []} headline={m.draft.headline} />
              {m.saved ? <div className="gain small">Saved as “{m.saved}” (off). It is now in the script list: review and enable it on Scripts, or add it to a market from the Plan.</div>
                : <div className="row"><button className="primary sm" disabled={acting === 'draft' + i} onClick={() => saveDraft(i, m.draft!)}>Save as draft script</button><span className="muted small">or type a change to refine it</span></div>}</>}
          </div>}
          {m.notes?.map((n, k) => <div key={k} className="muted small">Not offered: {n}</div>)}
          {m.cost != null && <div className="muted small">≈ £{m.cost.toFixed(3)}</div>}</div>)}
        {busy && <div className="muted small pad">Thinking…</div>}
        {err && <div className="loss small pad">{err}</div>}
        <div ref={end} />
      </div>
      <form className="row" onSubmit={e => { e.preventDefault(); send(text) }}>
        <input style={{ flex: 1 }} placeholder={build ? 'Describe the strategy, or a change to the draft…' : 'Ask the copilot…'} value={text} onChange={e => setText(e.target.value)} disabled={busy} />
        <button disabled={busy || !text.trim()}>Send</button>
      </form>
    </div>
  )
}
