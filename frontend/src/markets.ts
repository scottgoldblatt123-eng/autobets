import type { MarketInfo } from './api'

const GROUPS: [string, RegExp][] = [
  ['Result', /^(MATCH_ODDS|HALF_TIME|DRAW_NO_BET|TO_QUALIFY|ASIAN_HANDICAP|MATCH_ODDS_UNMANAGED|HALF_TIME_MATCH_ODDS)$|HANDICAP|WIN_|DOUBLE_CHANCE|WINNING_MARGIN/],
  ['Match goals', /^(OVER_UNDER|FIRST_HALF_GOALS|BOTH_TEAMS|TOTAL_GOALS|GOAL_LINE|NEXT_GOAL|ODD_OR_EVEN|SECOND_HALF_GOALS|HALF_WITH_MOST)|CLEAN_SHEET/],
  ['Score', /CORRECT_SCORE|HALF_TIME_SCORE|HALF_TIME_FULL_TIME|MATCH_ODDS_AND|FIRST_GOAL_ODDS|TIME_OF_FIRST/],
]
const line = (n: string) => Number((n.match(/(\d+(?:\.\d+)?)/) ?? [])[1] ?? 99)

/** Group an event's markets for the picker. Team totals ("Real Madrid Over/Under 2.5 Goals") are a team's own goals, not the match, so they get their own heading.
 *  Tennis markets are told apart by name: set betting and set winners are "Sets", total games, game handicap and tie-breaks are "Games". */
export function groupMarkets(ms: MarketInfo[], event = ''): [string, MarketInfo[]][] {
  const teams = event.split(/ v | vs /i).map(t => t.trim().toLowerCase()).filter(Boolean)
  const out = new Map<string, MarketInfo[]>()
  for (const m of ms) {
    const t = m.market_type ?? '', n = m.name.toLowerCase()
    let g: string
    if (/corner/.test(n)) g = 'Corners'
    else if (/card|booking/.test(n)) g = 'Cards'
    else if (/^(MATCH_ODDS|HALF_TIME)$/.test(t)) g = 'Result'
    else if (!/game \d/.test(n) && (/^SET_|SET_BETTING|SET_WINNER|SET_HANDICAP/.test(t) || /\bset (betting|\d|winner|handicap)|\bsets?\b.*(handicap|betting|winner)/.test(n))) g = 'Sets'
    else if (/GAMES|GAME_|TIE_?BREAK/.test(t) || /total games|games? handicap|game \d|tie[- ]?break|\bgames\b/.test(n)) g = 'Games'
    else if (/^team_.|TEAM_/.test(t) || teams.some(x => x && n.startsWith(x) && /goals|over|under/.test(n))) g = 'Team goals'
    else g = (GROUPS.find(([, re]) => re.test(t)) ?? ['Other'])[0]
    out.set(g, [...(out.get(g) ?? []), m])
  }
  const order = ['Result', 'Sets', 'Games', 'Match goals', 'Team goals', 'Score', 'Corners', 'Cards', 'Other']
  const same = (x: string, y: string) => x.replace(/[\d.]+/g, '') === y.replace(/[\d.]+/g, '')
  return order.filter(g => out.has(g)).map(g => [g, out.get(g)!.sort((x, y) => (same(x.name, y.name) ? line(x.name) - line(y.name) : x.name.localeCompare(y.name)))] as [string, MarketInfo[]])
}
