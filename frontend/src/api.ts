import type { Side } from './maths'

export interface Recent { short: [number, number][]; long: [number, number][]; short_s: number; long_s: number; short_span: number; long_span: number }
export interface Sel { backs: [number, number][]; lays: [number, number][]; traded: [number, number][]; last: number | null; status?: string; recent?: Recent }
export interface MarketState {
  name: string; event: string; competition: string; start: string | null; in_play: boolean; status?: string
  runners: Record<string, string>; selections: Record<string, Sel>; positions: Record<string, { win: number; lose: number }>
  outcomes?: Record<string, number>
  green?: { locked: number; level: boolean; bets: { selection_id: string; side: Side; price: number; stake: number }[]; after: Record<string, number> } | null
}
export interface Trigger { id: string; market_id: string; selection_id: string; price: number; direction: 'le' | 'ge'; label: string; locked: number }
export interface MarketTrigger { id: string; market_id: string; level: number; direction: 'ge' | 'le'; label: string }
export interface MatchedBet { order_id: string; market_id: string; selection_id: string; side: 'BACK' | 'LAY'; price: number; asked: number; size: number; source: string; t: number; if_wins: number; if_loses: number }
export interface PlanBet { selection_id: string; runner: string; side: Side; price: number; stake: number }
export interface Plan { bets: PlanBet[]; dropped: PlanBet[]; before: Record<string, number>; after: Record<string, number>; total_stake: number; error?: string; book?: number }
export interface PlanResult { placed: (PlanBet & { status: string; error?: string })[]; failed: number; after: Record<string, number> }
export interface Evt { t: number; text: string; trigger: string }
export interface Order {
  order_id: string; market_id: string; selection_id: string; side: Side; price: number; size: number
  matched: number; avg_price: number; remaining: number; status: string; persistence: 'KEEP' | 'CANCEL' | 'TAKE_SP'; placed_at: number
}
export interface LogEntry { t: number; kind: string; text: string }
export interface State { mode: string; markets: Record<string, MarketState>; orders: Order[]; totals: { exposure: number; open_pnl: number }; warnings: string[]; triggers: Trigger[]; market_triggers: MarketTrigger[]; matched_bets: MatchedBet[]; events: Evt[] }
export interface MatchCtx {
  kind: 'tennis' | 'football'; source: string; status: string; live: boolean; tournament?: string; round?: string
  model?: { p?: number[]; odds?: number[]; version: string; home?: number; draw?: number; away?: number; btts?: number; 'over_2.5'?: number } | null; players?: [string, string]; sets?: string[][]; sets_won?: string[] | null; game?: string[] | null; serving?: number | null
  teams?: [string, string]; goals?: number[] | null; ht?: number[] | null; elapsed?: number | null; code?: string; kickoff?: string
}
export interface FormRow { day: string; opponent: string; won?: boolean; result?: string; score: string; tournament?: string; venue?: string }
export interface MatchDetails {
  kind: 'tennis' | 'football' | null; note?: string; tour?: string | null
  players?: { name: string; rank: { place?: string; points?: string; country?: string; movement?: string } | null; form: FormRow[] }[]
  teams?: { name: string; table: { place?: number; points?: number; played?: number; gd?: number; form?: string; record?: string } | null; form: FormRow[] }[]
  why?: string
  fmodel?: { home: number; draw: number; away: number; btts: number; mu: number[]; games: number[]; correct: [string, number][]; [k: string]: unknown } | null
  model?: { v1: { p_a: number; p_b: number; odds_a: number; odds_b: number }; v2: { p_a: number; p_b: number; odds_a: number; odds_b: number }; v3?: { p_a: number; p_b: number; odds_a: number; odds_b: number; elo: number[] }; matches: number[] } | null
  h2h?: { day: string; tournament?: string; winner?: string; home?: string; away?: string; score: string }[]; h2h_wins?: number[]
}
export interface MarketInfo { market_id: string; event_id?: string; market_type?: string; shown?: string[]; name: string; event: string; competition: string; start: string | null; runners: Record<string, string>; in_play?: boolean }

let token = ''
try { token = localStorage.getItem('autobets.token') ?? '' } catch { /* storage unavailable */ }
export const setToken = (t: string) => { token = t; try { localStorage.setItem('autobets.token', t) } catch { /* ignore */ } }

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, { ...init, headers: { 'Content-Type': 'application/json', 'X-Auth': token, ...(init.headers ?? {}) } })
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* not json */ }
    throw Object.assign(new Error(msg), { status: r.status })
  }
  return r.json() as Promise<T>
}

export interface AiProposal { id: string; market_id: string; event: string; runner: string; side: 'BACK' | 'LAY'; price: number; stake: number; take_profit_ticks: number; stop_loss_ticks: number; reason: string; status: string }

