import type { Side } from './maths'

export interface Recent { short: [number, number][]; long: [number, number][]; short_s: number; long_s: number; short_span: number; long_span: number }
export interface Sel { backs: [number, number][]; lays: [number, number][]; traded: [number, number][]; last: number | null; recent?: Recent }
export interface MarketState {
  name: string; event: string; competition: string; start: string | null; in_play: boolean
  runners: Record<string, string>; selections: Record<string, Sel>; positions: Record<string, { win: number; lose: number }>
  outcomes?: Record<string, number>
  green?: { locked: number; level: boolean; bets: { selection_id: string; side: Side; price: number; stake: number }[]; after: Record<string, number> } | null
}
export interface Trigger { id: string; market_id: string; selection_id: string; price: number; direction: 'le' | 'ge'; label: string; locked: number }
export interface Evt { t: number; text: string; trigger: string }
export interface Order {
  order_id: string; market_id: string; selection_id: string; side: Side; price: number; size: number
  matched: number; avg_price: number; remaining: number; status: string
}
export interface State { mode: string; markets: Record<string, MarketState>; orders: Order[]; totals: { exposure: number; open_pnl: number }; warnings: string[]; triggers: Trigger[]; events: Evt[] }
export interface MarketInfo { market_id: string; name: string; event: string; competition: string; start: string | null; runners: Record<string, string>; in_play?: boolean }

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

export const api = {
  mode: () => call<{ mode: string }>('/api/mode'),
  ping: () => call<{ needs_token: boolean; mode: string }>('/api/ping'),
  markets: (sport: string) => call<MarketInfo[]>(`/api/markets?sport=${sport}`),
  state: (ids: string[]) => call<State>(`/api/state?ids=${ids.join(',')}`),
  place: (b: { market_id: string; selection_id: string; side: Side; price: number; size: number }) =>
    call<{ order: Order; warnings: string[] }>('/api/orders', { method: 'POST', body: JSON.stringify(b) }),
  cancel: (id: string) => call<Order>(`/api/orders/${id}`, { method: 'DELETE' }),
  cancelAll: (market: string, selection?: string, side?: Side) =>
    call<{ cancelled: number }>(`/api/markets/${market}/cancel-all?${new URLSearchParams({ ...(selection ? { selection_id: selection } : {}), ...(side ? { side } : {}) })}`, { method: 'POST' }),
  green: (market: string, hard: boolean) =>
    call<{ greened: boolean; reason?: string; cancelled: number; locked?: number; level?: boolean; placed?: { status: string }[] }>(`/api/markets/${market}/green?hard=${hard}`, { method: 'POST' }),
  addTrigger: (b: { market_id: string; selection_id: string; price: number }) =>
    call<Trigger>('/api/triggers', { method: 'POST', body: JSON.stringify(b) }),
  delTrigger: (id: string) => call<{ cancelled: boolean }>(`/api/triggers/${id}`, { method: 'DELETE' }),
  history: (market: string, selection: string, seconds: number) =>
    call<{ points: [number, number | null, number | null, number | null, number][] }>(`/api/history?${new URLSearchParams({ market_id: market, selection_id: selection, seconds: String(seconds) })}`),
  close: (market: string, selection: string) =>
    call<{ closed: boolean; reason?: string; locked_profit?: number }>(`/api/markets/${market}/close/${selection}`, { method: 'POST' }),
}
