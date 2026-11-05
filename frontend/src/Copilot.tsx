import { useEffect, useRef, useState } from 'react'
import { api } from './api'

interface Msg { role: 'user' | 'assistant'; content: string; cost?: number }
const KEY = 'autobets.copilot'
const load = (): Msg[] => { try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') } catch { return [] } }
const SUGGEST = ['What stands out in these markets right now?', 'Is the market over- or under-reacting to the score?', 'Where would I green up, and what does holding cost me?', 'What would make this idea wrong?']

/** Advisor-mode copilot: asks Claude about the open markets. It sees prices, score, model fair prices, gaps and the position; it cannot place anything. */
export default function Copilot({ marketIds, onClose }: { marketIds: string[]; onClose: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>(load), [text, setText] = useState(''), [busy, setBusy] = useState(false), [err, setErr] = useState('')
  const [status, setStatus] = useState<{ enabled: boolean; estimated_gbp: number; cap_gbp: number } | null>(null)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { api.aiStatus().then(s => setStatus(s as never)).catch(() => undefined) }, [msgs.length])
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(msgs.slice(-40))) } catch { /* storage unavailable */ } end.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy])
  const send = async (q: string) => {
    const t = q.trim(); if (!t || busy) return
    const next: Msg[] = [...msgs, { role: 'user', content: t }]
    setMsgs(next); setText(''); setBusy(true); setErr('')
    try {
      const r = await api.aiChat(next.map(m => ({ role: m.role, content: m.content })), marketIds.slice(0, 5))
      setMsgs([...next, { role: 'assistant', content: r.reply, cost: r.cost_gbp }])
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="copilot" role="dialog" aria-label="Copilot">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <b>Copilot <span className="muted small">(Advisor: ideas only, it cannot place bets)</span></b>
        <span>{msgs.length > 0 && <button className="sm" onClick={() => { setMsgs([]); setErr('') }} title="Clear this conversation">Clear</button>} <button className="sm" onClick={onClose}>✕</button></span>
      </div>
      <div className="muted small">Looking at {marketIds.length ? `${Math.min(marketIds.length, 5)} open market${marketIds.length > 1 ? 's' : ''}` : 'no open markets — open one to ask about it'}.
        {status && ` Est. spend this month £${status.estimated_gbp.toFixed(2)} of £${status.cap_gbp}.`}</div>
      <div className="cpmsgs">
        {msgs.length === 0 && <div className="muted small pad">Ask about the markets you have open. Try:{SUGGEST.map(s => <div key={s}><button className="chip" onClick={() => send(s)}>{s}</button></div>)}</div>}
        {msgs.map((m, i) => <div key={i} className={'cpmsg ' + m.role}>{m.content}{m.cost != null && <div className="muted small">≈ £{m.cost.toFixed(3)}</div>}</div>)}
        {busy && <div className="muted small pad">Thinking…</div>}
        {err && <div className="loss small pad">{err}</div>}
        <div ref={end} />
      </div>
      <form className="row" onSubmit={e => { e.preventDefault(); send(text) }}>
        <input style={{ flex: 1 }} placeholder="Ask the copilot…" value={text} onChange={e => setText(e.target.value)} disabled={busy} />
        <button disabled={busy || !text.trim()}>Send</button>
      </form>
    </div>
  )
}