export const api = {
  mode: () => call<{ mode: string }>('/api/mode'),
  ping: () => call<{ needs_token: boolean; mode: string }>('/api/ping'),
  context: (ids: string[]) => call<Record<string, MatchCtx>>(`/api/context?ids=${ids.join(',')}`),
  eventMarkets: (eventId: string) => call<MarketInfo[]>(`/api/event_markets?event_id=${encodeURIComponent(eventId)}`),
  footballStatus: () => call<Record<string, unknown>>('/api/football/status'),
  aiStatus: () => call<{ enabled: boolean; estimated_gbp: number; cap_gbp: number }>('/api/ai/status'),
  aiChat: (messages: { role: string; content: string }[], market_ids: string[], mode: string) => call<{ reply: string; cost_gbp: number; proposals: AiProposal[]; proposal_notes: string[] }>('/api/ai/chat', { method: 'POST', body: JSON.stringify({ messages, market_ids, mode }) }),
  aiApprove: (id: string) => call<{ proposal: AiProposal; warnings: string[] }>(`/api/ai/proposals/${id}/approve`, { method: 'POST' }),
  aiReject: (id: string) => call<AiProposal>(`/api/ai/proposals/${id}/reject`, { method: 'POST' }),
  pricelogStatus: () => call<Record<string, unknown>>('/api/pricelog/status'),
  tennisStatus: () => call<Record<string, unknown>>('/api/tennis/status'),
  matchDetails: (marketId: string) => call<MatchDetails>(`/api/match_details?market_id=${encodeURIComponent(marketId)}`),
  markets: (sport: string) => call<MarketInfo[]>(`/api/markets?sport=${sport}`),
  state: (ids: string[], shortS = 60, longS = 300) => call<State>(`/api/state?ids=${ids.join(',')}&short_s=${shortS}&long_s=${longS}`),
  place: (b: { market_id: string; selection_id: string; side: Side; price: number; size: number; persistence?: string; fok_s?: number; offset?: number; stop?: number }) =>
    call<{ order: Order; warnings: string[] }>('/api/orders', { method: 'POST', body: JSON.stringify(b) }),
  edit: (id: string, b: { price?: number; size?: number }) =>
    call<{ order: Order; warnings: string[] }>(`/api/orders/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  persist: (b: { persistence: string; market_ids?: string[]; order_id?: string }) =>
    call<{ changed: number }>('/api/orders-persistence', { method: 'POST', body: JSON.stringify(b) }),
  dutchPreview: (b: { market_id: string; selection_ids: string[]; side: Side; total: number; prices?: Record<string, number> }) => call<Plan>('/api/dutch/preview', { method: 'POST', body: JSON.stringify(b) }),
  dutch: (b: { market_id: string; selection_ids: string[]; side: Side; total: number; prices?: Record<string, number> }) => call<PlanResult>('/api/dutch', { method: 'POST', body: JSON.stringify(b) }),
  bookPreview: (b: { market_id: string; targets: Record<string, number> }) => call<Plan>('/api/book/preview', { method: 'POST', body: JSON.stringify(b) }),
  book: (b: { market_id: string; targets: Record<string, number> }) => call<PlanResult>('/api/book', { method: 'POST', body: JSON.stringify(b) }),
  demoStatus: (market_id: string, status: string, in_play?: boolean) => call<{ ok: boolean }>(`/api/demo/status?market_id=${market_id}&status=${status}${in_play === undefined ? '' : `&in_play=${in_play}`}`, { method: 'POST' }),
  log: (n = 100) => call<LogEntry[]>(`/api/log?n=${n}`),
  cancel: (id: string) => call<Order>(`/api/orders/${id}`, { method: 'DELETE' }),
  cancelAll: (market: string, selection?: string, side?: Side) =>
    call<{ cancelled: number }>(`/api/markets/${market}/cancel-all?${new URLSearchParams({ ...(selection ? { selection_id: selection } : {}), ...(side ? { side } : {}) })}`, { method: 'POST' }),
  green: (market: string, hard: boolean, pct = 1) =>
    call<{ greened: boolean; reason?: string; cancelled: number; locked?: number; level?: boolean; placed?: { status: string }[] }>(`/api/markets/${market}/green?hard=${hard}&pct=${pct}`, { method: 'POST' }),
  addMarketTrigger: (b: { market_id: string; level: number }) => call<MarketTrigger>('/api/market-triggers', { method: 'POST', body: JSON.stringify(b) }),
  delMarketTrigger: (id: string) => call<{ cancelled: boolean }>(`/api/market-triggers/${id}`, { method: 'DELETE' }),
  addTrigger: (b: { market_id: string; selection_id: string; price: number }) =>
    call<Trigger>('/api/triggers', { method: 'POST', body: JSON.stringify(b) }),
  delTrigger: (id: string) => call<{ cancelled: boolean }>(`/api/triggers/${id}`, { method: 'DELETE' }),
  history: (market: string, selection: string, seconds: number) =>
    call<{ points: [number, number | null, number | null, number | null, number][] }>(`/api/history?${new URLSearchParams({ market_id: market, selection_id: selection, seconds: String(seconds) })}`),
  close: (market: string, selection: string) =>
    call<{ closed: boolean; reason?: string; locked_profit?: number }>(`/api/markets/${market}/close/${selection}`, { method: 'POST' }),
}
