import { useEffect, useState, type ReactNode } from 'react'
import { api, type MarketInfo } from './api'
import MarketFinder from './MarketFinder'
import BulkAddDialog from './BulkAddDialog'
import Copilot from './Copilot'

/** Home and Plan: the market list on the left (tick markets, add many to the Plan), the screen in the middle and, on Home, the AI panel on the right. */
export default function Workbench({ say, children, withCopilot, openIds, onOpenLadder }: { say: (t: string, k?: 'ok' | 'warn' | 'err') => void; children: ReactNode; withCopilot: boolean; openIds: string[]; onOpenLadder: (id: string, view?: 'ladder' | 'grid') => void }) {
  const [planned, setPlanned] = useState<string[]>([]), [bulk, setBulk] = useState<MarketInfo[] | null>(null), [rev, setRev] = useState(0), [showList, setShowList] = useState(false)
  useEffect(() => { const f = () => api.plan().then(p => setPlanned(Array.from(new Set(p.rows.map(r => r.market_id))))).catch(() => undefined); void f(); const t = window.setInterval(f, 6000); return () => window.clearInterval(t) }, [rev])
  return (
    <div className="body workbench">
      <button className="wbtoggle" onClick={() => setShowList(v => !v)}>{showList ? 'Hide market list' : 'Market list'}</button>
      <div className={'wbleft' + (showList ? ' show' : '')}><MarketFinder say={say} mode="select" planned={new Set(planned)} clearKey={rev} onAddToPlan={setBulk} onOpenLadder={m => onOpenLadder(m.market_id)} onOpenGrid={m => onOpenLadder(m.market_id, 'grid')} /></div>
      <div className="wbmain" key={rev}>{children}</div>
      {withCopilot && <div className="wbright"><Copilot docked marketIds={Array.from(new Set([...planned, ...openIds]))} /></div>}
      {bulk && <BulkAddDialog markets={bulk} onClose={() => setBulk(null)} onDone={(m, k) => { say(m, k); setRev(r => r + 1) }} />}
    </div>
  )
}
