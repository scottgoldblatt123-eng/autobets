import { useState } from 'react'
import type { MarketState, MatchedBet } from './api'
import { money } from './maths'

const hhmmss = (t: number) => new Date(t * 1000).toLocaleTimeString('en-GB')
const SOURCES: Record<string, string> = { manual: 'You', 'script:offset': 'Offset', 'script:stop': 'Stop', 'script:green': 'Green up' }

/** Matched bets: the reference list of everything that has actually been matched, newest first, with what each bet would win or lose on its own. */
export default function MatchedPanel({ bets, markets }: { bets: MatchedBet[]; markets: Record<string, MarketState> }) {
  const [open, setOpen] = useState(true)
  const stake = bets.reduce((a, b) => a + b.size, 0)
  return (
    <div className={'opanel' + (open ? '' : ' shut')}>
      <div className="ohead">
        <button className="icon" onClick={() => setOpen(o => !o)} title={open ? 'Hide' : 'Show'}>{open ? '▾' : '▸'}</button>
        <b>Matched bets</b><span className="muted"> ({bets.length}{bets.length ? ` · £${stake.toFixed(2)} matched` : ''})</span>
      </div>
      {open && (
        <div className="obody">
          {!bets.length ? <div className="muted small pad">Nothing matched yet.</div> : (
            <table>
              <thead><tr><th>Time</th><th>Type</th><th>Runner</th><th>Odds</th><th>Stake</th><th>If it wins</th><th>If it loses</th><th>By</th></tr></thead>
              <tbody>
                {bets.map(b => {
                  const m = markets[b.market_id]
                  return (
                    <tr key={b.order_id}>
                      <td className="num">{hhmmss(b.t)}</td>
                      <td><b className={b.side === 'BACK' ? 'sidetag back' : 'sidetag lay'}>{b.side}</b></td>
                      <td>{m?.runners[b.selection_id] ?? b.selection_id}<div className="muted small">{m?.event}</div></td>
                      <td className="num">{b.price.toFixed(2)}</td>
                      <td className="num">£{b.size.toFixed(2)}</td>
                      <td className={'num ' + (b.if_wins >= 0 ? 'gain' : 'loss')}>{money(b.if_wins)}</td>
                      <td className={'num ' + (b.if_loses >= 0 ? 'gain' : 'loss')}>{money(b.if_loses)}</td>
                      <td className="muted">{SOURCES[b.source] ?? b.source}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
